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
# ÁREA DO ALUNO - NAVEGAÇÃO DOIS NÍVEIS
# ========================================

@aluno_required
def aluno_mapa(request):
    """Redireciona para a home da trilha (novo sistema de dois níveis)."""
    return redirect('trilha:home_trilha')


@aluno_required
def home_trilha(request):
    """
    NÍVEL 1: Home Global da Trilha.
    Exibe os 6 Restaurantes/Castelos (um por mês).
    O aluno clica no mês atual para entrar no mapa de steps.
    """
    aluno = request.usuario
    
    # Busca todos os meses do aluno
    meses = Mundo.objects.filter(aluno=aluno, ativo=True).prefetch_related('steps').order_by('numero')
    
    # Prepara dados dos meses com status
    meses_data = []
    mes_atual = None
    
    for mes in meses:
        steps = mes.steps.filter(ativo=True).order_by('ordem')
        total_steps = steps.count()
        
        # Conta steps concluídos
        concluidos = 0
        tem_em_andamento = False
        
        for step in steps:
            progresso = ProgressoAluno.objects.filter(aluno=aluno, step=step).first()
            if progresso:
                if progresso.status == StatusProgresso.CONCLUIDO:
                    concluidos += 1
                elif progresso.status in [StatusProgresso.EM_ANDAMENTO, StatusProgresso.PENDENTE_VALIDACAO]:
                    tem_em_andamento = True
        
        # Determina status do mês
        if concluidos == total_steps and total_steps > 0:
            status = 'CONCLUIDO'
        elif tem_em_andamento or concluidos > 0:
            status = 'ATUAL'
            if not mes_atual:
                mes_atual = mes
        else:
            status = 'FUTURO'
        
        meses_data.append({
            'id': mes.id,
            'numero': mes.numero,
            'nome': mes.nome,
            'status': status,
            'concluidos': concluidos,
            'total': total_steps,
        })
    
    # Se não tem mês atual, o primeiro não-concluído é o atual
    if not mes_atual and meses_data:
        for m in meses_data:
            if m['status'] != 'CONCLUIDO':
                m['status'] = 'ATUAL'
                break
    
    return render(request, 'trilha/home_trilha.html', {
        'usuario': aluno,
        'meses': meses_data,
        'page_title': 'Império dos Meses - Gestor de Sucesso'
    })


@aluno_required
def detalhe_mes(request, mes_id):
    """
    NÍVEL 2: Mapa Interno de Steps.
    Exibe a trilha interna de um mês específico.
    """
    aluno = request.usuario
    
    try:
        mes = Mundo.objects.get(id=mes_id, aluno=aluno, ativo=True)
    except Mundo.DoesNotExist:
        return redirect('trilha:home_trilha')
    
    # Busca steps do mês
    steps = mes.steps.filter(ativo=True).order_by('ordem')
    
    # Prepara dados dos steps com status
    steps_data = []
    for step in steps:
        progresso = ProgressoAluno.objects.filter(aluno=aluno, step=step).first()
        status = progresso.status if progresso else StatusProgresso.BLOQUEADO
        
        steps_data.append({
            'id': step.id,
            'ordem': step.ordem,
            'titulo': step.titulo,
            'status': status,
            'pontos': step.pontos,
        })
    
    # Se não tem nenhum step em andamento, desbloqueia o primeiro
    if steps_data and not any(s['status'] in [StatusProgresso.EM_ANDAMENTO, StatusProgresso.PENDENTE_VALIDACAO] for s in steps_data):
        for s in steps_data:
            if s['status'] == StatusProgresso.BLOQUEADO:
                # Inicializa o progresso
                step_obj = Step.objects.get(id=s['id'])
                progresso, _ = ProgressoAluno.objects.get_or_create(
                    aluno=aluno,
                    step=step_obj,
                    defaults={'status': StatusProgresso.EM_ANDAMENTO}
                )
                if progresso.status == StatusProgresso.BLOQUEADO:
                    progresso.iniciar()
                s['status'] = StatusProgresso.EM_ANDAMENTO
                break
    
    return render(request, 'trilha/detalhe_mes.html', {
        'usuario': aluno,
        'mes': {
            'id': mes.id,
            'numero': mes.numero,
            'nome': mes.nome,
        },
        'steps': steps_data,
        'page_title': f'Mês {mes.numero}: {mes.nome}'
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


