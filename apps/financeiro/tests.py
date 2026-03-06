from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.trilha.models import NotaSaude
from apps.usuarios.models import RoleChoices, Usuario

from .models import Contrato, ContratoStatus, Parcela, ParcelaStatus


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
