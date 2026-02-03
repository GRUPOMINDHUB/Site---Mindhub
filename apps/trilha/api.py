"""
API endpoints para o Monitor Graph View - Mindhub OS.
"""
import json
from datetime import timedelta
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Max, Count, Q

from apps.usuarios.models import Usuario, RoleChoices
from .models import (
    Mundo, Step, ProgressoAluno, Submissao, NotaSaude,
    StatusProgresso
)


def verificar_monitor(request):
    """Verifica se o usuário logado é monitor ou admin."""
    email = request.session.get('usuario')
    if not email:
        return None, JsonResponse({'error': 'Não autenticado'}, status=401)
    
    try:
        usuario = Usuario.objects.get(email=email)
        if not usuario.pode_validar:
            return None, JsonResponse({'error': 'Acesso negado'}, status=403)
        return usuario, None
    except Usuario.DoesNotExist:
        return None, JsonResponse({'error': 'Usuário não encontrado'}, status=404)


@require_http_methods(["GET"])
def api_monitor_alunos(request):
    """
    GET /api/monitor/alunos/
    Retorna lista de alunos com nota atual e cor para o Graph View.
    """
    monitor, error = verificar_monitor(request)
    if error:
        return error
    
    alunos = Usuario.objects.filter(role=RoleChoices.ALUNO, ativo=True)
    
    # Busca última nota de cada aluno
    alunos_data = []
    for aluno in alunos:
        nota_atual = NotaSaude.get_nota_atual(aluno)
        cor = NotaSaude.get_cor_nota(nota_atual)
        mundo_atual = aluno.get_mundo_atual()
        step_atual = aluno.get_step_atual()
        
        # Verifica última submissão
        ultima_submissao = Submissao.objects.filter(
            progresso__aluno=aluno
        ).order_by('-data_envio').first()
        
        # Conta submissões pendentes
        pendentes = Submissao.objects.filter(
            progresso__aluno=aluno,
            aprovado__isnull=True
        ).count()
        
        alunos_data.append({
            'id': aluno.id,
            'nome': aluno.nome or aluno.email.split('@')[0],
            'email': aluno.email,
            'foto': aluno.foto.url if aluno.foto else None,
            'nota': nota_atual,
            'cor': cor,
            'mundo': {
                'numero': mundo_atual.numero,
                'nome': mundo_atual.nome
            } if mundo_atual else None,
            'step': {
                'id': step_atual.id,
                'titulo': step_atual.titulo
            } if step_atual else None,
            'ultima_atividade': ultima_submissao.data_envio.isoformat() if ultima_submissao else None,
            'submissoes_pendentes': pendentes
        })
    
    return JsonResponse({
        'alunos': alunos_data,
        'total': len(alunos_data),
        'cores_legenda': {
            5: {'cor': '#28a745', 'label': 'Excelente'},
            4: {'cor': '#7cb342', 'label': 'Bom'},
            3: {'cor': '#ffc107', 'label': 'Regular'},
            2: {'cor': '#ff9800', 'label': 'Atenção'},
            1: {'cor': '#dc3545', 'label': 'Crítico'},
        }
    })


@require_http_methods(["GET"])
def api_monitor_aluno_detalhe(request, aluno_id):
    """
    GET /api/monitor/aluno/<id>/
    Retorna detalhes completos do aluno para o Drawer lateral.
    """
    monitor, error = verificar_monitor(request)
    if error:
        return error
    
    try:
        aluno = Usuario.objects.get(id=aluno_id, role=RoleChoices.ALUNO)
    except Usuario.DoesNotExist:
        return JsonResponse({'error': 'Aluno não encontrado'}, status=404)
    
    # Dados básicos
    nota_atual = NotaSaude.get_nota_atual(aluno)
    mundo_atual = aluno.get_mundo_atual()
    step_atual = aluno.get_step_atual()
    
    # Histórico de notas (últimas 10)
    historico_notas = NotaSaude.objects.filter(aluno=aluno)[:10]
    
    # Progresso geral
    total_steps = Step.objects.filter(ativo=True).count()
    steps_concluidos = ProgressoAluno.objects.filter(
        aluno=aluno,
        status=StatusProgresso.CONCLUIDO
    ).count()
    
    # Submissões pendentes de validação
    submissoes_pendentes = Submissao.objects.filter(
        progresso__aluno=aluno,
        aprovado__isnull=True
    ).select_related('progresso__step').order_by('-data_envio')
    
    # Últimas atividades
    ultimas_submissoes = Submissao.objects.filter(
        progresso__aluno=aluno
    ).select_related('progresso__step').order_by('-data_envio')[:5]
    
    return JsonResponse({
        'aluno': {
            'id': aluno.id,
            'nome': aluno.nome or aluno.email.split('@')[0],
            'email': aluno.email,
            'foto': aluno.foto.url if aluno.foto else None,
            'telefone': aluno.telefone,
            'data_cadastro': aluno.data_cadastro.isoformat(),
        },
        'saude': {
            'nota_atual': nota_atual,
            'cor': NotaSaude.get_cor_nota(nota_atual),
            'historico': [
                {
                    'nota': n.nota,
                    'data': n.data.isoformat(),
                    'automatica': n.automatica,
                    'observacao': n.observacao
                } for n in historico_notas
            ]
        },
        'progresso': {
            'mundo_atual': {
                'numero': mundo_atual.numero,
                'nome': mundo_atual.nome,
                'icone': mundo_atual.icone
            } if mundo_atual else None,
            'step_atual': {
                'id': step_atual.id,
                'titulo': step_atual.titulo,
                'tipo_validacao': step_atual.tipo_validacao
            } if step_atual else None,
            'total_steps': total_steps,
            'steps_concluidos': steps_concluidos,
            'porcentagem': round((steps_concluidos / total_steps * 100) if total_steps > 0 else 0, 1)
        },
        'submissoes_pendentes': [
            {
                'id': s.id,
                'step': s.progresso.step.titulo,
                'tipo': s.progresso.step.tipo_validacao,
                'data_envio': s.data_envio.isoformat(),
                'tem_arquivo': bool(s.arquivo),
                'tem_texto': bool(s.resposta_texto),
            } for s in submissoes_pendentes
        ],
        'ultimas_atividades': [
            {
                'id': s.id,
                'step': s.progresso.step.titulo,
                'data': s.data_envio.isoformat(),
                'status': 'pendente' if s.aprovado is None else ('aprovado' if s.aprovado else 'reprovado')
            } for s in ultimas_submissoes
        ]
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_monitor_atualizar_nota(request, aluno_id):
    """
    POST /api/monitor/aluno/<id>/nota/
    Atualiza a nota de saúde do aluno manualmente.
    Body: {"nota": 1-5, "observacao": "opcional"}
    """
    monitor, error = verificar_monitor(request)
    if error:
        return error
    
    try:
        aluno = Usuario.objects.get(id=aluno_id, role=RoleChoices.ALUNO)
    except Usuario.DoesNotExist:
        return JsonResponse({'error': 'Aluno não encontrado'}, status=404)
    
    try:
        data = json.loads(request.body)
        nota = int(data.get('nota'))
        observacao = data.get('observacao', '')
        
        if nota < 1 or nota > 5:
            return JsonResponse({'error': 'Nota deve ser entre 1 e 5'}, status=400)
    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse({'error': 'Dados inválidos'}, status=400)
    
    # Cria nova nota de saúde
    nova_nota = NotaSaude.objects.create(
        aluno=aluno,
        nota=nota,
        automatica=False,
        observacao=f"Definida por {monitor.email}. {observacao}".strip()
    )
    
    return JsonResponse({
        'success': True,
        'nota': {
            'id': nova_nota.id,
            'valor': nova_nota.nota,
            'cor': NotaSaude.get_cor_nota(nova_nota.nota),
            'data': nova_nota.data.isoformat()
        }
    })


@require_http_methods(["GET"])
def api_monitor_submissoes_pendentes(request):
    """
    GET /api/monitor/submissoes-pendentes/
    Lista todas as submissões pendentes de validação.
    """
    monitor, error = verificar_monitor(request)
    if error:
        return error
    
    submissoes = Submissao.objects.filter(
        aprovado__isnull=True
    ).select_related(
        'progresso__aluno', 
        'progresso__step__mundo'
    ).order_by('data_envio')
    
    return JsonResponse({
        'submissoes': [
            {
                'id': s.id,
                'aluno': {
                    'id': s.progresso.aluno.id,
                    'nome': s.progresso.aluno.nome or s.progresso.aluno.email.split('@')[0],
                    'email': s.progresso.aluno.email,
                    'foto': s.progresso.aluno.foto.url if s.progresso.aluno.foto else None
                },
                'step': {
                    'id': s.progresso.step.id,
                    'titulo': s.progresso.step.titulo,
                    'mundo': s.progresso.step.mundo.nome,
                    'tipo_validacao': s.progresso.step.tipo_validacao
                },
                'data_envio': s.data_envio.isoformat(),
                'arquivo': s.arquivo.url if s.arquivo else None,
                'resposta_texto': s.resposta_texto,
                'resposta_formulario': s.resposta_formulario
            } for s in submissoes
        ],
        'total': submissoes.count()
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_monitor_validar_submissao(request, submissao_id):
    """
    POST /api/monitor/submissao/<id>/validar/
    Aprova ou reprova uma submissão.
    Body: {"aprovado": true/false, "feedback": "texto opcional"}
    """
    monitor, error = verificar_monitor(request)
    if error:
        return error
    
    try:
        submissao = Submissao.objects.select_related(
            'progresso__aluno', 'progresso__step'
        ).get(id=submissao_id)
    except Submissao.DoesNotExist:
        return JsonResponse({'error': 'Submissão não encontrada'}, status=404)
    
    if submissao.aprovado is not None:
        return JsonResponse({'error': 'Submissão já foi validada'}, status=400)
    
    try:
        data = json.loads(request.body)
        aprovado = data.get('aprovado')
        feedback = data.get('feedback', '')
        
        if aprovado is None:
            return JsonResponse({'error': 'Campo aprovado é obrigatório'}, status=400)
        
        if not aprovado and not feedback:
            return JsonResponse({'error': 'Feedback é obrigatório para reprovação'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Dados inválidos'}, status=400)
    
    # Valida a submissão
    if aprovado:
        submissao.aprovar(monitor, feedback)
        mensagem = 'Submissão aprovada com sucesso'
    else:
        submissao.reprovar(monitor, feedback)
        mensagem = 'Submissão reprovada'
    
    return JsonResponse({
        'success': True,
        'message': mensagem,
        'submissao': {
            'id': submissao.id,
            'aprovado': submissao.aprovado,
            'feedback': submissao.feedback,
            'data_validacao': submissao.data_validacao.isoformat()
        },
        'aluno': {
            'id': submissao.progresso.aluno.id,
            'step_status': submissao.progresso.status
        }
    })


@require_http_methods(["GET"])
def api_monitor_estatisticas(request):
    """
    GET /api/monitor/estatisticas/
    Retorna estatísticas gerais para o dashboard.
    """
    monitor, error = verificar_monitor(request)
    if error:
        return error
    
    # Total de alunos
    total_alunos = Usuario.objects.filter(role=RoleChoices.ALUNO, ativo=True).count()
    
    # Distribuição por nota
    distribuicao_notas = {}
    for nota in range(1, 6):
        # Conta alunos cuja última nota é igual a 'nota'
        count = 0
        for aluno in Usuario.objects.filter(role=RoleChoices.ALUNO, ativo=True):
            if NotaSaude.get_nota_atual(aluno) == nota:
                count += 1
        distribuicao_notas[nota] = count
    
    # Submissões pendentes
    submissoes_pendentes = Submissao.objects.filter(aprovado__isnull=True).count()
    
    # Alunos inativos (sem submissão nos últimos 7 dias)
    limite_inatividade = timezone.now() - timedelta(days=7)
    alunos_ativos = Submissao.objects.filter(
        data_envio__gte=limite_inatividade
    ).values_list('progresso__aluno_id', flat=True).distinct()
    alunos_inativos = Usuario.objects.filter(
        role=RoleChoices.ALUNO, 
        ativo=True
    ).exclude(id__in=alunos_ativos).count()
    
    # Progresso por mundo
    progresso_mundos = []
    for mundo in Mundo.objects.filter(ativo=True).order_by('numero'):
        total_steps_mundo = mundo.steps.count()
        alunos_no_mundo = ProgressoAluno.objects.filter(
            step__mundo=mundo,
            status__in=[StatusProgresso.EM_ANDAMENTO, StatusProgresso.PENDENTE_VALIDACAO]
        ).values('aluno').distinct().count()
        
        progresso_mundos.append({
            'numero': mundo.numero,
            'nome': mundo.nome,
            'icone': mundo.icone,
            'total_steps': total_steps_mundo,
            'alunos_ativos': alunos_no_mundo
        })
    
    return JsonResponse({
        'total_alunos': total_alunos,
        'distribuicao_notas': distribuicao_notas,
        'submissoes_pendentes': submissoes_pendentes,
        'alunos_inativos': alunos_inativos,
        'progresso_mundos': progresso_mundos,
        'cores_notas': {
            str(k): NotaSaude.get_cor_nota(k) for k in range(1, 6)
        }
    })


def enviar_alerta_whatsapp(aluno_id, mensagem=None):
    """
    Placeholder para envio de alertas via WhatsApp.
    TODO: Implementar integração com API do WhatsApp (Twilio, Z-API, etc).
    """
    try:
        aluno = Usuario.objects.get(id=aluno_id)
        telefone = aluno.telefone
        
        if not telefone:
            return {'success': False, 'error': 'Aluno não tem telefone cadastrado'}
        
        # TODO: Implementar chamada real à API do WhatsApp
        # Exemplo com Twilio:
        # from twilio.rest import Client
        # client = Client(account_sid, auth_token)
        # message = client.messages.create(
        #     body=mensagem or f"Olá {aluno.nome}! Você tem atividades pendentes no Mindhub OS.",
        #     from_='whatsapp:+14155238886',
        #     to=f'whatsapp:{telefone}'
        # )
        
        return {
            'success': True, 
            'message': f'Alerta preparado para {telefone} (função placeholder)',
            'aluno_id': aluno_id
        }
    except Usuario.DoesNotExist:
        return {'success': False, 'error': 'Aluno não encontrado'}


@csrf_exempt
@require_http_methods(["POST"])
def api_monitor_enviar_alerta(request, aluno_id):
    """
    POST /api/monitor/aluno/<id>/alerta/
    Envia alerta via WhatsApp para o aluno.
    Body: {"mensagem": "texto opcional"}
    """
    monitor, error = verificar_monitor(request)
    if error:
        return error
    
    try:
        data = json.loads(request.body) if request.body else {}
        mensagem = data.get('mensagem')
    except json.JSONDecodeError:
        mensagem = None
    
    resultado = enviar_alerta_whatsapp(aluno_id, mensagem)
    
    status_code = 200 if resultado['success'] else 400
    return JsonResponse(resultado, status=status_code)


# ========================================
# API DO ALUNO
# ========================================

def verificar_aluno(request):
    """Verifica se o usuário logado é aluno."""
    email = request.session.get('usuario')
    if not email:
        return None, JsonResponse({'error': 'Não autenticado'}, status=401)
    
    try:
        usuario = Usuario.objects.get(email=email)
        if usuario.role != RoleChoices.ALUNO:
            return None, JsonResponse({'error': 'Acesso negado'}, status=403)
        return usuario, None
    except Usuario.DoesNotExist:
        return None, JsonResponse({'error': 'Usuário não encontrado'}, status=404)


@require_http_methods(["GET"])
def api_aluno_progresso(request):
    """
    GET /api/aluno/progresso/
    Retorna o progresso completo do aluno com mundos e steps.
    """
    aluno, error = verificar_aluno(request)
    if error:
        return error
    
    mundos_data = []
    total_pontos = 0
    total_steps = 0
    steps_concluidos_total = 0
    step_atual = None
    
    for mundo in Mundo.objects.filter(aluno=aluno, ativo=True).prefetch_related('steps').order_by('numero'):
        steps_mundo = mundo.steps.filter(ativo=True).order_by('ordem')
        steps_data = []
        steps_concluidos = 0
        
        for step in steps_mundo:
            total_steps += 1
            
            # Busca progresso do aluno neste step
            try:
                progresso = ProgressoAluno.objects.get(aluno=aluno, step=step)
                status = progresso.status
            except ProgressoAluno.DoesNotExist:
                status = StatusProgresso.BLOQUEADO
            
            if status == StatusProgresso.CONCLUIDO:
                steps_concluidos += 1
                steps_concluidos_total += 1
                total_pontos += step.pontos
            
            if status in [StatusProgresso.EM_ANDAMENTO, StatusProgresso.PENDENTE_VALIDACAO] and not step_atual:
                step_atual = {
                    'id': step.id,
                    'titulo': step.titulo,
                    'mundo': mundo.numero,
                    'status': status
                }
            
            steps_data.append({
                'id': step.id,
                'ordem': step.ordem,
                'titulo': step.titulo,
                'pontos': step.pontos,
                'status': status
            })
        
        porcentagem = round((steps_concluidos / len(steps_data) * 100) if steps_data else 0, 1)
        
        mundos_data.append({
            'numero': mundo.numero,
            'nome': mundo.nome,
            'icone': mundo.icone,
            'cor': mundo.cor_primaria,
            'total_steps': len(steps_data),
            'steps_concluidos': steps_concluidos,
            'porcentagem': porcentagem,
            'steps': steps_data
        })
    
    porcentagem_geral = round((steps_concluidos_total / total_steps * 100) if total_steps > 0 else 0, 1)
    
    return JsonResponse({
        'mundos': mundos_data,
        'total_pontos': total_pontos,
        'total_steps': total_steps,
        'steps_concluidos': steps_concluidos_total,
        'porcentagem_geral': porcentagem_geral,
        'step_atual': step_atual
    })


@require_http_methods(["GET"])
def api_aluno_step_detalhe(request, step_id):
    """
    GET /api/aluno/step/<id>/
    Retorna detalhes de um step específico.
    """
    aluno, error = verificar_aluno(request)
    if error:
        return error
    
    try:
        step = Step.objects.select_related('mundo').get(id=step_id, ativo=True)
    except Step.DoesNotExist:
        return JsonResponse({'error': 'Step não encontrado'}, status=404)
    
    # Busca progresso
    try:
        progresso = ProgressoAluno.objects.get(aluno=aluno, step=step)
        status = progresso.status
    except ProgressoAluno.DoesNotExist:
        status = StatusProgresso.BLOQUEADO
    
    # Busca feedback anterior (se reprovado)
    feedback_anterior = None
    ultima_submissao = Submissao.objects.filter(
        progresso__aluno=aluno,
        progresso__step=step,
        aprovado=False
    ).order_by('-data_envio').first()
    
    if ultima_submissao:
        feedback_anterior = ultima_submissao.feedback
    
    return JsonResponse({
        'id': step.id,
        'ordem': step.ordem,
        'titulo': step.titulo,
        'descricao': step.descricao,
        'instrucoes': step.instrucoes,
        'tipo_validacao': step.tipo_validacao,
        'pontos': step.pontos,
        'status': status,
        'mundo': {
            'numero': step.mundo.numero,
            'nome': step.mundo.nome
        },
        'feedback_anterior': feedback_anterior
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_aluno_submeter(request):
    """
    POST /api/aluno/submeter/
    Envia uma submissão para validação.
    """
    aluno, error = verificar_aluno(request)
    if error:
        return error
    
    step_id = request.POST.get('step_id')
    if not step_id:
        return JsonResponse({'error': 'step_id é obrigatório'}, status=400)
    
    try:
        step = Step.objects.get(id=step_id, ativo=True)
    except Step.DoesNotExist:
        return JsonResponse({'error': 'Step não encontrado'}, status=404)
    
    # Verifica se o step está em andamento
    try:
        progresso = ProgressoAluno.objects.get(aluno=aluno, step=step)
        if progresso.status != StatusProgresso.EM_ANDAMENTO:
            return JsonResponse({'error': 'Este step não está em andamento'}, status=400)
    except ProgressoAluno.DoesNotExist:
        return JsonResponse({'error': 'Você ainda não iniciou este step'}, status=400)
    
    # Cria a submissão
    submissao = Submissao(progresso=progresso)
    
    # Processa baseado no tipo de validação
    if step.tipo_validacao == 'FOTO':
        arquivo = request.FILES.get('arquivo')
        if not arquivo:
            return JsonResponse({'error': 'Arquivo é obrigatório'}, status=400)
        submissao.arquivo = arquivo
        
    elif step.tipo_validacao == 'TEXTO':
        texto = request.POST.get('resposta_texto', '').strip()
        if not texto:
            return JsonResponse({'error': 'Resposta é obrigatória'}, status=400)
        submissao.resposta_texto = texto
        
    elif step.tipo_validacao == 'FORMULARIO':
        # JSON com as respostas do formulário
        try:
            formulario = json.loads(request.POST.get('resposta_formulario', '{}'))
            submissao.resposta_formulario = formulario
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Dados do formulário inválidos'}, status=400)
    
    submissao.save()
    
    # Atualiza status do progresso
    progresso.enviar_para_validacao()
    
    return JsonResponse({
        'success': True,
        'message': 'Submissão enviada para validação!',
        'submissao_id': submissao.id
    })


# ========================================
# APIs DE GERENCIAMENTO DE TRILHAS (CMS)
# ========================================

def verificar_acesso_trilha(request, aluno_id):
    """
    Verifica se o usuário tem permissão para gerenciar a trilha do aluno.
    ADMIN: todos os alunos
    MONITOR: apenas seus alunos_responsaveis
    """
    email = request.session.get('usuario')
    if not email:
        return None, None, JsonResponse({'error': 'Não autenticado'}, status=401)
    
    try:
        usuario = Usuario.objects.get(email=email)
        aluno = Usuario.objects.get(id=aluno_id, role=RoleChoices.ALUNO)
        
        # ADMIN pode acessar todos
        if usuario.role == RoleChoices.ADMIN:
            return usuario, aluno, None
        
        # MONITOR só pode acessar seus alunos
        if usuario.role == RoleChoices.MONITOR:
            if aluno.monitor_responsavel_id == usuario.id:
                return usuario, aluno, None
            return None, None, JsonResponse({'error': 'Sem permissão para este aluno'}, status=403)
        
        return None, None, JsonResponse({'error': 'Acesso negado'}, status=403)
        
    except Usuario.DoesNotExist:
        return None, None, JsonResponse({'error': 'Usuário não encontrado'}, status=404)


@csrf_exempt
@require_http_methods(["GET"])
def api_trilha_aluno(request, aluno_id):
    """
    GET /api/trilha/{aluno_id}/
    Retorna mundos e steps do aluno para o CMS.
    """
    usuario, aluno, error = verificar_acesso_trilha(request, aluno_id)
    if error:
        return error
    
    mundos = Mundo.objects.filter(aluno=aluno, ativo=True).prefetch_related('steps').order_by('numero')
    
    data = {
        'aluno': {
            'id': aluno.id,
            'nome': aluno.nome or aluno.email,
            'email': aluno.email
        },
        'mundos': []
    }
    
    for mundo in mundos:
        mundo_data = {
            'id': mundo.id,
            'numero': mundo.numero,
            'nome': mundo.nome,
            'descricao': mundo.descricao,
            'objetivo': mundo.objetivo,
            'steps': []
        }
        
        for step in mundo.steps.filter(ativo=True).order_by('ordem'):
            mundo_data['steps'].append({
                'id': step.id,
                'ordem': step.ordem,
                'titulo': step.titulo,
                'descricao': step.descricao,
                'instrucoes': step.instrucoes,
                'tipo_validacao': step.tipo_validacao,
                'config_formulario': step.config_formulario,
                'pontos': step.pontos
            })
        
        data['mundos'].append(mundo_data)
    
    return JsonResponse(data)


@csrf_exempt
@require_http_methods(["POST"])
def api_salvar_mundo(request, aluno_id):
    """
    POST /api/trilha/{aluno_id}/mundo/
    Cria ou atualiza um mundo.
    """
    usuario, aluno, error = verificar_acesso_trilha(request, aluno_id)
    if error:
        return error
    
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    mundo_id = data.get('id')
    
    if mundo_id:
        # Atualizar existente
        try:
            mundo = Mundo.objects.get(id=mundo_id, aluno=aluno)
            mundo.nome = data.get('nome', mundo.nome)
            mundo.descricao = data.get('descricao', mundo.descricao)
            mundo.objetivo = data.get('objetivo', mundo.objetivo)
            mundo.numero = data.get('numero', mundo.numero)
            mundo.save()
        except Mundo.DoesNotExist:
            return JsonResponse({'error': 'Mundo não encontrado'}, status=404)
    else:
        # Criar novo
        ultimo_numero = Mundo.objects.filter(aluno=aluno).aggregate(Max('numero'))['numero__max'] or 0
        mundo = Mundo.objects.create(
            aluno=aluno,
            numero=ultimo_numero + 1,
            nome=data.get('nome', f'Mundo {ultimo_numero + 1}'),
            descricao=data.get('descricao', ''),
            objetivo=data.get('objetivo', '')
        )
    
    return JsonResponse({
        'success': True,
        'mundo': {
            'id': mundo.id,
            'numero': mundo.numero,
            'nome': mundo.nome
        }
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_salvar_step(request, aluno_id):
    """
    POST /api/trilha/{aluno_id}/step/
    Cria ou atualiza um step.
    """
    usuario, aluno, error = verificar_acesso_trilha(request, aluno_id)
    if error:
        return error
    
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    step_id = data.get('id')
    mundo_id = data.get('mundo_id')
    
    # Verificar se o mundo pertence ao aluno
    try:
        mundo = Mundo.objects.get(id=mundo_id, aluno=aluno)
    except Mundo.DoesNotExist:
        return JsonResponse({'error': 'Mundo não encontrado'}, status=404)
    
    if step_id:
        # Atualizar existente
        try:
            step = Step.objects.get(id=step_id, mundo=mundo)
            step.titulo = data.get('titulo', step.titulo)
            step.descricao = data.get('descricao', step.descricao)
            step.instrucoes = data.get('instrucoes', step.instrucoes)
            step.tipo_validacao = data.get('tipo_validacao', step.tipo_validacao)
            step.config_formulario = data.get('config_formulario', step.config_formulario)
            step.pontos = data.get('pontos', step.pontos)
            step.save()
        except Step.DoesNotExist:
            return JsonResponse({'error': 'Step não encontrado'}, status=404)
    else:
        # Criar novo
        ultima_ordem = Step.objects.filter(mundo=mundo).aggregate(Max('ordem'))['ordem__max'] or 0
        step = Step.objects.create(
            mundo=mundo,
            ordem=ultima_ordem + 1,
            titulo=data.get('titulo', 'Novo Step'),
            descricao=data.get('descricao', ''),
            instrucoes=data.get('instrucoes', ''),
            tipo_validacao=data.get('tipo_validacao', 'FOTO'),
            config_formulario=data.get('config_formulario'),
            pontos=data.get('pontos', 10)
        )
    
    return JsonResponse({
        'success': True,
        'step': {
            'id': step.id,
            'ordem': step.ordem,
            'titulo': step.titulo
        }
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_reordenar_steps(request, aluno_id):
    """
    POST /api/trilha/{aluno_id}/reordenar/
    Atualiza a ordem dos steps dentro de um mundo.
    Body: {"mundo_id": 1, "step_ids": [3, 1, 2]}
    """
    usuario, aluno, error = verificar_acesso_trilha(request, aluno_id)
    if error:
        return error
    
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    mundo_id = data.get('mundo_id')
    step_ids = data.get('step_ids', [])
    
    try:
        mundo = Mundo.objects.get(id=mundo_id, aluno=aluno)
    except Mundo.DoesNotExist:
        return JsonResponse({'error': 'Mundo não encontrado'}, status=404)
    
    # Atualiza a ordem de cada step
    for ordem, step_id in enumerate(step_ids, start=1):
        Step.objects.filter(id=step_id, mundo=mundo).update(ordem=ordem)
    
    return JsonResponse({'success': True})


@csrf_exempt
@require_http_methods(["DELETE"])
def api_deletar_step(request, aluno_id, step_id):
    """
    DELETE /api/trilha/{aluno_id}/step/{step_id}/
    Remove um step (soft delete via ativo=False).
    """
    usuario, aluno, error = verificar_acesso_trilha(request, aluno_id)
    if error:
        return error
    
    try:
        step = Step.objects.get(id=step_id, mundo__aluno=aluno)
        step.ativo = False
        step.save()
        return JsonResponse({'success': True})
    except Step.DoesNotExist:
        return JsonResponse({'error': 'Step não encontrado'}, status=404)


@csrf_exempt
@require_http_methods(["DELETE"])
def api_deletar_mundo(request, aluno_id, mundo_id):
    """
    DELETE /api/trilha/{aluno_id}/mundo/{mundo_id}/
    Remove um mundo e seus steps (soft delete via ativo=False).
    """
    usuario, aluno, error = verificar_acesso_trilha(request, aluno_id)
    if error:
        return error
    
    try:
        mundo = Mundo.objects.get(id=mundo_id, aluno=aluno)
        mundo.ativo = False
        mundo.save()
        # Desativa steps também
        mundo.steps.update(ativo=False)
        return JsonResponse({'success': True})
    except Mundo.DoesNotExist:
        return JsonResponse({'error': 'Mundo não encontrado'}, status=404)


@csrf_exempt
@require_http_methods(["POST"])
def api_clonar_trilha_base(request, aluno_id):
    """
    POST /api/trilha/{aluno_id}/clonar/
    Clona a Trilha Base (mundos com aluno=null) para o aluno.
    """
    usuario, aluno, error = verificar_acesso_trilha(request, aluno_id)
    if error:
        return error
    
    # Verifica se aluno já tem mundos
    if Mundo.objects.filter(aluno=aluno, ativo=True).exists():
        return JsonResponse({'error': 'Aluno já possui trilha. Delete antes de clonar.'}, status=400)
    
    # Busca trilha base (mundos sem aluno)
    mundos_base = Mundo.objects.filter(aluno__isnull=True, ativo=True).prefetch_related('steps')
    
    if not mundos_base.exists():
        return JsonResponse({'error': 'Nenhuma Trilha Base encontrada'}, status=404)
    
    # Clona cada mundo e seus steps
    mundos_criados = 0
    steps_criados = 0
    
    for mundo_base in mundos_base:
        novo_mundo = Mundo.objects.create(
            aluno=aluno,
            numero=mundo_base.numero,
            nome=mundo_base.nome,
            descricao=mundo_base.descricao,
            objetivo=mundo_base.objetivo,
            icone=mundo_base.icone,
            cor_primaria=mundo_base.cor_primaria
        )
        mundos_criados += 1
        
        for step_base in mundo_base.steps.filter(ativo=True):
            Step.objects.create(
                mundo=novo_mundo,
                ordem=step_base.ordem,
                titulo=step_base.titulo,
                descricao=step_base.descricao,
                instrucoes=step_base.instrucoes,
                tipo_validacao=step_base.tipo_validacao,
                config_formulario=step_base.config_formulario,
                pontos=step_base.pontos
            )
            steps_criados += 1
    
    return JsonResponse({
        'success': True,
        'message': f'Trilha clonada: {mundos_criados} mundos e {steps_criados} steps criados.',
        'mundos_criados': mundos_criados,
        'steps_criados': steps_criados
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_criar_trilha_vazia(request, aluno_id):
    """
    POST /api/trilha/{aluno_id}/criar-vazia/
    Cria 6 mundos vazios para o aluno.
    """
    usuario, aluno, error = verificar_acesso_trilha(request, aluno_id)
    if error:
        return error
    
    # Verifica se aluno já tem mundos
    if Mundo.objects.filter(aluno=aluno, ativo=True).exists():
        return JsonResponse({'error': 'Aluno já possui trilha'}, status=400)
    
    nomes_mundos = [
        'Mês 1 - Fundamentos',
        'Mês 2 - Operações',
        'Mês 3 - Finanças',
        'Mês 4 - Equipe',
        'Mês 5 - Marketing',
        'Mês 6 - Escala'
    ]
    
    for i, nome in enumerate(nomes_mundos, start=1):
        Mundo.objects.create(
            aluno=aluno,
            numero=i,
            nome=nome,
            descricao='',
            objetivo=''
        )
    
    return JsonResponse({
        'success': True,
        'message': '6 mundos vazios criados para o aluno.'
    })


