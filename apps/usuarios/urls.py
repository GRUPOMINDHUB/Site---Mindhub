"""
URLs do app Usuarios
Rotas de autenticação e gestão de acessos.
"""
from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [
    # Autenticação
    path('', views.landing_page, name='landing_page'),
    path('login/', views.index, name='index'), # Login page (antiga index)
    path('api/login', views.login_endpoint, name='login_endpoint'), # API Endpoint
    path('logout', views.logout, name='logout'),
    
    # Gestão de Acessos
    path('gerenciar-acessos/', views.gerenciar_acessos, name='gerenciar_acessos'),
    path('cadastrar-usuario/', views.cadastrar_usuario, name='cadastrar_usuario'),
    path('editar-usuario/<int:usuario_id>/', views.editar_usuario, name='editar_usuario'),
    path('excluir-usuario/<int:usuario_id>/', views.excluir_usuario, name='excluir_usuario'),
]
