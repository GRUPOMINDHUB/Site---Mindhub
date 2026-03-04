from django.urls import path
from . import views

app_name = 'financeiro'

urlpatterns = [
    # Dashboard Principal
    path('dashboard/', views.dashboard_financeiro, name='dashboard'),
    
    # APIs para o Modal (Ficha do Aluno e Edição)
    path('api/ficha/<int:aluno_id>/', views.api_ficha_aluno, name='api_ficha_aluno'),
    path('api/parcela/<int:parcela_id>/atualizar/', views.api_atualizar_parcela, name='api_atualizar_parcela'),
]
