from django.urls import path

from . import views

app_name = "financeiro"

urlpatterns = [
    path("dashboard/", views.dashboard_financeiro, name="dashboard"),
    path("aviso-inadimplencia/", views.aviso_inadimplencia, name="aviso_inadimplencia"),
    path("api/ficha/<int:aluno_id>/", views.api_ficha_aluno, name="api_ficha_aluno"),
    path("api/parcela/<int:parcela_id>/atualizar/", views.api_atualizar_parcela, name="api_atualizar_parcela"),
    path("api/parcela/<int:parcela_id>/renegociar/", views.api_renegociar_parcela, name="api_renegociar_parcela"),
]
