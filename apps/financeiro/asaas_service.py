from __future__ import annotations

from datetime import date
from uuid import uuid4

from django.utils import timezone

from .models import Contrato, Parcela


def garantir_customer_contrato(contrato: Contrato) -> Contrato:
    if contrato.asaas_customer_id:
        return contrato

    contrato.asaas_customer_id = f"ASAAS-CUST-{contrato.aluno_id}"
    contrato.save(update_fields=["asaas_customer_id"])
    return contrato


def criar_cobranca_parcela(parcela: Parcela) -> Parcela:
    garantir_customer_contrato(parcela.contrato)
    if not parcela.asaas_payment_id:
        parcela.asaas_payment_id = f"ASAAS-PAY-{uuid4().hex[:12].upper()}"

    parcela.asaas_invoice_url = f"https://www.asaas.com/i/{parcela.asaas_payment_id}"
    parcela.sincronizada_asaas_em = timezone.now()
    if not parcela.link_pagamento_ou_pix:
        parcela.link_pagamento_ou_pix = parcela.asaas_invoice_url
    parcela.save(
        update_fields=[
            "asaas_payment_id",
            "asaas_invoice_url",
            "sincronizada_asaas_em",
            "link_pagamento_ou_pix",
        ]
    )
    return parcela


def cancelar_cobranca_parcela(parcela: Parcela) -> Parcela:
    # Stub local para manter rastreabilidade sem apagar dados financeiros.
    parcela.sincronizada_asaas_em = timezone.now()
    parcela.save(update_fields=["sincronizada_asaas_em"])
    return parcela


def atualizar_vencimento_cobranca(parcela: Parcela, nova_data_vencimento: date) -> Parcela:
    parcela.data_vencimento = nova_data_vencimento
    parcela.sincronizada_asaas_em = timezone.now()
    parcela.save(update_fields=["data_vencimento", "sincronizada_asaas_em"])
    return parcela
