from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.financeiro.models import Contrato, ContratoStatus, OrigemParcela, Parcela, TipoParcela
from apps.usuarios.models import RoleChoices, Usuario

from .models import EnvioOnboarding, NotificacaoInterna, PerfilEmpresarial, PropostaFinanceira, StatusPropostaFinanceira


class ComercialFlowTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create(
            email="admin@mindhub.com",
            senha="123",
            role=RoleChoices.ADMIN,
            nome="Admin",
        )
        self.admin_master = Usuario.objects.create(
            email="master@mindhub.com",
            senha="123",
            role=RoleChoices.ADMIN,
            nome="Admin Master",
            pode_aprovar_financeiro=True,
        )
        self.monitor = Usuario.objects.create(
            email="monitor@mindhub.com",
            senha="123",
            role=RoleChoices.MONITOR,
            nome="Monitor",
        )

    def login_as(self, usuario: Usuario):
        session = self.client.session
        session["usuario"] = usuario.email
        session.save()

    def payload_cadastro(self, **overrides):
        hoje = timezone.localdate()
        payload = {
            "nome": "Aluno Novo",
            "email": "novo@mindhub.com",
            "telefone": "11999999999",
            "senha": "SenhaForte123",
            "monitor_responsavel": self.monitor.id,
            "nome_empresa": "Cafe Mindhub",
            "telefone_empresa": "1133334444",
            "cnpj": "12.345.678/0001-90",
            "endereco": "Rua Central, 100",
            "nicho": "CAFE",
            "nome_representante": "Bianca",
            "cpf_representante": "123.456.789-00",
            "dificuldades": ["ESTOQUE", "CMV"],
            "observacoes": "Duas operacoes e uma cozinha central.",
            "valor_total_negociado": "2000.00",
            "data_assinatura": hoje.isoformat(),
            "quantidade_entrada": "1",
            "valor_entrada": "500.00",
            "quantidade_recorrente": "3",
            "valor_recorrente": "500.00",
            "primeiro_vencimento": hoje.isoformat(),
        }
        payload.update(overrides)
        return payload

    def criar_aluno_com_contrato(self):
        aluno = Usuario.objects.create(
            email="aluno@mindhub.com",
            senha="123",
            role=RoleChoices.ALUNO,
            nome="Aluno Atual",
            monitor_responsavel=self.monitor,
        )
        PerfilEmpresarial.objects.create(
            aluno=aluno,
            nome_empresa="Empresa Atual",
            nicho="RESTAURANTE",
            dificuldades=["FINANCEIRO"],
            monitor_responsavel_snapshot=self.monitor,
        )
        contrato = Contrato.objects.create(
            aluno=aluno,
            valor_total_negociado="1200.00",
            data_assinatura=timezone.localdate(),
            observacoes_gerais="Contrato inicial",
            status=ContratoStatus.ATIVO,
            criado_por=self.admin,
        )
        return aluno, contrato

    def test_cadastro_onboarding_cria_ficha_completa(self):
        self.login_as(self.admin)

        response = self.client.post(reverse("comercial:cadastro_novo"), data=self.payload_cadastro())

        self.assertEqual(response.status_code, 302)

        aluno = Usuario.objects.get(email="novo@mindhub.com")
        perfil = PerfilEmpresarial.objects.get(aluno=aluno)
        contrato = Contrato.objects.get(aluno=aluno)

        self.assertEqual(aluno.role, RoleChoices.ALUNO)
        self.assertEqual(aluno.monitor_responsavel, self.monitor)
        self.assertEqual(perfil.nome_empresa, "Cafe Mindhub")
        self.assertEqual(contrato.valor_total_negociado, Decimal("2000.00"))
        self.assertEqual(contrato.parcelas.filter(ativa=True).count(), 4)
        self.assertEqual(EnvioOnboarding.objects.filter(aluno=aluno).count(), 2)
        self.assertTrue(NotificacaoInterna.objects.filter(destinatario=self.monitor, aluno=aluno).exists())
        self.assertTrue(contrato.parcelas.exclude(asaas_payment_id="").exists())

    def test_monitor_visualiza_ficha_mas_nao_edita(self):
        aluno, contrato = self.criar_aluno_com_contrato()
        Parcela.objects.create(
            contrato=contrato,
            numero=1,
            valor="400.00",
            data_vencimento=timezone.localdate(),
            tipo_parcela=TipoParcela.ENTRADA,
        )

        self.login_as(self.monitor)

        response = self.client.get(reverse("comercial:cadastro_detalhe", args=[aluno.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Propor renegociacao")

        self.client.post(
            reverse("comercial:cadastro_detalhe", args=[aluno.id]),
            data=self.payload_cadastro(nome="Nome Alterado", email=aluno.email),
        )
        aluno.refresh_from_db()

        self.assertEqual(aluno.nome, "Aluno Atual")

    def test_monitor_envia_proposta_e_admin_master_aprova(self):
        aluno, contrato = self.criar_aluno_com_contrato()
        parcela_1 = Parcela.objects.create(
            contrato=contrato,
            numero=1,
            valor="400.00",
            data_vencimento=timezone.localdate() + timedelta(days=2),
            tipo_parcela=TipoParcela.ENTRADA,
        )
        parcela_2 = Parcela.objects.create(
            contrato=contrato,
            numero=2,
            valor="400.00",
            data_vencimento=timezone.localdate() + timedelta(days=32),
            tipo_parcela=TipoParcela.RECORRENTE,
        )

        self.login_as(self.monitor)
        response = self.client.post(
            reverse("comercial:criar_proposta", args=[aluno.id]),
            data={
                "motivo": "Reprogramar caixa do aluno",
                "observacao_monitor": "Solicitou parcelas menores.",
                "quantidade_parcelas": 2,
                "valor_parcela": "350.00",
                "primeiro_vencimento": (timezone.localdate() + timedelta(days=15)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 302)

        proposta = PropostaFinanceira.objects.get(aluno=aluno)
        self.assertEqual(proposta.status, StatusPropostaFinanceira.PENDENTE)
        self.assertTrue(
            NotificacaoInterna.objects.filter(destinatario=self.admin_master, aluno=aluno).exists()
        )

        self.login_as(self.admin_master)
        approve_response = self.client.post(
            reverse("comercial:aprovar_proposta", args=[proposta.id]),
            data={"observacao_admin": "Aprovado para preservar o contrato."},
        )

        self.assertEqual(approve_response.status_code, 302)

        proposta.refresh_from_db()
        parcela_1.refresh_from_db()
        parcela_2.refresh_from_db()

        novas_parcelas = list(contrato.parcelas.filter(ativa=True).order_by("numero"))
        self.assertEqual(proposta.status, StatusPropostaFinanceira.APROVADA)
        self.assertFalse(parcela_1.ativa)
        self.assertFalse(parcela_2.ativa)
        self.assertEqual(len(novas_parcelas), 2)
        self.assertTrue(all(parcela.origem == OrigemParcela.RENEGOCIACAO for parcela in novas_parcelas))
        self.assertTrue(all(parcela.asaas_payment_id for parcela in novas_parcelas))

    def test_edicao_financeira_com_pagamento_registrado_retorna_erro(self):
        aluno, contrato = self.criar_aluno_com_contrato()
        Parcela.objects.create(
            contrato=contrato,
            numero=1,
            valor="600.00",
            data_vencimento=timezone.localdate() - timedelta(days=10),
            data_pagamento=timezone.localdate() - timedelta(days=2),
            tipo_parcela=TipoParcela.ENTRADA,
        )
        Parcela.objects.create(
            contrato=contrato,
            numero=2,
            valor="600.00",
            data_vencimento=timezone.localdate() + timedelta(days=20),
            tipo_parcela=TipoParcela.RECORRENTE,
        )

        self.login_as(self.admin)
        response = self.client.post(
            reverse("comercial:cadastro_detalhe", args=[aluno.id]),
            data=self.payload_cadastro(
                nome=aluno.nome,
                email=aluno.email,
                quantidade_entrada="0",
                quantidade_recorrente="4",
                valor_recorrente="300.00",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nao e possivel reescrever o parcelamento")
        self.assertEqual(contrato.parcelas.filter(ativa=True).count(), 2)
