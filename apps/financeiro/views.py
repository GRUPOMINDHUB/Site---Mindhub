from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.usuarios.models import RoleChoices, Usuario
from apps.usuarios.utils import get_usuario_logado

from .forms import ParcelaAtualizacaoForm
from .models import Contrato, Parcela
from .services import (
    contexto_dashboard_financeiro,
    ficha_aluno_financeira,
    possui_bloqueio_trilha,
    resumo_aluno_financeiro,
)


def verificar_acesso_financeiro(request):
    usuario = get_usuario_logado(request)
    if usuario and usuario.role in {RoleChoices.ADMIN, RoleChoices.MONITOR}:
        return usuario
    return None


def dashboard_financeiro(request):
    usuario = verificar_acesso_financeiro(request)
    if not usuario:
        messages.error(request, "Acesso restrito ao modulo financeiro.")
        return redirect("usuarios:index")

    periodo = request.GET.get("periodo", "mensal")
    contexto = contexto_dashboard_financeiro(usuario, periodo)
    contexto.update(
        {
            "usuario": usuario,
            "page_title": "Central Financeira",
        }
    )
    return render(request, "financeiro/dashboard.html", contexto)


def aviso_inadimplencia(request):
    usuario = get_usuario_logado(request)
    if not usuario or not usuario.is_aluno:
        return redirect("usuarios:index")

    if not possui_bloqueio_trilha(usuario):
        return redirect("trilha:home_trilha")

    resumo = resumo_aluno_financeiro(usuario)
    contrato = getattr(usuario, "contrato", None)
    parcela_critica = contrato.parcela_referencia() if contrato else None
    monitor = usuario.monitor_responsavel

    return render(
        request,
        "financeiro/aviso_inadimplencia.html",
        {
            "usuario": usuario,
            "monitor": monitor,
            "resumo": resumo,
            "parcela_critica": parcela_critica,
            "page_title": "Assinatura Suspensa",
        },
    )


def api_ficha_aluno(request, aluno_id):
    usuario = verificar_acesso_financeiro(request)
    if not usuario:
        return JsonResponse({"error": "Acesso negado."}, status=403)

    aluno = get_object_or_404(Usuario, id=aluno_id, role=RoleChoices.ALUNO)
    if usuario.is_monitor and aluno.monitor_responsavel_id != usuario.id:
        return JsonResponse({"error": "Acesso negado."}, status=403)

    try:
        payload = ficha_aluno_financeira(aluno)
    except (AttributeError, Contrato.DoesNotExist):
        return JsonResponse({"error": "Contrato nao encontrado para este aluno."}, status=404)

    return JsonResponse(payload)


@require_POST
def api_atualizar_parcela(request, parcela_id):
    usuario = verificar_acesso_financeiro(request)
    if not usuario:
        return JsonResponse({"success": False, "error": "Acesso negado."}, status=403)

    parcela = get_object_or_404(Parcela.objects.select_related("contrato__aluno__monitor_responsavel"), id=parcela_id)
    if usuario.is_monitor and parcela.contrato.aluno.monitor_responsavel_id != usuario.id:
        return JsonResponse({"success": False, "error": "Acesso negado."}, status=403)

    form = ParcelaAtualizacaoForm(request.POST, request.FILES, instance=parcela)
    if not form.is_valid():
        return JsonResponse(
            {
                "success": False,
                "error": "Dados invalidos.",
                "errors": form.errors,
            },
            status=400,
        )

    parcela = form.save()
    resumo = resumo_aluno_financeiro(parcela.contrato.aluno)

    return JsonResponse(
        {
            "success": True,
            "status_atualizado": parcela.status_dinamico,
            "resumo_aluno": resumo,
        }
    )
