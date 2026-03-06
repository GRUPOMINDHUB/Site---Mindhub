from functools import wraps

from django.shortcuts import redirect

from apps.usuarios.utils import get_usuario_logado

from .services import possui_bloqueio_trilha, sincronizar_nota_saude_financeira


def verificar_inadimplencia(usuario) -> bool:
    if not usuario:
        return False
    sincronizar_nota_saude_financeira(usuario)
    return possui_bloqueio_trilha(usuario)


def bloquear_inadimplente(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        usuario = get_usuario_logado(request)
        if usuario and verificar_inadimplencia(usuario):
            return redirect("financeiro:aviso_inadimplencia")
        return view_func(request, *args, **kwargs)

    return _wrapped_view
