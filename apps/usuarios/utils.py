"""
Utilitários para o app de Usuários.
"""
from .models import Usuario

def get_usuario_logado(request):
    """
    Retorna o usuário logado na sessão ou None.
    Substitui lógica repetida em views.
    """
    email = request.session.get('usuario')
    if not email:
        return None
    try:
        return Usuario.objects.get(email=email)
    except Usuario.DoesNotExist:
        return None
