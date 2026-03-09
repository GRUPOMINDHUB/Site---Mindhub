from __future__ import annotations

import secrets
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.financeiro.models import Contrato, ContratoStatus, OrigemParcela, Parcela, TipoParcela
from apps.trilha.models import Submissao
from apps.usuarios.models import RoleChoices, Usuario

from .models import (
    CanalOnboarding,
    DificuldadeDiagnostico,
    EnvioOnboarding,
    NichoEmpresa,
    NotificacaoInterna,
    PerfilEmpresarial,
    PropostaFinanceira,
    PropostaFinanceiraParcela,
    StatusEnvioOnboarding,
    StatusPropostaFinanceira,
    TipoNotificacao,
)


@dataclass
class CadastroResultado:
    aluno: Usuario
    senha_plana: str
    criado: bool


ZERO = Decimal("0.00")


def monitores_ativos():
    return Usuario.objects.filter(role=RoleChoices.MONITOR, ativo=True).order_by("nome", "email")


def usuarios_aprovadores_financeiros():
    aprovadores = Usuario.objects.filter(
        role=RoleChoices.ADMIN,
        ativo=True,
        pode_aprovar_financeiro=True,
    ).order_by("nome", "email")
    if aprovadores.exists():
        return aprovadores
    return Usuario.objects.filter(role=RoleChoices.ADMIN, ativo=True).order_by("nome", "email")


def alunos_visiveis_por_usuario(usuario: Usuario):
    queryset = (
        Usuario.objects.filter(role=RoleChoices.ALUNO, ativo=True)
        .select_related("monitor_responsavel", "perfil_empresarial", "contrato")
        .order_by("-data_cadastro")
    )
    if usuario.is_monitor:
        queryset = queryset.filter(monitor_responsavel=usuario)
    return queryset


def usuario_pode_visualizar_aluno(usuario: Usuario, aluno: Usuario) -> bool:
    if usuario.is_admin or usuario.is_comercial:
        return True
    return usuario.is_monitor and aluno.monitor_responsavel_id == usuario.id


def usuario_pode_editar_cadastro(usuario: Usuario) -> bool:
    return usuario.is_admin or usuario.is_comercial


def gerar_senha_temporaria() -> str:
    caracteres = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(caracteres) for _ in range(10))


def construir_mensagem_boas_vindas(
    aluno: Usuario,
    senha_plana: str,
    landing_url: str,
    link_pagamento_ou_pix: str = "",
) -> dict[str, str]:
    nome = aluno.nome or aluno.email.split("@")[0]
    link_pagamento_ou_pix = (link_pagamento_ou_pix or "").strip()
    bloco_pagamento = ""
    if link_pagamento_ou_pix:
        bloco_pagamento = f"\n\nPagamento (Pix/Link): {link_pagamento_ou_pix}"
    mensagem_base = (
        f"Ola, {nome}! Seu acesso ao Mindhub OS foi criado com sucesso.\n\n"
        f"Login: {aluno.email}\n"
        f"Senha: {senha_plana}\n"
        f"Acesso: {landing_url}\n\n"
        "Assim que entrar, fale com seu monitor para iniciar a configuracao da trilha."
        f"{bloco_pagamento}"
    )
    return {
        "email": (
            f"Ola, {nome}!\n\n"
            f"Seu acesso ao Mindhub OS esta pronto.\n\n"
            f"Login: {aluno.email}\n"
            f"Senha temporaria: {senha_plana}\n"
            f"Landing page: {landing_url}\n\n"
            f"Qualquer duvida, responda esta mensagem ou fale com seu monitor.{bloco_pagamento}"
        ),
        "whatsapp": mensagem_base,
    }


def registrar_envios_onboarding(aluno: Usuario, senha_plana: str, landing_url: str, link_pagamento_ou_pix: str = ""):
    mensagens = construir_mensagem_boas_vindas(aluno, senha_plana, landing_url, link_pagamento_ou_pix=link_pagamento_ou_pix)
    envios = []

    envio_email = EnvioOnboarding.objects.create(
        aluno=aluno,
        canal=CanalOnboarding.EMAIL,
        destinatario=aluno.email,
        mensagem=mensagens["email"],
    )
    try:
        if getattr(settings, "EMAIL_HOST", ""):
            send_mail(
                subject="Bem-vindo ao Mindhub OS",
                message=mensagens["email"],
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@mindhub.local"),
                recipient_list=[aluno.email],
                fail_silently=False,
            )
            envio_email.status = StatusEnvioOnboarding.ENVIADO
            envio_email.enviado_em = timezone.now()
            envio_email.save(update_fields=["status", "enviado_em"])
    except Exception as exc:
        envio_email.status = StatusEnvioOnboarding.ERRO
        envio_email.erro = str(exc)
        envio_email.save(update_fields=["status", "erro"])
    envios.append(envio_email)

    envios.append(
        EnvioOnboarding.objects.create(
            aluno=aluno,
            canal=CanalOnboarding.WHATSAPP,
            destinatario=aluno.telefone or "",
            mensagem=mensagens["whatsapp"],
        )
    )
    return envios


def sincronizar_parcela_asaas(parcela: Parcela):
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


def sincronizar_contrato_asaas(contrato: Contrato):
    if not contrato.asaas_customer_id:
        contrato.asaas_customer_id = f"ASAAS-CUST-{contrato.aluno_id}"
        contrato.save(update_fields=["asaas_customer_id"])
    for parcela in contrato.parcelas.filter(ativa=True):
        sincronizar_parcela_asaas(parcela)


def _construir_parcelas(
    contrato: Contrato,
    valor_entrada: Decimal,
    parcelas_planejadas: list[dict],
    data_contrato,
    origem: str,
    entrada_quitada: bool,
):
    parcelas = []

    if valor_entrada and valor_entrada > ZERO:
        parcelas.append(
            Parcela.objects.create(
                contrato=contrato,
                numero=0,
                valor=valor_entrada,
                data_vencimento=data_contrato,
                data_pagamento=data_contrato if entrada_quitada else None,
                observacoes="Entrada do contrato.",
                tipo_parcela=TipoParcela.ENTRADA,
                origem=origem,
            )
        )

    for numero, parcela_planejada in enumerate(parcelas_planejadas, start=1):
        parcelas.append(
            Parcela.objects.create(
                contrato=contrato,
                numero=numero,
                valor=parcela_planejada["valor"],
                data_vencimento=parcela_planejada["data_vencimento"],
                observacoes=parcela_planejada.get("observacoes", ""),
                link_pagamento_ou_pix=parcela_planejada.get("link_pagamento_ou_pix", ""),
                tipo_parcela=TipoParcela.RECORRENTE,
                origem=origem,
            )
        )

    return parcelas


def _valor_total_planejado(valor_entrada: Decimal, parcelas_planejadas: list[dict]) -> Decimal:
    return valor_entrada + sum((parcela["valor"] for parcela in parcelas_planejadas), ZERO)


def _resumo_parcelamento(parcelas):
    if not parcelas:
        return None

    entrada = sum((parcela.valor for parcela in parcelas if parcela.tipo_parcela == TipoParcela.ENTRADA), ZERO)
    recorrentes = [
        {
            "valor": parcela.valor,
            "data_vencimento": parcela.data_vencimento,
        }
        for parcela in parcelas
        if parcela.tipo_parcela == TipoParcela.RECORRENTE
    ]

    return {
        "valor_entrada": entrada,
        "parcelas": recorrentes,
    }


def _parcelamento_corresponde(parcelas, valor_entrada: Decimal, parcelas_planejadas: list[dict]) -> bool:
    resumo = _resumo_parcelamento(parcelas)
    if not resumo:
        return False

    if resumo["valor_entrada"] != valor_entrada:
        return False

    if len(resumo["parcelas"]) != len(parcelas_planejadas):
        return False

    for atual, planejada in zip(resumo["parcelas"], parcelas_planejadas):
        if atual["valor"] != planejada["valor"] or atual["data_vencimento"] != planejada["data_vencimento"]:
            return False

    return True


def _sincronizar_parcelamento_contrato(
    contrato: Contrato,
    valor_entrada: Decimal,
    parcelas_planejadas: list[dict],
    data_contrato,
    entrada_quitada: bool,
):
    parcelas_ativas = list(contrato.parcelas.filter(ativa=True).order_by("numero"))
    if not parcelas_ativas:
        _construir_parcelas(
            contrato=contrato,
            valor_entrada=valor_entrada,
            parcelas_planejadas=parcelas_planejadas,
            data_contrato=data_contrato,
            origem=OrigemParcela.CADASTRO,
            entrada_quitada=entrada_quitada,
        )
        sincronizar_contrato_asaas(contrato)
        return

    if _parcelamento_corresponde(parcelas_ativas, valor_entrada, parcelas_planejadas):
        parcela_entrada = contrato.parcelas.filter(ativa=True, tipo_parcela=TipoParcela.ENTRADA).first()
        if parcela_entrada and entrada_quitada and not parcela_entrada.data_pagamento:
            parcela_entrada.data_pagamento = data_contrato
            parcela_entrada.save(update_fields=["data_pagamento"])
        link_pagamento = (parcelas_planejadas[0].get("link_pagamento_ou_pix") or "").strip() if parcelas_planejadas else ""
        if link_pagamento:
            contrato.parcelas.filter(ativa=True, link_pagamento_ou_pix="").update(link_pagamento_ou_pix=link_pagamento)
        sincronizar_contrato_asaas(contrato)
        return

    if any(parcela.data_pagamento for parcela in parcelas_ativas):
        raise ValidationError(
            "Nao e possivel reescrever o parcelamento com pagamentos ja registrados. "
            "Use uma proposta de renegociacao para ajustar as proximas parcelas."
        )

    contrato.parcelas.filter(ativa=True).update(
        ativa=False,
        observacoes="[CADASTRO] Parcelamento substituido por atualizacao da ficha.",
    )
    _construir_parcelas(
        contrato=contrato,
        valor_entrada=valor_entrada,
        parcelas_planejadas=parcelas_planejadas,
        data_contrato=data_contrato,
        origem=OrigemParcela.CADASTRO,
        entrada_quitada=entrada_quitada,
    )
    sincronizar_contrato_asaas(contrato)


def criar_notificacao_onboarding(aluno: Usuario):
    monitor = aluno.monitor_responsavel
    if not monitor:
        return None

    return NotificacaoInterna.objects.create(
        destinatario=monitor,
        tipo=TipoNotificacao.ONBOARDING,
        titulo=f"Novo Aluno Cadastrado: {aluno.nome or aluno.email}",
        mensagem=f"Novo Aluno Cadastrado: {aluno.nome or aluno.email}. Clique aqui para configurar a Trilha.",
        url_destino=f"/gerenciar/{aluno.id}/",
        aluno=aluno,
    )


def criar_notificacao_proposta(proposta: PropostaFinanceira):
    notificacoes = []
    for aprovador in usuarios_aprovadores_financeiros():
        notificacoes.append(
            NotificacaoInterna.objects.create(
                destinatario=aprovador,
                tipo=TipoNotificacao.PROPOSTA_FINANCEIRA,
                titulo=f"Nova proposta financeira para {proposta.aluno.nome or proposta.aluno.email}",
                mensagem=(
                    f"O monitor {proposta.criada_por.nome or proposta.criada_por.email} "
                    f"solicitou aprovacao de renegociacao para {proposta.aluno.nome or proposta.aluno.email}."
                ),
                url_destino=f"/comercial/cadastros/{proposta.aluno_id}/",
                aluno=proposta.aluno,
            )
        )
    return notificacoes


@transaction.atomic
def salvar_onboarding_aluno(
    form,
    usuario_logado: Usuario,
    landing_url: str,
    parcelas_planejadas: list[dict],
    aluno: Usuario | None = None,
) -> CadastroResultado:
    dados = form.cleaned_data
    criando = aluno is None
    senha_informada = dados.get("senha")
    senha_plana = senha_informada or (gerar_senha_temporaria() if criando else "")
    valor_entrada = dados.get("valor_entrada") or ZERO
    valor_total_negociado = _valor_total_planejado(valor_entrada, parcelas_planejadas)

    if criando:
        aluno = Usuario(role=RoleChoices.ALUNO, ativo=True)

    aluno.nome = dados["nome"]
    aluno.email = dados["email"].strip().lower()
    aluno.telefone = dados.get("telefone", "")
    aluno.monitor_responsavel = dados["monitor_responsavel"]
    aluno.role = RoleChoices.ALUNO
    if criando or senha_informada:
        aluno.senha = make_password(senha_plana)
    aluno.save()

    perfil, _ = PerfilEmpresarial.objects.get_or_create(aluno=aluno)
    perfil.nome_empresa = dados["nome_empresa"]
    perfil.telefone_empresa = dados.get("telefone_empresa", "")
    perfil.cnpj = dados.get("cnpj", "")
    perfil.endereco = dados.get("endereco", "")
    perfil.nicho = dados.get("nicho", NichoEmpresa.OUTRO)
    perfil.nome_representante = dados.get("nome_representante", "")
    perfil.cpf_representante = dados.get("cpf_representante", "")
    perfil.dificuldades = dados.get("dificuldades", [])
    perfil.observacoes = dados.get("observacoes", "")
    perfil.monitor_responsavel_snapshot = dados["monitor_responsavel"]
    perfil.save()

    contrato, _ = Contrato.objects.get_or_create(
        aluno=aluno,
        defaults={
            "valor_total_negociado": valor_total_negociado,
            "data_assinatura": dados["data_contrato"],
            "metodo_pagamento": dados["metodo_pagamento"],
            "status": ContratoStatus.ATIVO,
            "criado_por": usuario_logado,
        },
    )
    contrato.valor_total_negociado = valor_total_negociado
    contrato.data_assinatura = dados["data_contrato"]
    contrato.metodo_pagamento = dados["metodo_pagamento"]
    contrato.observacoes_gerais = dados.get("observacoes", "")
    contrato.status = ContratoStatus.ATIVO
    contrato.criado_por = contrato.criado_por or usuario_logado
    if dados.get("contrato_assinado"):
        contrato.contrato_assinado = dados["contrato_assinado"]
    if dados.get("comprovante_entrada"):
        contrato.comprovante_entrada = dados["comprovante_entrada"]
    contrato.save()

    _sincronizar_parcelamento_contrato(
        contrato=contrato,
        valor_entrada=valor_entrada,
        parcelas_planejadas=parcelas_planejadas,
        data_contrato=dados["data_contrato"],
        entrada_quitada=bool(contrato.comprovante_entrada),
    )

    if criando:
        link_pagamento = (parcelas_planejadas[0].get("link_pagamento_ou_pix") or "").strip() if parcelas_planejadas else ""
        registrar_envios_onboarding(aluno, senha_plana, landing_url, link_pagamento_ou_pix=link_pagamento)
        criar_notificacao_onboarding(aluno)

    return CadastroResultado(aluno=aluno, senha_plana=senha_plana, criado=criando)


@transaction.atomic
def criar_proposta_financeira(aluno: Usuario, contrato: Contrato, monitor: Usuario, dados: dict) -> PropostaFinanceira:
    proposta = PropostaFinanceira.objects.create(
        aluno=aluno,
        contrato=contrato,
        criada_por=monitor,
        motivo=dados["motivo"],
        observacao_monitor=dados.get("observacao_monitor", ""),
    )

    data_cursor = dados["primeiro_vencimento"]
    for numero in range(1, dados["quantidade_parcelas"] + 1):
        PropostaFinanceiraParcela.objects.create(
            proposta=proposta,
            numero=numero,
            valor=dados["valor_parcela"],
            data_vencimento=data_cursor,
            observacoes=dados.get("observacao_monitor", ""),
        )
        data_cursor = data_cursor + relativedelta(months=1)

    criar_notificacao_proposta(proposta)
    return proposta


@transaction.atomic
def aprovar_proposta_financeira(proposta: PropostaFinanceira, aprovador: Usuario, observacao_admin: str = ""):
    if not aprovador.is_admin_master:
        raise ValidationError("Usuario sem permissao para aprovar financeiro.")
    if proposta.status != StatusPropostaFinanceira.PENDENTE:
        raise ValidationError("A proposta nao esta pendente.")

    contrato = proposta.contrato
    contrato.parcelas.filter(ativa=True, data_pagamento__isnull=True).update(
        ativa=False,
        ja_renegociada=True,
        observacoes="[RENEGOCIACAO] Parcela substituida por proposta aprovada.",
    )

    ultimo_numero = contrato.parcelas.order_by("-numero").values_list("numero", flat=True).first() or 0
    for parcela_proposta in proposta.parcelas_propostas.all().order_by("numero"):
        nova_parcela = Parcela.objects.create(
            contrato=contrato,
            numero=ultimo_numero + parcela_proposta.numero,
            valor=parcela_proposta.valor,
            data_vencimento=parcela_proposta.data_vencimento,
            observacoes=f"[RENEGOCIACAO] {parcela_proposta.observacoes}".strip(),
            origem=OrigemParcela.RENEGOCIACAO,
            tipo_parcela=TipoParcela.RECORRENTE,
        )
        sincronizar_parcela_asaas(nova_parcela)

    proposta.status = StatusPropostaFinanceira.APROVADA
    proposta.observacao_admin = observacao_admin
    proposta.aprovada_por = aprovador
    proposta.aprovada_em = timezone.now()
    proposta.save(update_fields=["status", "observacao_admin", "aprovada_por", "aprovada_em"])


@transaction.atomic
def rejeitar_proposta_financeira(proposta: PropostaFinanceira, aprovador: Usuario, observacao_admin: str = ""):
    if not aprovador.is_admin_master:
        raise ValidationError("Usuario sem permissao para aprovar financeiro.")
    if proposta.status != StatusPropostaFinanceira.PENDENTE:
        raise ValidationError("A proposta nao esta pendente.")

    proposta.status = StatusPropostaFinanceira.REJEITADA
    proposta.observacao_admin = observacao_admin
    proposta.aprovada_por = aprovador
    proposta.aprovada_em = timezone.now()
    proposta.save(update_fields=["status", "observacao_admin", "aprovada_por", "aprovada_em"])


def notificacoes_internas(usuario: Usuario):
    return NotificacaoInterna.objects.filter(destinatario=usuario).order_by("lida", "-criada_em")


def submissoes_pendentes_para_usuario(usuario: Usuario):
    queryset = Submissao.objects.filter(aprovado__isnull=True).select_related(
        "progresso__aluno",
        "progresso__step__mundo",
    ).order_by("data_envio")
    if usuario.is_monitor:
        queryset = queryset.filter(progresso__aluno__monitor_responsavel=usuario)
    return queryset


def propostas_pendentes_para_usuario(usuario: Usuario):
    queryset = PropostaFinanceira.objects.filter(status=StatusPropostaFinanceira.PENDENTE).select_related(
        "aluno",
        "criada_por",
        "contrato",
    ).prefetch_related("parcelas_propostas")
    if usuario.is_admin_master:
        return queryset
    return queryset.none()


def total_notificacoes(usuario: Usuario) -> int:
    total = notificacoes_internas(usuario).filter(lida=False).count()
    if usuario.pode_validar:
        total += submissoes_pendentes_para_usuario(usuario).count()
    if usuario.is_admin_master:
        total += propostas_pendentes_para_usuario(usuario).count()
    return total


def resumo_cadastros(usuario: Usuario):
    alunos = alunos_visiveis_por_usuario(usuario)
    total = alunos.count()
    com_perfil = PerfilEmpresarial.objects.filter(aluno__in=alunos).count()
    com_contrato = Contrato.objects.filter(aluno__in=alunos).count()
    onboarding_pendente = NotificacaoInterna.objects.filter(
        destinatario=usuario,
        tipo=TipoNotificacao.ONBOARDING,
        lida=False,
    ).count()
    return {
        "total_alunos": total,
        "com_perfil": com_perfil,
        "com_contrato": com_contrato,
        "onboarding_pendente": onboarding_pendente,
    }


def escolhas_dificuldades():
    return list(DificuldadeDiagnostico.choices)


def escolhas_nichos():
    return list(NichoEmpresa.choices)
