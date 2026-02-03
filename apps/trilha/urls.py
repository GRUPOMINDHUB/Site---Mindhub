"""
URLs do app Trilha - Mindhub OS.
"""
from django.urls import path
from . import views, api

app_name = 'trilha'

urlpatterns = [
    # Views (páginas)
    path('monitor/', views.monitor_dashboard, name='monitor_dashboard'),
    path('monitor/graph/', views.monitor_graph, name='monitor_graph'),
    path('monitor/validar/', views.monitor_validar, name='monitor_validar'),
    path('gerenciar/<int:aluno_id>/', views.gerenciar_trilha, name='gerenciar_trilha'),
    
    # Área do Aluno
    path('mapa/', views.aluno_mapa, name='aluno_mapa'),
    
    # API endpoints para Monitor (Graph View)
    path('api/monitor/alunos/', api.api_monitor_alunos, name='api_monitor_alunos'),
    path('api/monitor/aluno/<int:aluno_id>/', api.api_monitor_aluno_detalhe, name='api_monitor_aluno_detalhe'),
    path('api/monitor/aluno/<int:aluno_id>/nota/', api.api_monitor_atualizar_nota, name='api_monitor_atualizar_nota'),
    path('api/monitor/aluno/<int:aluno_id>/alerta/', api.api_monitor_enviar_alerta, name='api_monitor_enviar_alerta'),
    path('api/monitor/submissoes-pendentes/', api.api_monitor_submissoes_pendentes, name='api_monitor_submissoes_pendentes'),
    path('api/monitor/submissao/<int:submissao_id>/validar/', api.api_monitor_validar_submissao, name='api_monitor_validar_submissao'),
    path('api/monitor/estatisticas/', api.api_monitor_estatisticas, name='api_monitor_estatisticas'),
    
    # API endpoints para Aluno
    path('api/aluno/progresso/', api.api_aluno_progresso, name='api_aluno_progresso'),
    path('api/aluno/step/<int:step_id>/', api.api_aluno_step_detalhe, name='api_aluno_step_detalhe'),
    path('api/aluno/submeter/', api.api_aluno_submeter, name='api_aluno_submeter'),
    
    # API endpoints para Gerenciamento de Trilhas (CMS)
    path('api/trilha/<int:aluno_id>/', api.api_trilha_aluno, name='api_trilha_aluno'),
    path('api/trilha/<int:aluno_id>/mundo/', api.api_salvar_mundo, name='api_salvar_mundo'),
    path('api/trilha/<int:aluno_id>/step/', api.api_salvar_step, name='api_salvar_step'),
    path('api/trilha/<int:aluno_id>/reordenar/', api.api_reordenar_steps, name='api_reordenar_steps'),
    path('api/trilha/<int:aluno_id>/step/<int:step_id>/', api.api_deletar_step, name='api_deletar_step'),
    path('api/trilha/<int:aluno_id>/mundo/<int:mundo_id>/', api.api_deletar_mundo, name='api_deletar_mundo'),
    path('api/trilha/<int:aluno_id>/clonar/', api.api_clonar_trilha_base, name='api_clonar_trilha'),
    path('api/trilha/<int:aluno_id>/criar-vazia/', api.api_criar_trilha_vazia, name='api_criar_trilha_vazia'),
]


