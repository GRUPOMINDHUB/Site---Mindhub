"""
Models do app Usuarios - Mindhub OS.
"""
from django.db import models
from django.contrib.auth.hashers import make_password, check_password


class RoleChoices(models.TextChoices):
    """Tipos de usuário no sistema."""
    ADMIN = 'ADMIN', 'Administrador'
    MONITOR = 'MONITOR', 'Monitor'
    ALUNO = 'ALUNO', 'Aluno'
    COMERCIAL = 'COMERCIAL', 'Comercial'


class Usuario(models.Model):
    """
    Modelo de Usuário do Mindhub OS.
    Suporta roles: ADMIN, MONITOR, ALUNO.
    """
    email = models.EmailField(unique=True)
    senha = models.CharField(max_length=255)
    role = models.CharField(
        max_length=20, 
        choices=RoleChoices.choices, 
        default=RoleChoices.ALUNO
    )
    nome = models.CharField(max_length=200, blank=True)
    foto = models.ImageField(
        upload_to='fotos_usuarios/', 
        null=True, 
        blank=True,
        help_text="Foto de perfil do usuário"
    )
    telefone = models.CharField(max_length=20, blank=True, help_text="WhatsApp para alertas")
    monitor_responsavel = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alunos_responsaveis',
        limit_choices_to={'role': RoleChoices.MONITOR},
        help_text="Monitor responsável pelo aluno (apenas para alunos)"
    )
    data_cadastro = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
    
    def __str__(self):
        return self.nome or self.email
    
    def verificar_senha(self, senha):
        """
        Verifica se a senha fornecida corresponde à senha armazenada.
        Suporta tanto texto plano (legado) quanto hash.
        """
        # Se a senha começa com algoritmo de hash do Django
        if self.senha.startswith('pbkdf2_') or self.senha.startswith('argon2'):
            return check_password(senha, self.senha)
        # Fallback para texto plano (legado)
        return self.senha == senha
    
    def set_senha(self, senha):
        """Define a senha com hash seguro."""
        self.senha = make_password(senha)
        self.save()
    
    @property
    def is_admin(self):
        return self.role == RoleChoices.ADMIN
    
    @property
    def is_monitor(self):
        return self.role == RoleChoices.MONITOR
    
    @property
    def is_aluno(self):
        return self.role == RoleChoices.ALUNO
    
    @property
    def is_comercial(self):
        return self.role == RoleChoices.COMERCIAL
    
    @property
    def pode_validar(self):
        """Verifica se o usuário pode validar submissões."""
        return self.role in [RoleChoices.ADMIN, RoleChoices.MONITOR]
    
    @property
    def pode_gerenciar_acessos(self):
        """Verifica se o usuário pode gerenciar acessos."""
        return self.role in [RoleChoices.ADMIN, RoleChoices.MONITOR, RoleChoices.COMERCIAL]
    
    def get_nota_saude_atual(self):
        """Retorna a nota de saúde mais recente."""
        from apps.trilha.models import NotaSaude
        return NotaSaude.get_nota_atual(self)
    
    def get_mundo_atual(self):
        """Retorna o mundo atual do aluno baseado no progresso."""
        from apps.trilha.models import ProgressoAluno, StatusProgresso
        # Busca o step mais avançado em andamento ou pendente
        progresso = ProgressoAluno.objects.filter(
            aluno=self,
            status__in=[StatusProgresso.EM_ANDAMENTO, StatusProgresso.PENDENTE_VALIDACAO]
        ).select_related('step__mundo').order_by('-step__mundo__numero', '-step__ordem').first()
        
        if progresso:
            return progresso.step.mundo
        
        # Se não tem progresso em andamento, busca o último concluído
        ultimo_concluido = ProgressoAluno.objects.filter(
            aluno=self,
            status=StatusProgresso.CONCLUIDO
        ).select_related('step__mundo').order_by('-step__mundo__numero', '-step__ordem').first()
        
        if ultimo_concluido:
            return ultimo_concluido.step.mundo
        
        # Retorna None se nunca começou
        return None
    
    def get_step_atual(self):
        """Retorna o step atual do aluno."""
        from apps.trilha.models import ProgressoAluno, StatusProgresso
        progresso = ProgressoAluno.objects.filter(
            aluno=self,
            status__in=[StatusProgresso.EM_ANDAMENTO, StatusProgresso.PENDENTE_VALIDACAO]
        ).select_related('step').order_by('step__mundo__numero', 'step__ordem').first()
        
        return progresso.step if progresso else None
