from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from django.utils import timezone
from apps.financeiro.models import Parcela

def verificar_inadimplencia(usuario):
    """
    Função helper para verificar se um usuário possui parcelas INADIMPLENTES (8+ dias).
    """
    # Comercial, Admin, Monitor não devem ser bloqueados pelas próprias dívidas (se tivessem)
    if not usuario.is_aluno:
         return False
         
    try:
        contrato = usuario.contrato
        if contrato.status == 'CANCELADO':
            return True # Cancelado também é bloqueado da trilha.
            
        # Pega as parcelas
        for p in contrato.parcelas.all():
            if p.status_dinamico == 'INADIMPLENTE':
                return True
                
        return False
    except Exception as e:
        # Se não tem contrato, não tem dívida
        return False


def bloquear_inadimplente(view_func):
    """
    Decorator para bloquear o acesso do aluno às páginas da Trilha
    caso ele esteja inadimplente ou cancelado.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            # Reutiliza do apps.usuarios as logicas de Usuario customizado
            # Se for um superuser padrão do Django, deixa passar
            if getattr(request.user, 'is_superuser', False):
                return view_func(request, *args, **kwargs)
                
            if verificar_inadimplencia(request.user):
                messages.error(request, "Sua assinatura está suspensa por questões financeiras. Por favor, procure seu monitor ou o suporte.")
                # Assumindo que temos uma url para a página de perfil ou página inicial de aviso.
                return redirect('usuarios:perfil') # Substituir por uma rota segura se 'perfil' for bloqueada.
                
        return view_func(request, *args, **kwargs)
    return _wrapped_view
