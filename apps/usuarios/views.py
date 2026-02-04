"""
Views de autenticação e gestão de acessos - Mindhub OS.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth.hashers import make_password
import json
import secrets
import string

from .models import Usuario, RoleChoices
from .utils import get_usuario_logado

def index(request):
    """
    Rota: / (Flask)
    Renderiza página de login
    """
    return render(request, 'login.html')


def ia_page(request):
    """
    Rota: /ia (Flask)
    Página do chat - requer autenticação
    """
    if 'usuario' not in request.session:
        return redirect('usuarios:index')
    return render(request, 'chat.html')


@csrf_exempt  # Temporário - em produção usar CSRF token no frontend
@require_http_methods(["POST"])
def login_endpoint(request):
    """
    Rota: /login (Flask)
    Valida credenciais e cria sessão
    """
    try:
        dados = json.loads(request.body)
        email = dados.get('email')
        senha = dados.get('senha')
        
        # Validação usando Django ORM (email sem diferenciar maiúsculas)
        if not email or not senha:
            return JsonResponse({
                "status": "erro",
                "mensagem": "E-mail e senha são obrigatórios"
            }, status=401)
        
        try:
            usuario = Usuario.objects.get(email__iexact=email.strip())
            if usuario.verificar_senha(senha):
                # Salva usuário na sessão (igual ao Flask)
                request.session['usuario'] = usuario.email
                return JsonResponse({
                    "status": "sucesso",
                    "role": usuario.role
                }, status=200)
        except Usuario.DoesNotExist:
            pass
        
        return JsonResponse({
            "status": "erro",
            "mensagem": "Credenciais inválidas"
        }, status=401)
        
    except Exception as e:
        return JsonResponse({
            "status": "erro",
            "mensagem": str(e)
        }, status=500)


def logout(request):
    """
    Rota: /logout (Flask)
    Limpa sessão e redireciona para login
    """
    request.session.pop('usuario', None)
    return redirect('usuarios:index')


# ========================================
# GESTÃO DE ACESSOS
# ========================================

def gerenciar_acessos(request):
    """
    View principal de gestão de acessos.
    Lógica por role:
    - ADMIN: vê todos os usuários
    - MONITOR: vê apenas seus alunos
    - COMERCIAL: redireciona para cadastro
    """
    usuario = get_usuario_logado(request)
    if not usuario or not usuario.pode_gerenciar_acessos:
        messages.error(request, 'Acesso negado.')
        return redirect('/')
    
    # COMERCIAL vai direto para cadastro
    if usuario.is_comercial:
        return redirect('usuarios:cadastrar_usuario')
    
    # ADMIN vê todos
    if usuario.is_admin:
        usuarios = Usuario.objects.all().order_by('-data_cadastro')
    # MONITOR vê apenas seus alunos
    elif usuario.is_monitor:
        usuarios = Usuario.objects.filter(
            role=RoleChoices.ALUNO,
            monitor_responsavel=usuario
        ).order_by('-data_cadastro')
    else:
        usuarios = Usuario.objects.none()
    
    return render(request, 'usuarios/gerenciar_acessos.html', {
        'usuario': usuario,
        'usuarios': usuarios,
        'page_title': 'Gerenciar Acessos'
    })


def cadastrar_usuario(request):
    """
    Formulário de cadastro de usuário.
    Regras:
    - ADMIN: pode escolher qualquer role, se ALUNO pode escolher qualquer MONITOR
    - MONITOR: só pode cadastrar ALUNO, monitor_responsavel = ele mesmo (oculto)
    - COMERCIAL: só pode cadastrar ALUNO, DEVE escolher um MONITOR
    """
    usuario_logado = get_usuario_logado(request)
    if not usuario_logado or not usuario_logado.pode_gerenciar_acessos:
        messages.error(request, 'Acesso negado.')
        return redirect('/')
    
    # Busca monitores para dropdown
    monitores = Usuario.objects.filter(role=RoleChoices.MONITOR, ativo=True).order_by('nome')
    
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        email = request.POST.get('email', '').strip()
        senha = request.POST.get('senha', '').strip()
        gerar_senha = request.POST.get('gerar_senha') == 'on'
        role = request.POST.get('role', RoleChoices.ALUNO)
        monitor_id = request.POST.get('monitor_responsavel')
        telefone = request.POST.get('telefone', '').strip()
        
        # Validações
        if not nome or not email:
            messages.error(request, 'Nome e e-mail são obrigatórios.')
            return render(request, 'usuarios/form_usuario.html', {
                'usuario': usuario_logado,
                'monitores': monitores,
                'page_title': 'Cadastrar Usuário',
                'form_data': request.POST
            })
        
        # Regras por role
        if usuario_logado.is_monitor:
            role = RoleChoices.ALUNO
            monitor_id = str(usuario_logado.id)
        elif usuario_logado.is_comercial:
            role = RoleChoices.ALUNO
            if not monitor_id:
                messages.error(request, 'Você deve selecionar um Monitor responsável.')
                return render(request, 'usuarios/form_usuario.html', {
                    'usuario': usuario_logado,
                    'monitores': monitores,
                    'page_title': 'Cadastrar Usuário',
                    'form_data': request.POST
                })
        
        # Gera senha se solicitado
        if gerar_senha or not senha:
            senha = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        
        # Cria usuário
        try:
            novo_usuario = Usuario.objects.create(
                nome=nome,
                email=email,
                senha=make_password(senha),
                role=role,
                telefone=telefone,
                ativo=True
            )
            
            if role == RoleChoices.ALUNO and monitor_id:
                try:
                    monitor = Usuario.objects.get(id=int(monitor_id), role=RoleChoices.MONITOR)
                    novo_usuario.monitor_responsavel = monitor
                    novo_usuario.save()
                except (Usuario.DoesNotExist, ValueError):
                    pass
            
            messages.success(request, f'Usuário {novo_usuario.nome} cadastrado com sucesso!')
            if gerar_senha:
                messages.info(request, f'Senha gerada: {senha}')
            return redirect('usuarios:gerenciar_acessos')
            
        except Exception as e:
            messages.error(request, f'Erro ao cadastrar: {str(e)}')
    
    return render(request, 'usuarios/form_usuario.html', {
        'usuario': usuario_logado,
        'monitores': monitores,
        'page_title': 'Cadastrar Usuário'
    })


def editar_usuario(request, usuario_id):
    """
    Formulário de edição de usuário.
    Mesmas regras de cadastro.
    """
    usuario_logado = get_usuario_logado(request)
    if not usuario_logado or not usuario_logado.pode_gerenciar_acessos:
        messages.error(request, 'Acesso negado.')
        return redirect('/')
    
    usuario_edit = get_object_or_404(Usuario, id=usuario_id)
    
    # Verifica permissão: MONITOR só edita seus alunos
    if usuario_logado.is_monitor:
        if usuario_edit.monitor_responsavel != usuario_logado:
            messages.error(request, 'Você só pode editar seus próprios alunos.')
            return redirect('usuarios:gerenciar_acessos')
    
    monitores = Usuario.objects.filter(role=RoleChoices.MONITOR, ativo=True).order_by('nome')
    
    if request.method == 'POST':
        usuario_edit.nome = request.POST.get('nome', '').strip()
        usuario_edit.email = request.POST.get('email', '').strip()
        senha = request.POST.get('senha', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        
        # Role (só ADMIN pode mudar)
        if usuario_logado.is_admin:
            role = request.POST.get('role')
            if role in [r[0] for r in RoleChoices.choices]:
                usuario_edit.role = role
                # Se mudou para não-ALUNO, limpa monitor_responsavel
                if role != RoleChoices.ALUNO:
                    usuario_edit.monitor_responsavel = None
        
        # Monitor responsável (se for aluno)
        if usuario_edit.role == RoleChoices.ALUNO:
            monitor_id = request.POST.get('monitor_responsavel')
            if monitor_id:
                try:
                    monitor = Usuario.objects.get(id=int(monitor_id), role=RoleChoices.MONITOR)
                    usuario_edit.monitor_responsavel = monitor
                except (Usuario.DoesNotExist, ValueError):
                    pass
            # Se não forneceu monitor e é COMERCIAL, mantém o atual ou deixa None
            elif usuario_logado.is_comercial and not monitor_id:
                # COMERCIAL deve sempre fornecer um monitor
                pass  # Já validado no cadastro
        
        # Senha (só atualiza se fornecida)
        if senha:
            usuario_edit.senha = make_password(senha)
        
        usuario_edit.telefone = telefone
        usuario_edit.save()
        
        messages.success(request, f'Usuário {usuario_edit.nome} atualizado com sucesso!')
        return redirect('usuarios:gerenciar_acessos')
    
    return render(request, 'usuarios/form_usuario.html', {
        'usuario': usuario_logado,
        'usuario_edit': usuario_edit,
        'monitores': monitores,
        'page_title': f'Editar Usuário - {usuario_edit.nome}'
    })


@require_http_methods(["POST"])
def excluir_usuario(request, usuario_id):
    """
    Exclui um usuário (soft delete: marca como inativo).
    """
    usuario_logado = get_usuario_logado(request)
    if not usuario_logado or not usuario_logado.pode_gerenciar_acessos:
        messages.error(request, 'Acesso negado.')
        return redirect('/')
    
    usuario_excluir = get_object_or_404(Usuario, id=usuario_id)
    
    # Verifica permissão
    if usuario_logado.is_monitor:
        if usuario_excluir.monitor_responsavel != usuario_logado:
            messages.error(request, 'Você só pode excluir seus próprios alunos.')
            return redirect('usuarios:gerenciar_acessos')
    
    # Não permite excluir a si mesmo
    if usuario_excluir.id == usuario_logado.id:
        messages.error(request, 'Você não pode excluir seu próprio usuário.')
        return redirect('usuarios:gerenciar_acessos')
    
    # Soft delete
    usuario_excluir.ativo = False
    usuario_excluir.save()
    
    messages.success(request, f'Usuário {usuario_excluir.nome} foi desativado.')
    return redirect('usuarios:gerenciar_acessos')
