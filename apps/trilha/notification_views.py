from django.contrib import messages
from django.shortcuts import redirect, render

from apps.comercial.forms import ParecerPropostaFinanceiraForm
from apps.comercial.services import notificacoes_internas, propostas_pendentes_para_usuario, submissoes_pendentes_para_usuario
from apps.usuarios.models import Usuario
from apps.usuarios.utils import get_usuario_logado


def verificar_acesso_monitor(request):
    usuario = get_usuario_logado(request)
    if usuario and usuario.pode_validar:
        return usuario
    return None


def bloquear_comercial(view_func):
    def wrapper(request, *args, **kwargs):
        email = request.session.get("usuario")
        if email:
            try:
                usuario = Usuario.objects.get(email=email)
                if usuario.is_comercial:
                    messages.error(request, "Acesso restrito.")
                    return redirect("usuarios:gerenciar_acessos")
            except Usuario.DoesNotExist:
                pass
        return view_func(request, *args, **kwargs)

    return wrapper


@bloquear_comercial
def monitor_notificacoes(request):
    usuario = verificar_acesso_monitor(request)
    if not usuario:
        return redirect("/")

    return render(
        request,
        "trilha/monitor_notificacoes.html",
        {
            "usuario": usuario,
            "notificacoes_internas": notificacoes_internas(usuario)[:20],
            "submissoes_pendentes": submissoes_pendentes_para_usuario(usuario)[:20],
            "propostas_pendentes": propostas_pendentes_para_usuario(usuario)[:20],
            "parecer_form": ParecerPropostaFinanceiraForm(),
            "page_title": "Notificacoes",
        },
    )
