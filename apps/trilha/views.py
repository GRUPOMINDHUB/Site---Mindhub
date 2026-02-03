"""
Views do app Trilha - Mindhub OS.
"""
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden

from apps.usuarios.models import Usuario, RoleChoices
from .models import Mundo, Step, ProgressoAluno, StatusProgresso
from .decorators import aluno_required


def verificar_acesso_monitor(request):
    """Verifica se o usuário tem acesso de monitor (ADMIN ou MONITOR)."""
    email = request.session.get('usuario')
    if not email:
        return None
    
    try:
        usuario = Usuario.objects.get(email=email)
        if usuario.pode_validar:
            return usuario
    except Usuario.DoesNotExist:
        pass
    
    return None


def bloquear_comercial(view_func):
    """Decorator para bloquear acesso de usuários COMERCIAL."""
    def wrapper(request, *args, **kwargs):
        email = request.session.get('usuario')
        if email:
            try:
                usuario = Usuario.objects.get(email=email)
                if usuario.is_comercial:
                    from django.contrib import messages
                    messages.error(request, 'Acesso Restrito: Você não tem permissão para acessar esta página.')
                    return redirect('usuarios:gerenciar_acessos')
            except Usuario.DoesNotExist:
                pass
        return view_func(request, *args, **kwargs)
    return wrapper


@bloquear_comercial
def monitor_dashboard(request):
    """
    Dashboard principal do Monitor.
    Mostra estatísticas e acesso rápido às funcionalidades.
    """
    usuario = verificar_acesso_monitor(request)
    if not usuario:
        return redirect('/')
    
    return render(request, 'trilha/monitor_dashboard.html', {
        'usuario': usuario,
        'page_title': 'Dashboard do Monitor'
    })


@bloquear_comercial
def monitor_graph(request):
    """
    Graph View - Visualização em grafo dos alunos.
    Usa D3.js para renderizar os nós.
    """
    usuario = verificar_acesso_monitor(request)
    if not usuario:
        return redirect('/')
    
    return render(request, 'trilha/monitor_graph.html', {
        'usuario': usuario,
        'page_title': 'Visão Geral - Graph View'
    })


@bloquear_comercial
def monitor_validar(request):
    """
    Página de validação de submissões.
    Lista submissões pendentes para aprovar/reprovar.
    """
    usuario = verificar_acesso_monitor(request)
    if not usuario:
        return redirect('/')
    
    return render(request, 'trilha/monitor_validar.html', {
        'usuario': usuario,
        'page_title': 'Validar Submissões'
    })


# ========================================
# ÁREA DO ALUNO
# ========================================

@aluno_required
def aluno_mapa(request):
    """
    Mapa da Jornada Gamificada do Aluno.
    Exibe o progresso nos Mundos e Steps estilo Mario World.
    """
    aluno = request.usuario
    
    # Busca mundos do próprio aluno (trilha individual)
    mundos = Mundo.objects.filter(aluno=aluno, ativo=True).prefetch_related('steps').order_by('numero')
    
    # Se aluno não tem mundos próprios, verifica se tem trilha base
    if not mundos.exists():
        # Não inicializa mais automaticamente - o Monitor precisa configurar
        pass
    else:
        # Inicializa progresso do aluno se for a primeira vez
        primeiro_step = Step.objects.filter(
            mundo__aluno=aluno, 
            ativo=True
        ).order_by('mundo__numero', 'ordem').first()
        
        if primeiro_step:
            progresso, criado = ProgressoAluno.objects.get_or_create(
                aluno=aluno,
                step=primeiro_step,
                defaults={'status': StatusProgresso.EM_ANDAMENTO}
            )
            if criado:
                progresso.iniciar()
    
    return render(request, 'trilha/mapa_aluno.html', {
        'usuario': aluno,
        'mundos': mundos,
        'page_title': 'Minha Jornada - Gestor de Sucesso'
    })


# ========================================
# CMS - GERENCIAMENTO DE TRILHAS
# ========================================

@bloquear_comercial
def gerenciar_trilha(request, aluno_id):
    """
    CMS para gerenciar a trilha individual de um aluno.
    Apenas ADMIN e MONITOR (do aluno) podem acessar.
    """
    usuario = verificar_acesso_monitor(request)
    if not usuario:
        return redirect('/')
    
    try:
        aluno = Usuario.objects.get(id=aluno_id, role=RoleChoices.ALUNO)
    except Usuario.DoesNotExist:
        return redirect('/trilha/monitor/')
    
    # Verificar permissão: ADMIN pode todos, MONITOR só seus alunos
    if usuario.role == RoleChoices.MONITOR:
        if aluno.monitor_responsavel_id != usuario.id:
            return HttpResponseForbidden("Você não tem permissão para gerenciar este aluno.")
    
    return render(request, 'trilha/gerenciar_conteudo.html', {
        'usuario': usuario,
        'aluno': aluno,
        'page_title': f'Trilha de {aluno.nome or aluno.email}'
    })


