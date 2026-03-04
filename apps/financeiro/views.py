from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from datetime import date

from apps.usuarios.models import Usuario, RoleChoices
from apps.usuarios.utils import get_usuario_logado
from .models import Contrato, Parcela
from .forms import ParcelaForm
from django.db.models import Sum

def verificar_acesso_financeiro(request):
    """Verifica se o usuário tem acesso (ADMIN ou MONITOR). COMERCIAL não tem."""
    usuario = get_usuario_logado(request)
    if usuario and usuario.role in [RoleChoices.ADMIN, RoleChoices.MONITOR]:
        return usuario
    return None

def dashboard_financeiro(request):
    """
    Dashboard principal do Financeiro.
    Contém a Aba 1 (Ficha de Alunos) e Aba 2 (Farol/Projeções).
    """
    usuario = verificar_acesso_financeiro(request)
    if not usuario:
        messages.error(request, 'Acesso Restrito ao módulo financeiro.')
        return redirect('usuarios:index')
        
    # Aba 1: Lista de Alunos e Contratos
    alunos_qs = Usuario.objects.filter(role=RoleChoices.ALUNO, ativo=True)
    
    if usuario.role == RoleChoices.MONITOR:
        alunos_qs = alunos_qs.filter(monitor_responsavel=usuario)
        
    # Prepara dados para a tabela
    alunos_data = []
    
    # Aba 2: Métricas Geriais
    total_alunos_ativos = alunos_qs.count()
    total_atrasados = 0
    total_inadimplentes = 0
    total_cancelados = 0
    valor_em_atraso = 0
    valor_inadimplente = 0
    
    for aluno in alunos_qs:
        try:
            contrato = getattr(aluno, 'contrato', None)
            if not contrato:
                alunos_data.append({
                    'id': aluno.id,
                    'nome': aluno.nome or aluno.email.split('@')[0],
                    'email': aluno.email,
                    'monitor': aluno.monitor_responsavel.nome if aluno.monitor_responsavel else 'Sem Monitor',
                    'parcela_atual': None,
                    'status_badge': 'Sem Contrato',
                    'status_color': 'bg-gray-500',
                    'telefone': aluno.telefone_sem_formatacao,
                })
                continue
                
            if contrato.status == 'CANCELADO':
                total_cancelados += 1
                alunos_data.append({
                    'id': aluno.id,
                    'nome': aluno.nome or aluno.email.split('@')[0],
                    'email': aluno.email,
                    'monitor': aluno.monitor_responsavel.nome if aluno.monitor_responsavel else 'Sem Monitor',
                    'parcela_atual': None,
                    'status_badge': 'Cancelado',
                    'status_color': 'bg-gray-500',
                    'telefone': aluno.telefone_sem_formatacao,
                })
                continue

            # Encontrar a parcela atual (a próxima a vencer ou a mais atrasada)
            hoje = timezone.localtime(timezone.now()).date()
            parcelas = contrato.parcelas.all().order_by('data_vencimento')
            parcela_atual = None
            
            # Prioridade: 1. Inadimplente, 2. Atrasada, 3. Pendente
            inadimplentes = [p for p in parcelas if p.status_dinamico == 'INADIMPLENTE']
            atrasadas = [p for p in parcelas if p.status_dinamico == 'ATRASADO']
            pendentes = [p for p in parcelas if p.status_dinamico == 'PENDENTE']
            
            # Métricas Globais (Agregando por aluno as piores situações)
            teve_inadimplencia = len(inadimplentes) > 0
            teve_atraso = len(atrasadas) > 0 and not teve_inadimplencia
            
            if teve_inadimplencia:
                total_inadimplentes += 1
                for p in inadimplentes:
                    valor_inadimplente += p.valor
            elif teve_atraso:
                total_atrasados += 1
                for p in atrasadas:
                    valor_em_atraso += p.valor
            
            if inadimplentes:
                parcela_atual = inadimplentes[0]
            elif atrasadas:
                parcela_atual = atrasadas[0]
            elif pendentes:
                parcela_atual = pendentes[0]
                
            if parcela_atual:
                status_dyn = parcela_atual.status_dinamico
                
                # Definir cores pro badge
                colors = {
                    'PAGO': 'bg-green-500/20 text-green-500',
                    'PENDENTE': 'bg-yellow-500/20 text-yellow-500',
                    'ATRASADO': 'bg-orange-500/20 text-orange-500',
                    'INADIMPLENTE': 'bg-mindhub-red/20 text-mindhub-red',
                }
                
                alunos_data.append({
                    'id': aluno.id,
                    'nome': aluno.nome or aluno.email.split('@')[0],
                    'email': aluno.email,
                    'monitor': aluno.monitor_responsavel.nome if aluno.monitor_responsavel else 'Sem Monitor',
                    'parcela_atual': {
                        'numero': parcela_atual.numero,
                        'valor': parcela_atual.valor,
                        'vencimento': parcela_atual.data_vencimento,
                    },
                    'status_badge': status_dyn,
                    'status_color': colors.get(status_dyn, 'bg-gray-500/20 text-gray-500'),
                    'telefone': aluno.telefone_sem_formatacao,
                })
            else:
                alunos_data.append({
                    'id': aluno.id,
                    'nome': aluno.nome or aluno.email.split('@')[0],
                    'email': aluno.email,
                    'monitor': aluno.monitor_responsavel.nome if aluno.monitor_responsavel else 'Sem Monitor',
                    'parcela_atual': None,
                    'status_badge': 'Quitado',
                    'status_color': 'bg-green-500/20 text-green-500',
                    'telefone': aluno.telefone_sem_formatacao,
                })
        except Exception as e:
            print(f"Erro ao processar aluno {aluno.id} no financeiro: {e}")
            pass
            
    # Filtro de Período via URL parameter
    periodo = request.GET.get('periodo', 'mensal')
    hoje = timezone.localtime(timezone.now()).date()
    
    if periodo == 'anual':
        data_inicio = hoje.replace(month=1, day=1)
        data_fim = hoje.replace(month=12, day=31)
    elif periodo == 'semestral':
        if hoje.month <= 6:
            data_inicio = hoje.replace(month=1, day=1)
            data_fim = hoje.replace(month=6, day=30)
        else:
            data_inicio = hoje.replace(month=7, day=1)
            data_fim = hoje.replace(month=12, day=31)
    elif periodo == 'trimestral':
        trimestre = (hoje.month - 1) // 3 + 1
        mes_inicio = (trimestre - 1) * 3 + 1
        data_inicio = hoje.replace(month=mes_inicio, day=1)
        
        mes_fim = mes_inicio + 2
        proximo_mes = mes_fim + 1 if mes_fim < 12 else 1
        ano_fim = hoje.year if mes_fim < 12 else hoje.year + 1
        data_fim = date(ano_fim, proximo_mes, 1) - relativedelta(days=1)
    else: # mensal
        data_inicio = hoje.replace(day=1)
        proximo_mes = hoje.month + 1 if hoje.month < 12 else 1
        ano_fim = hoje.year if hoje.month < 12 else hoje.year + 1
        data_fim = date(ano_fim, proximo_mes, 1) - relativedelta(days=1)
        
    faturamento_presumido_qs = Parcela.objects.filter(
        data_vencimento__gte=data_inicio, 
        data_vencimento__lte=data_fim,
        contrato__status='ATIVO'
    )
    
    if usuario.role == RoleChoices.MONITOR:
         faturamento_presumido_qs = faturamento_presumido_qs.filter(contrato__aluno__monitor_responsavel=usuario)

    faturamento_presumido = faturamento_presumido_qs.aggregate(total=Sum('valor'))['total'] or 0


    pct_atrasados = (total_atrasados / total_alunos_ativos * 100) if total_alunos_ativos > 0 else 0
    pct_inadimplentes = (total_inadimplentes / total_alunos_ativos * 100) if total_alunos_ativos > 0 else 0
    pct_cancelados = (total_cancelados / total_alunos_ativos * 100) if total_alunos_ativos > 0 else 0
            
    metrics = {
        'total_ativos': total_alunos_ativos,
        'pct_atrasados': round(pct_atrasados, 1),
        'pct_inadimplentes': round(pct_inadimplentes, 1),
        'pct_cancelados': round(pct_cancelados, 1),
        'faturamento_presumido': faturamento_presumido,
        'valor_em_atraso': valor_em_atraso,
        'valor_inadimplente': valor_inadimplente,
        'periodo_selecionado': periodo,
        'data_inicio_filtro': data_inicio.strftime('%d/%m/%Y'),
        'data_fim_filtro': data_fim.strftime('%d/%m/%Y'),
    }

    return render(request, 'financeiro/dashboard.html', {
        'usuario': usuario,
        'alunos': alunos_data,
        'metrics': metrics,
        'page_title': 'Central Financeira'
    })

def api_ficha_aluno(request, aluno_id):
    """Retorna os dados do contrato e parcelas de um aluno para o Modal."""
    usuario = verificar_acesso_financeiro(request)
    if not usuario:
        return JsonResponse({'error': 'Acesso negado'}, status=403)
        
    aluno = get_object_or_404(Usuario, id=aluno_id, role=RoleChoices.ALUNO)
    
    if usuario.role == RoleChoices.MONITOR and aluno.monitor_responsavel != usuario:
        return JsonResponse({'error': 'Acesso negado'}, status=403)
        
    try:
        contrato = aluno.contrato
        parcelas = contrato.parcelas.all().order_by('data_vencimento')
        
        parcelas_data = []
        for p in parcelas:
            parcelas_data.append({
                'id': p.id,
                'numero': p.numero,
                'valor': str(p.valor),
                'data_vencimento': p.data_vencimento.strftime('%Y-%m-%d'),
                'data_pagamento': p.data_pagamento.strftime('%Y-%m-%d') if p.data_pagamento else None,
                'status': p.status_dinamico,
                'link': p.link_pagamento_ou_pix,
                'comprovante_url': p.comprovante.url if p.comprovante else None
            })
            
        return JsonResponse({
            'contrato': {
                'id': contrato.id,
                'valor_total': str(contrato.valor_total_negociado),
                'data_assinatura': contrato.data_assinatura.strftime('%Y-%m-%d'),
                'status': contrato.status,
                'observacoes': contrato.observacoes_gerais
            },
            'parcelas': parcelas_data,
            'aluno': {
                'nome': aluno.nome or aluno.email,
                'telefone': aluno.telefone_sem_formatacao
            }
        })
    except Exception as e:
         return JsonResponse({'error': 'Contrato não encontrado para este aluno.'}, status=404)

@require_POST
def api_atualizar_parcela(request, parcela_id):
    """Atualiza dados de uma parcela (dar baixa, link, comprovante) direto do modal."""
    usuario = verificar_acesso_financeiro(request)
    if not usuario:
        return JsonResponse({'error': 'Acesso negado'}, status=403)
        
    parcela = get_object_or_404(Parcela, id=parcela_id)
    
    if usuario.role == RoleChoices.MONITOR and parcela.contrato.aluno.monitor_responsavel != usuario:
        return JsonResponse({'error': 'Acesso negado'}, status=403)
        
    # Extrai dados do POST/FILES
    data_pagamento = request.POST.get('data_pagamento')
    link = request.POST.get('link_pagamento_ou_pix')
    comprovante = request.FILES.get('comprovante')
    
    if data_pagamento:
        parcela.data_pagamento = data_pagamento
    if link is not None:
        parcela.link_pagamento_ou_pix = link
    if comprovante:
        parcela.comprovante = comprovante
        
    parcela.save()
    
    return JsonResponse({'success': True, 'status_atualizado': parcela.status_dinamico})
