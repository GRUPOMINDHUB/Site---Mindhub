from django.urls import path

from . import views

app_name = "comercial"

urlpatterns = [
    path("cadastros/", views.cadastros, name="cadastros"),
    path("cadastros/novo/", views.cadastro_novo, name="cadastro_novo"),
    path("cadastros/<int:aluno_id>/", views.cadastro_detalhe, name="cadastro_detalhe"),
    path("cadastros/<int:aluno_id>/proposta/", views.criar_proposta, name="criar_proposta"),
    path("propostas/<int:proposta_id>/aprovar/", views.aprovar_proposta, name="aprovar_proposta"),
    path("propostas/<int:proposta_id>/rejeitar/", views.rejeitar_proposta, name="rejeitar_proposta"),
    path("notificacoes/<int:notificacao_id>/lida/", views.marcar_notificacao_lida, name="marcar_notificacao_lida"),
    path("api/notificacoes/total/", views.api_total_notificacoes, name="api_total_notificacoes"),
]
