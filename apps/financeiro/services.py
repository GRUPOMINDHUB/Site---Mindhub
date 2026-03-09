from __future__ import annotations

import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from urllib.parse import quote

from django.db.models import Prefetch
from django.utils import timezone

from apps.usuarios.models import RoleChoices, Usuario

from .models import Contrato, ContratoStatus, Parcela, ParcelaStatus

PIX_MINDHUB = "biancafraga.mentoria@gmail.com"
OBSERVACAO_NOTA_FINANCEIRA = (
    "[FINANCEIRO] Nota reduzida automaticamente devido a parcela atrasada ou inadimplente."
)
STATUS_UI = {
    "PAGO": {
        "label": "Pago",
        "badge_class": "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
        "dot_class": "bg-emerald-400",
    },
    "PENDENTE": {
        "label": "Pendente",
        "badge_class": "bg-amber-400/15 text-amber-200 ring-1 ring-amber-400/30",
        "dot_class": "bg-amber-300",
    },
    "ATRASADO": {
        "label": "Atrasado",
        "badge_class": "bg-red-700/20 text-red-200 ring-1 ring-red-700/40",
        "dot_class": "bg-red-500",
    },
    "INADIMPLENTE": {
        "label": "Inadimplente",
        "badge_class": "bg-[#e30613]/20 text-red-100 ring-1 ring-[#e30613]/40",
        "dot_class": "bg-[#e30613]",
    },
    "CANCELADA_RENEGOCIACAO": {
        "label": "Cancelada (renegociacao)",
        "badge_class": "bg-white/5 text-zinc-400 ring-1 ring-white/10",
        "dot_class": "bg-zinc-500",
    },
    "CANCELADO": {
        "label": "Cancelado",
        "badge_class": "bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/30",
        "dot_class": "bg-slate-400",
    },
    "SEM_CONTRATO": {
        "label": "Sem contrato",
        "badge_class": "bg-white/10 text-slate-300 ring-1 ring-white/10",
        "dot_class": "bg-slate-500",
    },
}
ZERO = Decimal("0.00")


@dataclass(frozen=True)
class PeriodoFinanceiro:
    chave: str
    label: str
    data_inicio: date
    data_fim: date
    proximo_inicio: date
    proximo_fim: date


def hoje_local() -> date:
    return timezone.localdate()


def moeda_brl(valor: Decimal | None) -> str:
    valor = valor or ZERO
    return f"{valor:.2f}".replace(".", ",")


def data_brasileira(valor: date | None) -> str:
    if not valor:
        return "-"
    return valor.strftime("%d/%m/%Y")


def normalizar_telefone_whatsapp(telefone: str | None) -> str:
    digitos = re.sub(r"\D", "", telefone or "")
    if not digitos:
        return ""
    if digitos.startswith("55"):
        return digitos
    return f"55{digitos}"


def status_ui(status: str) -> dict[str, str]:
    return STATUS_UI.get(status, STATUS_UI["SEM_CONTRATO"])


def adicionar_meses(ano: int, mes: int, quantidade: int) -> tuple[int, int]:
    indice = (ano * 12) + (mes - 1) + quantidade
    novo_ano, novo_mes = divmod(indice, 12)
    return novo_ano, novo_mes + 1


def limites_mes(ano: int, mes: int) -> tuple[date, date]:
    ultimo_dia = monthrange(ano, mes)[1]
    return date(ano, mes, 1), date(ano, mes, ultimo_dia)


def calcular_periodo_financeiro(periodo: str, referencia: date | None = None) -> PeriodoFinanceiro:
    referencia = referencia or hoje_local()
    periodo = periodo if periodo in {"mensal", "trimestral", "semestral", "anual"} else "mensal"

    if periodo == "trimestral":
        mes_inicio = ((referencia.month - 1) // 3) * 3 + 1
        meses = 3
        label = "Trimestral"
    elif periodo == "semestral":
        mes_inicio = 1 if referencia.month <= 6 else 7
        meses = 6
        label = "Semestral"
    elif periodo == "anual":
        mes_inicio = 1
        meses = 12
        label = "Anual"
    else:
        mes_inicio = referencia.month
        meses = 1
        label = "Mensal"

    ano_inicio = referencia.year
    data_inicio = date(ano_inicio, mes_inicio, 1)
    ano_fim, mes_fim = adicionar_meses(ano_inicio, mes_inicio, meses - 1)
    _, data_fim = limites_mes(ano_fim, mes_fim)

    prox_ano, prox_mes = adicionar_meses(ano_inicio, mes_inicio, meses)
    proximo_inicio = date(prox_ano, prox_mes, 1)
    prox_fim_ano, prox_fim_mes = adicionar_meses(prox_ano, prox_mes, meses - 1)
    _, proximo_fim = limites_mes(prox_fim_ano, prox_fim_mes)

    return PeriodoFinanceiro(
        chave=periodo,
        label=label,
        data_inicio=data_inicio,
        data_fim=data_fim,
        proximo_inicio=proximo_inicio,
        proximo_fim=proximo_fim,
    )


def periodo_opcoes() -> list[dict[str, str]]:
    return [
        {"value": "mensal", "label": "Mensal"},
        {"value": "trimestral", "label": "Trimestral"},
        {"value": "semestral", "label": "Semestral"},
        {"value": "anual", "label": "Anual"},
    ]


def alunos_financeiros(usuario: Usuario) -> list[Usuario]:
    parcelas_prefetch = Prefetch(
        "contrato__parcelas",
        queryset=Parcela.objects.filter(ativa=True).order_by("data_vencimento", "numero"),
    )
    queryset = (
        Usuario.objects.filter(role=RoleChoices.ALUNO, ativo=True)
        .select_related("monitor_responsavel", "contrato")
        .prefetch_related(parcelas_prefetch)
        .order_by("nome", "email")
    )
    if usuario.is_monitor:
        queryset = queryset.filter(monitor_responsavel=usuario)
    return list(queryset)


def status_principal_contrato(contrato, referencia: date | None = None) -> str:
    if not contrato:
        return "SEM_CONTRATO"
    if contrato.status == ContratoStatus.CANCELADO:
        return ParcelaStatus.CANCELADO
    if contrato.possui_status(ParcelaStatus.INADIMPLENTE, referencia):
        return ParcelaStatus.INADIMPLENTE
    if contrato.possui_status(ParcelaStatus.ATRASADO, referencia):
        return ParcelaStatus.ATRASADO
    if contrato.possui_status(ParcelaStatus.PENDENTE, referencia):
        return ParcelaStatus.PENDENTE
    return ParcelaStatus.PAGO


def sincronizar_nota_saude_financeira(aluno: Usuario, referencia: date | None = None) -> bool:
    if not aluno or not aluno.is_aluno:
        return False

    contrato = getattr(aluno, "contrato", None)
    if not contrato or contrato.status == ContratoStatus.CANCELADO:
        return False

    referencia = referencia or hoje_local()
    if not contrato.possui_status(ParcelaStatus.ATRASADO, referencia) and not contrato.possui_status(
        ParcelaStatus.INADIMPLENTE, referencia
    ):
        return False

    from apps.trilha.models import NotaSaude

    ultima_nota = NotaSaude.objects.filter(aluno=aluno).first()
    if ultima_nota and ultima_nota.nota == 1:
        return False

    NotaSaude.objects.create(
        aluno=aluno,
        nota=1,
        automatica=True,
        observacao=OBSERVACAO_NOTA_FINANCEIRA,
    )
    return True


def possui_bloqueio_trilha(aluno: Usuario, referencia: date | None = None) -> bool:
    if not aluno or not aluno.is_aluno:
        return False

    contrato = getattr(aluno, "contrato", None)
    if not contrato or contrato.status == ContratoStatus.CANCELADO:
        return False

    referencia = referencia or hoje_local()
    return contrato.possui_status(ParcelaStatus.INADIMPLENTE, referencia)


def resumo_aluno_financeiro(aluno: Usuario, referencia: date | None = None) -> dict[str, object]:
    referencia = referencia or hoje_local()
    contrato = getattr(aluno, "contrato", None)
    monitor = aluno.monitor_responsavel
    status_codigo = status_principal_contrato(contrato, referencia)
    estilo = status_ui(status_codigo)
    parcela_atual = contrato.parcela_referencia(referencia) if contrato else None

    if status_codigo in {ParcelaStatus.ATRASADO, ParcelaStatus.INADIMPLENTE}:
        sincronizar_nota_saude_financeira(aluno, referencia)

    return {
        "id": aluno.id,
        "nome": aluno.nome or aluno.email.split("@")[0],
        "email": aluno.email,
        "telefone": aluno.telefone,
        "telefone_whatsapp": normalizar_telefone_whatsapp(aluno.telefone),
        "monitor_nome": monitor.nome if monitor and monitor.nome else (monitor.email if monitor else "Sem monitor"),
        "status_codigo": status_codigo,
        "status_label": estilo["label"],
        "status_badge_class": estilo["badge_class"],
        "status_dot_class": estilo["dot_class"],
        "contrato_status": contrato.status if contrato else None,
        "parcela_atual": (
            {
                "id": parcela_atual.id,
                "numero": parcela_atual.numero,
                "valor": parcela_atual.valor,
                "data_vencimento": parcela_atual.data_vencimento,
                "data_vencimento_br": data_brasileira(parcela_atual.data_vencimento),
                "dias_atraso": parcela_atual.dias_atraso(referencia),
            }
            if parcela_atual
            else None
        ),
    }


def mensagem_cobranca_preventiva(nome_aluno: str, valor: Decimal, data_vencimento: date, link_pagamento: str, nome_monitor: str) -> str:
    return (
        f'Olá, {nome_aluno}! Tudo bem? 😊 Passando para te dar um "alô" preventivo: '
        f"sua próxima parcela no valor de R$ {moeda_brl(valor)} vence daqui a dois dias úteis, "
        f"no dia {data_brasileira(data_vencimento)}.\n\n"
        f"🔑 Chave Pix: {PIX_MINDHUB} OU 🔗 Link de Pagamento: {link_pagamento}\n\n"
        f"Caso precise de algo ou queira adiantar o pagamento, estou à disposição! "
        f"Um abraço, {nome_monitor} | Monitoria – Grupo MindHub"
    )


def mensagem_cobranca_hoje(nome_aluno: str, valor: Decimal, link_pagamento: str) -> str:
    return (
        f"Bom dia, {nome_aluno}! Tudo certo? Hoje vence a sua parcela de R$ {moeda_brl(valor)}. "
        "Para facilitar, seguem os dados para pagamento:\n\n"
        f"🔑 Chave Pix: {PIX_MINDHUB} 🔗 Link de Pagamento: {link_pagamento}\n\n"
        "Assim que realizar o pagamento, por favor, me envie o comprovante por aqui para darmos baixa."
    )


def link_whatsapp(telefone: str, mensagem: str) -> str:
    if not telefone:
        return ""
    return f"https://wa.me/{telefone}?text={quote(mensagem, safe='')}"


def ficha_aluno_financeira(aluno: Usuario, referencia: date | None = None) -> dict[str, object]:
    referencia = referencia or hoje_local()
    contrato = getattr(aluno, "contrato", None)
    if not contrato:
        raise Contrato.DoesNotExist("Aluno sem contrato")

    monitor_nome = (
        aluno.monitor_responsavel.nome
        if aluno.monitor_responsavel and aluno.monitor_responsavel.nome
        else "Monitor"
    )
    telefone = normalizar_telefone_whatsapp(aluno.telefone)
    sincronizar_nota_saude_financeira(aluno, referencia)

    parcelas = []
    for parcela in contrato.parcelas.all().order_by("data_vencimento", "numero"):
        status = parcela.get_status(referencia)
        link_pagamento = parcela.link_pagamento_ou_pix or "Nao informado"
        pode_cobrar = status not in {ParcelaStatus.PAGO, ParcelaStatus.CANCELADO, ParcelaStatus.CANCELADA_RENEGOCIACAO}
        tem_historico_renegociacao = bool(parcela.parcela_origem_id or parcela.ja_renegociada)
        exibir_tag_renegociado = (
            tem_historico_renegociacao and status in {ParcelaStatus.PENDENTE, ParcelaStatus.ATRASADO, ParcelaStatus.INADIMPLENTE}
        )
        pode_renegociar = parcela.ativa and not parcela.data_pagamento and not parcela.ja_renegociada and status in {
            ParcelaStatus.PENDENTE,
            ParcelaStatus.ATRASADO,
            ParcelaStatus.INADIMPLENTE,
        }

        parcelas.append(
            {
                "id": parcela.id,
                "numero": parcela.numero,
                "valor": str(parcela.valor),
                "valor_formatado": moeda_brl(parcela.valor),
                "data_vencimento": parcela.data_vencimento.isoformat(),
                "data_vencimento_br": data_brasileira(parcela.data_vencimento),
                "data_pagamento": parcela.data_pagamento.isoformat() if parcela.data_pagamento else "",
                "data_pagamento_br": data_brasileira(parcela.data_pagamento) if parcela.data_pagamento else "",
                "status": status,
                "status_label": status_ui(status)["label"],
                "status_badge_class": status_ui(status)["badge_class"],
                "dias_atraso": parcela.dias_atraso(referencia),
                "ativa": parcela.ativa,
                "ja_renegociada": parcela.ja_renegociada,
                "parcela_origem_id": parcela.parcela_origem_id,
                "is_cancelada_renegociacao": status == ParcelaStatus.CANCELADA_RENEGOCIACAO,
                "exibir_tag_renegociado": exibir_tag_renegociado,
                "pode_renegociar": pode_renegociar,
                "link_pagamento_ou_pix": parcela.link_pagamento_ou_pix or "",
                "comprovante_url": parcela.comprovante.url if parcela.comprovante else "",
                "observacoes": parcela.observacoes or "",
                "whatsapp_prev_url": (
                    link_whatsapp(
                        telefone,
                        mensagem_cobranca_preventiva(
                            aluno.nome or aluno.email.split("@")[0],
                            parcela.valor,
                            parcela.data_vencimento,
                            link_pagamento,
                            monitor_nome,
                        ),
                    )
                    if pode_cobrar
                    else ""
                ),
                "whatsapp_today_url": (
                    link_whatsapp(
                        telefone,
                        mensagem_cobranca_hoje(
                            aluno.nome or aluno.email.split("@")[0],
                            parcela.valor,
                            link_pagamento,
                        ),
                    )
                    if pode_cobrar
                    else ""
                ),
            }
        )

    return {
        "aluno": {
            "id": aluno.id,
            "nome": aluno.nome or aluno.email.split("@")[0],
            "email": aluno.email,
            "telefone": telefone,
            "monitor_nome": monitor_nome,
        },
        "contrato": {
            "id": contrato.id,
            "valor_total": str(contrato.valor_total_negociado),
            "valor_total_formatado": moeda_brl(contrato.valor_total_negociado),
            "data_assinatura": contrato.data_assinatura.isoformat(),
            "data_assinatura_br": data_brasileira(contrato.data_assinatura),
            "observacoes": contrato.observacoes_gerais or "",
            "status": contrato.status,
        },
        "parcelas": parcelas,
    }


def contexto_dashboard_financeiro(usuario: Usuario, periodo: str, referencia: date | None = None) -> dict[str, object]:
    referencia = referencia or hoje_local()
    periodo_ref = calcular_periodo_financeiro(periodo, referencia)
    alunos = alunos_financeiros(usuario)
    overview = [resumo_aluno_financeiro(aluno, referencia) for aluno in alunos]
    overview_por_id = {item["id"]: item for item in overview}

    total_base = 0
    total_ativos = 0
    total_atrasados = 0
    total_inadimplentes = 0
    total_cancelados = 0
    valor_em_atraso = ZERO
    valor_inadimplente = ZERO
    volume_renegociado = ZERO
    faturamento_presumido = ZERO
    previsibilidade_proximo_periodo = ZERO
    farol = []

    for aluno in alunos:
        contrato = getattr(aluno, "contrato", None)
        if not contrato:
            continue

        total_base += 1
        parcelas = list(contrato.parcelas.filter(ativa=True))

        if contrato.status == ContratoStatus.CANCELADO:
            total_cancelados += 1
            continue

        total_ativos += 1
        tem_inadimplencia = False
        tem_atraso = False

        for parcela in parcelas:
            status = parcela.get_status(referencia)
            if status == ParcelaStatus.ATRASADO:
                tem_atraso = True
                valor_em_atraso += parcela.valor
            elif status == ParcelaStatus.INADIMPLENTE:
                tem_inadimplencia = True
                valor_inadimplente += parcela.valor

            if (
                parcela.ativa
                and not parcela.data_pagamento
                and status not in {ParcelaStatus.CANCELADO, ParcelaStatus.CANCELADA_RENEGOCIACAO}
                and (parcela.parcela_origem_id or parcela.ja_renegociada)
            ):
                volume_renegociado += parcela.valor

            if periodo_ref.data_inicio <= parcela.data_vencimento <= periodo_ref.data_fim:
                faturamento_presumido += parcela.valor

        if tem_inadimplencia:
            total_inadimplentes += 1
        elif tem_atraso:
            total_atrasados += 1

        if not tem_inadimplencia:
            for parcela in parcelas:
                if periodo_ref.proximo_inicio <= parcela.data_vencimento <= periodo_ref.proximo_fim:
                    previsibilidade_proximo_periodo += parcela.valor

        resumo = overview_por_id.get(aluno.id)
        if resumo and resumo["status_codigo"] in {ParcelaStatus.ATRASADO, ParcelaStatus.INADIMPLENTE, ParcelaStatus.CANCELADO}:
            farol.append(resumo)

    denominador = total_base or 1
    metrics = {
        "total_base": total_base,
        "total_ativos": total_ativos,
        "pct_atrasados": round((total_atrasados / denominador) * 100, 1),
        "pct_inadimplentes": round((total_inadimplentes / denominador) * 100, 1),
        "pct_cancelados": round((total_cancelados / denominador) * 100, 1),
        "valor_em_atraso": valor_em_atraso,
        "valor_inadimplente": valor_inadimplente,
        "volume_renegociado": volume_renegociado,
        "faturamento_presumido": faturamento_presumido,
        "previsibilidade_proximo_periodo": previsibilidade_proximo_periodo,
        "periodo_selecionado": periodo_ref.chave,
        "periodo_label": periodo_ref.label,
        "data_inicio_filtro": data_brasileira(periodo_ref.data_inicio),
        "data_fim_filtro": data_brasileira(periodo_ref.data_fim),
        "proximo_inicio_filtro": data_brasileira(periodo_ref.proximo_inicio),
        "proximo_fim_filtro": data_brasileira(periodo_ref.proximo_fim),
    }

    return {
        "alunos": overview,
        "farol": farol,
        "metrics": metrics,
        "periodo_opcoes": periodo_opcoes(),
    }
