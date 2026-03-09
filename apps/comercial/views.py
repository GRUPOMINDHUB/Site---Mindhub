from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.financeiro.models import Contrato, MetodoPagamentoContrato, TipoParcela
from apps.usuarios.models import RoleChoices, Usuario

from .forms import CadastroAlunoOnboardingForm, ParecerPropostaFinanceiraForm, PropostaFinanceiraForm
from .models import NotificacaoInterna, PropostaFinanceira
from .permissions import admin_master_required, cadastro_access_required, cadastro_edit_required
from .services import (
    alunos_visiveis_por_usuario,
    criar_proposta_financeira,
    rejeitar_proposta_financeira,
    resumo_cadastros,
    salvar_onboarding_aluno,
    total_notificacoes,
    usuario_pode_editar_cadastro,
    usuario_pode_visualizar_aluno,
    aprovar_proposta_financeira,
)


def _initial_cadastro(aluno: Usuario):
    perfil = getattr(aluno, "perfil_empresarial", None)
    contrato = getattr(aluno, "contrato", None)
    parcelas = list(contrato.parcelas.filter(ativa=True).order_by("numero")) if contrato else []
    entrada = [p for p in parcelas if p.tipo_parcela == TipoParcela.ENTRADA]
    recorrentes = [p for p in parcelas if p.tipo_parcela == TipoParcela.RECORRENTE]
    valor_entrada = sum((parcela.valor for parcela in entrada), Decimal("0.00"))
    modalidade = "PARCELADO" if len(recorrentes) > 1 else "AVISTA"
    valor_total_avista = recorrentes[0].valor if len(recorrentes) == 1 else Decimal("0.00")
    link_pagamento = (
        (recorrentes[0].link_pagamento_ou_pix if recorrentes else "")
        or (entrada[0].link_pagamento_ou_pix if entrada else "")
        or ""
    )

    return {
        "nome": aluno.nome,
        "email": aluno.email,
        "telefone": aluno.telefone,
        "monitor_responsavel": aluno.monitor_responsavel_id,
        "nome_empresa": perfil.nome_empresa if perfil else "",
        "telefone_empresa": perfil.telefone_empresa if perfil else "",
        "cnpj": perfil.cnpj if perfil else "",
        "endereco": perfil.endereco if perfil else "",
        "nicho": perfil.nicho if perfil else "OUTRO",
        "nome_representante": perfil.nome_representante if perfil else "",
        "cpf_representante": perfil.cpf_representante if perfil else "",
        "dificuldades": perfil.dificuldades if perfil else [],
        "observacoes": perfil.observacoes if perfil else (contrato.observacoes_gerais if contrato else ""),
        "valor_entrada": valor_entrada,
        "data_contrato": contrato.data_assinatura if contrato else None,
        "modalidade_pagamento": modalidade,
        "valor_total_avista": valor_total_avista,
        "quantidade_parcelas": len(recorrentes) if recorrentes else 1,
        "metodo_pagamento": contrato.metodo_pagamento if contrato else MetodoPagamentoContrato.PIX,
        "link_pagamento_ou_pix": link_pagamento,
    }


def _parcelas_planejadas_context(request, contrato: Contrato | None):
    if request.method == "POST":
        valores = request.POST.getlist("parcela_valor[]")
        vencimentos = request.POST.getlist("parcela_vencimento[]")
        parcelas = []
        quantidade_linhas = max(len(valores), len(vencimentos))
        for indice in range(quantidade_linhas):
            valor = (valores[indice] if indice < len(valores) else "")
            vencimento = (vencimentos[indice] if indice < len(vencimentos) else "")
            valor = (valor or "").strip()
            vencimento = (vencimento or "").strip()
            if not valor and not vencimento:
                continue
            parcelas.append(
                {
                    "numero": indice,
                    "valor": valor,
                    "data_vencimento": vencimento,
                }
            )
        return parcelas

    if not contrato:
        return []

    parcelas = []
    for indice, parcela in enumerate(
        contrato.parcelas.filter(ativa=True, tipo_parcela=TipoParcela.RECORRENTE).order_by("numero"),
        start=1,
    ):
        parcelas.append(
            {
                "numero": indice,
                "valor": f"{parcela.valor:.2f}",
                "data_vencimento": parcela.data_vencimento.isoformat(),
            }
        )
    return parcelas


def _modalidade_financeira(form: CadastroAlunoOnboardingForm) -> str:
    if form.is_bound:
        return form.data.get("modalidade_pagamento") or "PARCELADO"
    return form.initial.get("modalidade_pagamento") or "PARCELADO"


def _capturar_parcelas_planejadas(request, form: CadastroAlunoOnboardingForm) -> list[dict]:
    dados = form.cleaned_data
    modalidade = dados["modalidade_pagamento"]
    link_pagamento = (dados.get("link_pagamento_ou_pix") or "").strip()

    if modalidade == "AVISTA":
        return [
            {
                "valor": dados["valor_total_avista"],
                "data_vencimento": dados["data_contrato"],
                "observacoes": "Pagamento a vista.",
                "link_pagamento_ou_pix": link_pagamento,
            }
        ]

    valores = request.POST.getlist("parcela_valor[]")
    vencimentos = request.POST.getlist("parcela_vencimento[]")
    if len(valores) != len(vencimentos):
        raise ValidationError("As parcelas enviadas estao inconsistentes.")

    parcelas = []
    for indice, (valor_bruto, vencimento_bruto) in enumerate(zip(valores, vencimentos), start=1):
        valor_bruto = (valor_bruto or "").strip()
        vencimento_bruto = (vencimento_bruto or "").strip()

        if not valor_bruto and not vencimento_bruto:
            continue
        if not valor_bruto or not vencimento_bruto:
            raise ValidationError(f"Preencha valor e vencimento da parcela {indice}.")

        try:
            valor = Decimal(valor_bruto)
        except InvalidOperation as exc:
            raise ValidationError(f"Valor invalido na parcela {indice}.") from exc

        data_vencimento = parse_date(vencimento_bruto)
        if not data_vencimento:
            raise ValidationError(f"Data invalida na parcela {indice}.")
        if valor <= 0:
            raise ValidationError(f"O valor da parcela {indice} deve ser maior que zero.")

        parcelas.append(
            {
                "valor": valor.quantize(Decimal("0.01")),
                "data_vencimento": data_vencimento,
                "observacoes": f"Parcela {indice} criada na central comercial.",
                "link_pagamento_ou_pix": link_pagamento,
            }
        )

    quantidade_parcelas = dados.get("quantidade_parcelas") or 0
    if len(parcelas) != quantidade_parcelas:
        raise ValidationError("A quantidade de parcelas nao corresponde as linhas preenchidas.")

    return parcelas


@cadastro_access_required
def cadastros(request):
    usuario = request.usuario
    alunos = alunos_visiveis_por_usuario(usuario)
    return render(
        request,
        "comercial/cadastros_list.html",
        {
            "usuario": usuario,
            "cadastros": alunos,
            "resumo": resumo_cadastros(usuario),
            "page_title": "Central de Cadastros",
        },
    )


@cadastro_edit_required
def cadastro_novo(request):
    usuario = request.usuario
    if request.method == "POST":
        form = CadastroAlunoOnboardingForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                parcelas_planejadas = _capturar_parcelas_planejadas(request, form)
                resultado = salvar_onboarding_aluno(
                    form=form,
                    usuario_logado=usuario,
                    landing_url=request.build_absolute_uri(reverse("usuarios:landing_page")),
                    parcelas_planejadas=parcelas_planejadas,
                )
            except ValidationError as exc:
                for erro in exc.messages:
                    form.add_error(None, erro)
            else:
                messages.success(request, "Aluno cadastrado com sucesso.")
                messages.info(request, f"Senha de acesso: {resultado.senha_plana}")
                return redirect("comercial:cadastro_detalhe", aluno_id=resultado.aluno.id)
    else:
        form = CadastroAlunoOnboardingForm()

    return render(
        request,
        "comercial/cadastro_form.html",
        {
            "usuario": usuario,
            "form": form,
            "aluno": None,
            "page_title": "Novo Cadastro",
            "modo": "novo",
            "readonly": False,
            "proposal_form": None,
            "propostas": [],
            "parcelas": [],
            "parcelas_planejadas": _parcelas_planejadas_context(request, None),
            "modalidade_financeira": _modalidade_financeira(form),
        },
    )


@cadastro_access_required
def cadastro_detalhe(request, aluno_id):
    usuario = request.usuario
    aluno = get_object_or_404(
        Usuario.objects.select_related("monitor_responsavel", "perfil_empresarial", "contrato"),
        id=aluno_id,
        role=RoleChoices.ALUNO,
    )

    if not usuario_pode_visualizar_aluno(usuario, aluno):
        messages.error(request, "Acesso negado a esta ficha.")
        return redirect("comercial:cadastros")

    readonly = not usuario_pode_editar_cadastro(usuario)
    contrato = getattr(aluno, "contrato", None)
    parcelas = contrato.parcelas.order_by("numero") if contrato else []

    if request.method == "POST" and not readonly:
        form = CadastroAlunoOnboardingForm(
            request.POST,
            request.FILES,
            allow_password_optional=True,
        )
        if form.is_valid():
            try:
                parcelas_planejadas = _capturar_parcelas_planejadas(request, form)
                resultado = salvar_onboarding_aluno(
                    form=form,
                    usuario_logado=usuario,
                    aluno=aluno,
                    landing_url=request.build_absolute_uri(reverse("usuarios:landing_page")),
                    parcelas_planejadas=parcelas_planejadas,
                )
            except ValidationError as exc:
                for erro in exc.messages:
                    form.add_error(None, erro)
            else:
                messages.success(request, "Ficha atualizada com sucesso.")
                if form.cleaned_data.get("senha"):
                    messages.info(request, f"Nova senha definida: {resultado.senha_plana}")
                return redirect("comercial:cadastro_detalhe", aluno_id=aluno.id)
    else:
        form = CadastroAlunoOnboardingForm(
            initial=_initial_cadastro(aluno),
            allow_password_optional=True,
        )

    if readonly:
        for field in form.fields.values():
            field.widget.attrs["disabled"] = "disabled"

    proposal_form = PropostaFinanceiraForm() if usuario.is_monitor and contrato else None
    propostas = aluno.propostas_financeiras.select_related("criada_por", "aprovada_por").prefetch_related("parcelas_propostas")

    return render(
        request,
        "comercial/cadastro_form.html",
        {
            "usuario": usuario,
            "form": form,
            "aluno": aluno,
            "page_title": f"Ficha de {aluno.nome or aluno.email}",
            "modo": "detalhe",
            "readonly": readonly,
            "proposal_form": proposal_form,
            "propostas": propostas,
            "parcelas": parcelas,
            "contrato": contrato,
            "parcelas_planejadas": _parcelas_planejadas_context(request, contrato),
            "modalidade_financeira": _modalidade_financeira(form),
        },
    )


@cadastro_access_required
@require_POST
def criar_proposta(request, aluno_id):
    usuario = request.usuario
    aluno = get_object_or_404(Usuario, id=aluno_id, role=RoleChoices.ALUNO)
    if not usuario.is_monitor or not usuario_pode_visualizar_aluno(usuario, aluno):
        messages.error(request, "Somente o monitor responsavel pode propor renegociacao.")
        return redirect("comercial:cadastro_detalhe", aluno_id=aluno_id)

    contrato = get_object_or_404(Contrato, aluno=aluno)
    form = PropostaFinanceiraForm(request.POST)
    if form.is_valid():
        criar_proposta_financeira(aluno, contrato, usuario, form.cleaned_data)
        messages.success(request, "Proposta financeira enviada para aprovacao.")
    else:
        messages.error(request, "Nao foi possivel criar a proposta. Revise os campos.")
    return redirect("comercial:cadastro_detalhe", aluno_id=aluno_id)


@admin_master_required
@require_POST
def aprovar_proposta(request, proposta_id):
    proposta = get_object_or_404(PropostaFinanceira.objects.prefetch_related("parcelas_propostas"), id=proposta_id)
    form = ParecerPropostaFinanceiraForm(request.POST)
    if form.is_valid():
        aprovar_proposta_financeira(proposta, request.usuario, form.cleaned_data.get("observacao_admin", ""))
        messages.success(request, "Proposta financeira aprovada.")
    else:
        messages.error(request, "Parecer invalido.")
    return redirect("trilha:monitor_notificacoes")


@admin_master_required
@require_POST
def rejeitar_proposta(request, proposta_id):
    proposta = get_object_or_404(PropostaFinanceira, id=proposta_id)
    form = ParecerPropostaFinanceiraForm(request.POST)
    if form.is_valid():
        rejeitar_proposta_financeira(proposta, request.usuario, form.cleaned_data.get("observacao_admin", ""))
        messages.success(request, "Proposta financeira rejeitada.")
    else:
        messages.error(request, "Parecer invalido.")
    return redirect("trilha:monitor_notificacoes")


@cadastro_access_required
@require_POST
def marcar_notificacao_lida(request, notificacao_id):
    notificacao = get_object_or_404(NotificacaoInterna, id=notificacao_id, destinatario=request.usuario)
    notificacao.marcar_como_lida()
    destino = notificacao.url_destino or reverse("trilha:monitor_notificacoes")
    return redirect(destino)


@cadastro_access_required
def api_total_notificacoes(request):
    return JsonResponse({"total": total_notificacoes(request.usuario)})
