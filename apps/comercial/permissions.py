from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from apps.usuarios.utils import get_usuario_logado

from .services import usuario_pode_editar_cadastro


def cadastro_access_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        usuario = get_usuario_logado(request)
        if not usuario or not (usuario.is_admin or usuario.is_monitor or usuario.is_comercial):
            messages.error(request, "Acesso negado.")
            return redirect("usuarios:index")
        request.usuario = usuario
        return view_func(request, *args, **kwargs)

    return wrapper


def cadastro_edit_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        usuario = get_usuario_logado(request)
        if not usuario or not usuario_pode_editar_cadastro(usuario):
            messages.error(request, "Somente ADM ou Comercial podem editar esta ficha.")
            return redirect("comercial:cadastros")
        request.usuario = usuario
        return view_func(request, *args, **kwargs)

    return wrapper


def admin_master_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        usuario = get_usuario_logado(request)
        if not usuario or not usuario.is_admin_master:
            messages.error(request, "Somente o ADM Master pode aprovar esta acao.")
            return redirect("trilha:monitor_notificacoes")
        request.usuario = usuario
        return view_func(request, *args, **kwargs)

    return wrapper
