from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.financeiro.models import Contrato
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
    entrada = [p for p in parcelas if p.tipo_parcela == "ENTRADA"]
    recorrentes = [p for p in parcelas if p.tipo_parcela == "RECORRENTE"]

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
        "valor_total_negociado": contrato.valor_total_negociado if contrato else 0,
        "data_assinatura": contrato.data_assinatura if contrato else None,
        "quantidade_entrada": len(entrada),
        "valor_entrada": entrada[0].valor if entrada else 0,
        "quantidade_recorrente": len(recorrentes),
        "valor_recorrente": recorrentes[0].valor if recorrentes else 0,
        "primeiro_vencimento": parcelas[0].data_vencimento if parcelas else None,
    }


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
                resultado = salvar_onboarding_aluno(
                    form=form,
                    usuario_logado=usuario,
                    landing_url=request.build_absolute_uri(reverse("usuarios:landing_page")),
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
                resultado = salvar_onboarding_aluno(
                    form=form,
                    usuario_logado=usuario,
                    aluno=aluno,
                    landing_url=request.build_absolute_uri(reverse("usuarios:landing_page")),
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
