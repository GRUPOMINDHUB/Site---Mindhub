from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils.dateparse import parse_date

from apps.usuarios.models import Usuario

from .asaas_service import cancelar_cobranca_parcela, criar_cobranca_parcela, atualizar_vencimento_cobranca
from .models import ContratoStatus, OrigemParcela, Parcela, PropostaRenegociacao, TipoRenegociacao

ZERO = Decimal("0.00")


class RenegociacaoError(ValueError):
    pass


def _parse_data(valor: date | str | None, campo: str) -> date:
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        data = parse_date(valor)
        if data:
            return data
    raise RenegociacaoError(f"Campo {campo} invalido.")


def _parse_decimal(valor, campo: str) -> Decimal:
    try:
        convertido = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise RenegociacaoError(f"Campo {campo} invalido.")
    if convertido <= ZERO:
        raise RenegociacaoError(f"Campo {campo} deve ser maior que zero.")
    return convertido


def _normalizar_fatiamento(dados_fatiamento) -> list[dict]:
    if not isinstance(dados_fatiamento, list) or len(dados_fatiamento) < 2:
        raise RenegociacaoError("Informe ao menos duas fatias para quebrar a parcela.")

    fatias = []
    for indice, fatia in enumerate(dados_fatiamento, start=1):
        if not isinstance(fatia, dict):
            raise RenegociacaoError("Formato de fatias invalido.")
        valor = _parse_decimal(fatia.get("valor"), f"dados_fatiamento[{indice}].valor")
        data_vencimento = _parse_data(fatia.get("data_vencimento"), f"dados_fatiamento[{indice}].data_vencimento")
        fatias.append({"numero": indice, "valor": valor, "data_vencimento": data_vencimento})
    return fatias


def _validar_limites_renegociacao(parcela: Parcela):
    if parcela.contrato.status == ContratoStatus.CANCELADO:
        raise RenegociacaoError("Nao e possivel renegociar parcela de contrato cancelado.")
    if parcela.ja_renegociada:
        raise RenegociacaoError("Esta parcela ja foi renegociada e nao pode ser renegociada novamente.")
    if not parcela.ativa:
        raise RenegociacaoError("Nao e possivel renegociar parcela inativa.")
    if parcela.data_pagamento:
        raise RenegociacaoError("Nao e possivel renegociar parcela ja paga.")


def _proximo_numero_parcela(contrato_id: int) -> int:
    ultimo = (
        Parcela.objects.select_for_update()
        .filter(contrato_id=contrato_id)
        .order_by("-numero")
        .values_list("numero", flat=True)
        .first()
        or 0
    )
    return ultimo + 1


def _append_obs(atual: str, nova: str) -> str:
    atual = (atual or "").strip()
    nova = (nova or "").strip()
    if not nova:
        return atual
    if not atual:
        return nova
    return f"{atual}\n{nova}"


@transaction.atomic
def executar_renegociacao(
    *,
    parcela_id: int,
    tipo_renegociacao: str,
    executado_por: Usuario | None = None,
    nova_data_vencimento: date | str | None = None,
    dados_fatiamento=None,
    observacoes: str = "",
):
    parcela = (
        Parcela.objects.select_for_update()
        .select_related("contrato")
        .get(id=parcela_id)
    )
    _validar_limites_renegociacao(parcela)

    if tipo_renegociacao not in {TipoRenegociacao.ADIAR, TipoRenegociacao.QUEBRAR}:
        raise RenegociacaoError("Tipo de renegociacao invalido.")

    if tipo_renegociacao == TipoRenegociacao.QUEBRAR:
        fatias = _normalizar_fatiamento(dados_fatiamento)

        cancelar_cobranca_parcela(parcela)

        parcela.ativa = False
        parcela.ja_renegociada = True
        parcela.observacoes = _append_obs(parcela.observacoes, "[RENEGOCIACAO] Parcela quebrada em novas fatias.")
        parcela.save(update_fields=["ativa", "ja_renegociada", "observacoes"])

        proposta = PropostaRenegociacao.objects.create(
            contrato=parcela.contrato,
            parcela_alvo=parcela,
            tipo_renegociacao=TipoRenegociacao.QUEBRAR,
            dados_fatiamento=[
                {
                    "numero": fatia["numero"],
                    "valor": str(fatia["valor"]),
                    "data_vencimento": fatia["data_vencimento"].isoformat(),
                }
                for fatia in fatias
            ],
            criada_por=executado_por,
            observacoes=observacoes,
        )

        numero_atual = _proximo_numero_parcela(parcela.contrato_id)
        novas_parcelas = []
        for fatia in fatias:
            nova_parcela = Parcela.objects.create(
                contrato=parcela.contrato,
                numero=numero_atual,
                valor=fatia["valor"],
                data_vencimento=fatia["data_vencimento"],
                link_pagamento_ou_pix=parcela.link_pagamento_ou_pix,
                observacoes=_append_obs(observacoes, f"[RENEGOCIACAO] Derivada da parcela {parcela.numero}."),
                tipo_parcela=parcela.tipo_parcela,
                origem=OrigemParcela.RENEGOCIACAO,
                parcela_origem=parcela,
            )
            criar_cobranca_parcela(nova_parcela)
            novas_parcelas.append(nova_parcela)
            numero_atual += 1

        return {"proposta": proposta, "parcelas": novas_parcelas}

    data_original = parcela.data_vencimento
    nova_data = _parse_data(nova_data_vencimento, "nova_data_vencimento")
    delta = nova_data - data_original
    if not isinstance(delta, timedelta) or delta.days == 0:
        raise RenegociacaoError("A nova data de vencimento deve ser diferente da data atual.")

    proposta = PropostaRenegociacao.objects.create(
        contrato=parcela.contrato,
        parcela_alvo=parcela,
        tipo_renegociacao=TipoRenegociacao.ADIAR,
        dados_fatiamento={
            "data_original": data_original.isoformat(),
            "nova_data_vencimento": nova_data.isoformat(),
            "delta_dias": delta.days,
        },
        criada_por=executado_por,
        observacoes=observacoes,
    )

    parcela.ja_renegociada = True
    parcela.observacoes = _append_obs(parcela.observacoes, "[RENEGOCIACAO] Parcela adiada em efeito cascata.")
    parcela.save(update_fields=["ja_renegociada", "observacoes"])
    atualizar_vencimento_cobranca(parcela, nova_data)

    futuras = list(
        Parcela.objects.select_for_update()
        .filter(
            contrato=parcela.contrato,
            ativa=True,
            data_pagamento__isnull=True,
            data_vencimento__gt=data_original,
        )
        .exclude(id=parcela.id)
        .order_by("data_vencimento", "numero")
    )
    for parcela_futura in futuras:
        atualizar_vencimento_cobranca(parcela_futura, parcela_futura.data_vencimento + delta)

    return {"proposta": proposta, "parcelas": [parcela] + futuras}
