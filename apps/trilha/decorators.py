"""
Decorators do app Trilha - Mindhub OS.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

from apps.usuarios.models import Usuario, RoleChoices


def get_usuario_logado(request):
    """Retorna o usuário logado ou None."""
    email = request.session.get('usuario')
    if not email:
        return None
    try:
        return Usuario.objects.get(email=email)
    except Usuario.DoesNotExist:
        return None


def aluno_required(view_func):
    """
    Decorator que garante que apenas usuários com role == 'ALUNO' acessem a view.
    Redireciona para login se não autenticado ou para a página correta se outro role.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        usuario = get_usuario_logado(request)
        
        if not usuario:
            messages.error(request, 'Você precisa estar logado para acessar esta página.')
            return redirect('usuarios:index')
        
        if not usuario.is_aluno:
            messages.error(request, 'Esta área é exclusiva para alunos.')
            if usuario.is_admin or usuario.is_monitor:
                return redirect('trilha:monitor_dashboard')
            return redirect('usuarios:index')
        
        # Adiciona o usuário ao request para uso na view
        request.usuario = usuario
        return view_func(request, *args, **kwargs)
    
    return wrapper
