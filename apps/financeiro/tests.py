import json
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.trilha.models import NotaSaude
from apps.usuarios.models import RoleChoices, Usuario

from .models import Contrato, ContratoStatus, OrigemParcela, Parcela, ParcelaStatus, TipoRenegociacao
from .renegociacao_service import RenegociacaoError, executar_renegociacao
from .services import contexto_dashboard_financeiro


class FinanceiroTests(TestCase):
    def setUp(self):
        self.monitor = Usuario.objects.create(
            email="monitor@mindhub.com",
            senha="123",
            role=RoleChoices.MONITOR,
            nome="Monitor Financeiro",
            telefone="(11) 99999-1111",
        )
        self.aluno = Usuario.objects.create(
            email="aluno@mindhub.com",
            senha="123",
            role=RoleChoices.ALUNO,
            nome="Aluno Teste",
            monitor_responsavel=self.monitor,
            telefone="(11) 98888-0000",
        )
        self.contrato = Contrato.objects.create(
            aluno=self.aluno,
            valor_total_negociado="1200.00",
            data_assinatura=timezone.localdate(),
            status=ContratoStatus.ATIVO,
        )

    def test_status_dinamico_da_parcela(self):
        hoje = timezone.localdate()
        parcela = Parcela.objects.create(
            contrato=self.contrato,
            numero=1,
            valor="300.00",
            data_vencimento=hoje,
        )
        self.assertEqual(parcela.status_dinamico, ParcelaStatus.PENDENTE)

        parcela.data_vencimento = hoje - timedelta(days=3)
        parcela.data_pagamento = None
        parcela.save()
        self.assertEqual(parcela.status_dinamico, ParcelaStatus.ATRASADO)

        parcela.data_vencimento = hoje - timedelta(days=9)
        parcela.save()
        self.assertEqual(parcela.status_dinamico, ParcelaStatus.INADIMPLENTE)

        parcela.data_pagamento = hoje
        parcela.save()
        self.assertEqual(parcela.status_dinamico, ParcelaStatus.PAGO)

        self.contrato.status = ContratoStatus.CANCELADO
        self.contrato.save()
        parcela.data_pagamento = None
        parcela.save()
        self.assertEqual(parcela.status_dinamico, ParcelaStatus.CANCELADO)

    def test_signal_forca_nota_saude_critica(self):
        Parcela.objects.create(
            contrato=self.contrato,
            numero=1,
            valor="300.00",
            data_vencimento=timezone.localdate() - timedelta(days=4),
        )

        nota = NotaSaude.objects.filter(aluno=self.aluno).first()
        self.assertIsNotNone(nota)
        self.assertEqual(nota.nota, 1)
        self.assertTrue(nota.automatica)

    def test_aluno_inadimplente_e_redirecionado_na_trilha(self):
        Parcela.objects.create(
            contrato=self.contrato,
            numero=1,
            valor="300.00",
            data_vencimento=timezone.localdate() - timedelta(days=10),
        )

        session = self.client.session
        session["usuario"] = self.aluno.email
        session.save()

        response = self.client.get(reverse("trilha:home_trilha"))

        self.assertRedirects(response, reverse("financeiro:aviso_inadimplencia"))

    def test_dashboard_financeiro_renderiza_para_monitor(self):
        Parcela.objects.create(
            contrato=self.contrato,
            numero=1,
            valor="300.00",
            data_vencimento=timezone.localdate() + timedelta(days=2),
        )

        session = self.client.session
        session["usuario"] = self.monitor.email
        session.save()

        response = self.client.get(reverse("financeiro:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Central Financeira")

    def test_status_cancelada_renegociacao(self):
        parcela = Parcela.objects.create(
            contrato=self.contrato,
            numero=1,
            valor="300.00",
            data_vencimento=timezone.localdate() + timedelta(days=2),
        )
        parcela.ativa = False
        parcela.ja_renegociada = True
        parcela.save(update_fields=["ativa", "ja_renegociada"])

        self.assertEqual(parcela.status_dinamico, ParcelaStatus.CANCELADA_RENEGOCIACAO)

    def test_motor_quebrar_soft_delete_e_rastreabilidade(self):
        parcela = Parcela.objects.create(
            contrato=self.contrato,
            numero=1,
            valor="900.00",
            data_vencimento=timezone.localdate() + timedelta(days=7),
            link_pagamento_ou_pix="https://link-original",
        )

        executar_renegociacao(
            parcela_id=parcela.id,
            tipo_renegociacao=TipoRenegociacao.QUEBRAR,
            executado_por=self.monitor,
            dados_fatiamento=[
                {"valor": "450.00", "data_vencimento": (timezone.localdate() + timedelta(days=12)).isoformat()},
                {"valor": "450.00", "data_vencimento": (timezone.localdate() + timedelta(days=22)).isoformat()},
            ],
        )

        parcela.refresh_from_db()
        self.assertFalse(parcela.ativa)
        self.assertTrue(parcela.ja_renegociada)
        self.assertEqual(parcela.status_dinamico, ParcelaStatus.CANCELADA_RENEGOCIACAO)

        novas = Parcela.objects.filter(contrato=self.contrato, parcela_origem=parcela).order_by("numero")
        self.assertEqual(novas.count(), 2)
        self.assertTrue(all(item.origem == OrigemParcela.RENEGOCIACAO for item in novas))

        with self.assertRaises(RenegociacaoError):
            executar_renegociacao(
                parcela_id=parcela.id,
                tipo_renegociacao=TipoRenegociacao.ADIAR,
                executado_por=self.monitor,
                nova_data_vencimento=(timezone.localdate() + timedelta(days=30)).isoformat(),
            )

    def test_motor_adiar_aplica_cascata(self):
        hoje = timezone.localdate()
        parcela_alvo = Parcela.objects.create(
            contrato=self.contrato,
            numero=1,
            valor="300.00",
            data_vencimento=hoje + timedelta(days=5),
        )
        parcela_futura = Parcela.objects.create(
            contrato=self.contrato,
            numero=2,
            valor="300.00",
            data_vencimento=hoje + timedelta(days=35),
        )

        executar_renegociacao(
            parcela_id=parcela_alvo.id,
            tipo_renegociacao=TipoRenegociacao.ADIAR,
            executado_por=self.monitor,
            nova_data_vencimento=(hoje + timedelta(days=15)).isoformat(),
        )

        parcela_alvo.refresh_from_db()
        parcela_futura.refresh_from_db()
        self.assertTrue(parcela_alvo.ja_renegociada)
        self.assertEqual(parcela_alvo.data_vencimento, hoje + timedelta(days=15))
        self.assertEqual(parcela_futura.data_vencimento, hoje + timedelta(days=45))

    def test_dashboard_exibe_volume_renegociado(self):
        hoje = timezone.localdate()
        Parcela.objects.create(
            contrato=self.contrato,
            numero=1,
            valor="500.00",
            data_vencimento=hoje + timedelta(days=4),
            ja_renegociada=True,
        )
        Parcela.objects.create(
            contrato=self.contrato,
            numero=2,
            valor="300.00",
            data_vencimento=hoje + timedelta(days=10),
        )

        contexto = contexto_dashboard_financeiro(self.monitor, "mensal", referencia=hoje)
        self.assertEqual(contexto["metrics"]["volume_renegociado"], Decimal("500.00"))

    def test_api_renegociar_parcela(self):
        parcela = Parcela.objects.create(
            contrato=self.contrato,
            numero=1,
            valor="600.00",
            data_vencimento=timezone.localdate() + timedelta(days=6),
        )
        session = self.client.session
        session["usuario"] = self.monitor.email
        session.save()

        response = self.client.post(
            reverse("financeiro:api_renegociar_parcela", args=[parcela.id]),
            data=json.dumps(
                {
                    "tipo_renegociacao": "ADIAR",
                    "nova_data_vencimento": (timezone.localdate() + timedelta(days=16)).isoformat(),
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])

        parcela.refresh_from_db()
        self.assertTrue(parcela.ja_renegociada)
