"""
Models do app Trilha - Sistema de Trilha Gamificada Mindhub OS.
"""
from django.db import models
from django.utils import timezone


class TipoValidacao(models.TextChoices):
    """Tipos de validação para Steps."""
    FOTO = 'FOTO', 'Foto'
    FORMULARIO = 'FORMULARIO', 'Formulário'
    TEXTO = 'TEXTO', 'Texto'


class StatusProgresso(models.TextChoices):
    """Status do progresso do aluno em cada Step."""
    BLOQUEADO = 'BLOQUEADO', 'Bloqueado'
    EM_ANDAMENTO = 'EM_ANDAMENTO', 'Em Andamento'
    PENDENTE_VALIDACAO = 'PENDENTE_VALIDACAO', 'Pendente Validação'
    CONCLUIDO = 'CONCLUIDO', 'Concluído'


class Mundo(models.Model):
    """
    Representa um Mundo na trilha (1 a 6).
    Cada Mundo pertence a um aluno específico ou é um template base (aluno=null).
    """
    aluno = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.CASCADE,
        related_name='mundos_personalizados',
        null=True,
        blank=True,
        help_text="Aluno dono desta trilha. Null = Trilha Base (template)"
    )
    numero = models.IntegerField(help_text="Número do mundo (1-6)")
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    objetivo = models.TextField(blank=True, help_text="Objetivo do mundo")
    icone = models.CharField(
        max_length=50, 
        default='chef',
        help_text="Nome do ícone (chef, cash-register, chart-line, trophy, etc)"
    )
    cor_primaria = models.CharField(max_length=7, default='#e30613', help_text="Cor hex do mundo")
    ativo = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['numero']
        verbose_name = 'Mundo'
        verbose_name_plural = 'Mundos'
        # Unique por aluno + numero (permite mesmo numero para alunos diferentes)
        unique_together = ['aluno', 'numero']
    
    def __str__(self):
        return f"Mundo {self.numero}: {self.nome}"
    
    @property
    def total_steps(self):
        return self.steps.count()


class Step(models.Model):
    """
    Representa um Step (etapa) dentro de um Mundo.
    Cada Step tem instruções e um tipo de validação.
    """
    mundo = models.ForeignKey(
        Mundo, 
        on_delete=models.CASCADE, 
        related_name='steps'
    )
    ordem = models.IntegerField(help_text="Ordem do step dentro do mundo")
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    instrucoes = models.TextField(help_text="Instruções detalhadas para o aluno")
    tipo_validacao = models.CharField(
        max_length=20, 
        choices=TipoValidacao.choices,
        default=TipoValidacao.FOTO
    )
    config_formulario = models.JSONField(
        null=True,
        blank=True,
        help_text="Perguntas do formulário: [{pergunta: str, obrigatoria: bool}]"
    )
    pontos = models.IntegerField(default=10, help_text="Pontos ao completar este step")
    ativo = models.BooleanField(default=True)
    
    # Coordenadas do mapa (0-100%)
    pos_x = models.IntegerField(default=0, help_text="Posição Horizontal (%)")
    pos_y = models.IntegerField(default=0, help_text="Posição Vertical (%)")
    
    class Meta:
        ordering = ['mundo__numero', 'ordem']
        verbose_name = 'Step'
        verbose_name_plural = 'Steps'
    
    def __str__(self):
        return f"M{self.mundo.numero} - Step {self.ordem}: {self.titulo}"


class ProgressoAluno(models.Model):
    """
    Registra o progresso de cada aluno em cada Step.
    """
    aluno = models.ForeignKey(
        'usuarios.Usuario', 
        on_delete=models.CASCADE,
        related_name='progressos'
    )
    step = models.ForeignKey(
        Step, 
        on_delete=models.CASCADE,
        related_name='progressos'
    )
    status = models.CharField(
        max_length=25, 
        choices=StatusProgresso.choices, 
        default=StatusProgresso.BLOQUEADO
    )
    data_inicio = models.DateTimeField(null=True, blank=True)
    data_conclusao = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['aluno', 'step']
        verbose_name = 'Progresso do Aluno'
        verbose_name_plural = 'Progressos dos Alunos'
    
    def __str__(self):
        return f"{self.aluno.email} - {self.step} ({self.status})"
    
    def iniciar(self):
        """Marca o step como em andamento."""
        self.status = StatusProgresso.EM_ANDAMENTO
        self.data_inicio = timezone.now()
        self.save()
    
    def enviar_para_validacao(self):
        """Marca o step como pendente de validação."""
        self.status = StatusProgresso.PENDENTE_VALIDACAO
        self.save()
    
    def concluir(self):
        """Marca o step como concluído."""
        self.status = StatusProgresso.CONCLUIDO
        self.data_conclusao = timezone.now()
        self.save()


class Submissao(models.Model):
    """
    Guarda as submissões dos alunos (fotos, textos, formulários).
    """
    progresso = models.ForeignKey(
        ProgressoAluno, 
        on_delete=models.CASCADE, 
        related_name='submissoes'
    )
    arquivo = models.FileField(
        upload_to='submissoes/%Y/%m/', 
        null=True, 
        blank=True,
        help_text="Arquivo enviado (foto ou documento)"
    )
    resposta_texto = models.TextField(blank=True, help_text="Resposta em texto")
    resposta_formulario = models.JSONField(
        null=True, 
        blank=True,
        help_text="Respostas do formulário em JSON"
    )
    data_envio = models.DateTimeField(auto_now_add=True)
    
    # Validação pelo Monitor
    validado_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validacoes'
    )
    data_validacao = models.DateTimeField(null=True, blank=True)
    aprovado = models.BooleanField(null=True, help_text="null=pendente, True=aprovado, False=reprovado")
    feedback = models.TextField(blank=True, help_text="Feedback do monitor")
    
    class Meta:
        ordering = ['-data_envio']
        verbose_name = 'Submissão'
        verbose_name_plural = 'Submissões'
    
    def __str__(self):
        status = "Pendente" if self.aprovado is None else ("Aprovado" if self.aprovado else "Reprovado")
        return f"Submissão {self.id} - {self.progresso.aluno.email} ({status})"
    
    def aprovar(self, monitor, feedback=''):
        """Aprova a submissão e avança o aluno."""
        self.aprovado = True
        self.validado_por = monitor
        self.data_validacao = timezone.now()
        self.feedback = feedback
        self.save()
        self.progresso.concluir()
    
    def reprovar(self, monitor, feedback):
        """Reprova a submissão com feedback."""
        self.aprovado = False
        self.validado_por = monitor
        self.data_validacao = timezone.now()
        self.feedback = feedback
        self.save()
        # Volta para em andamento para o aluno tentar novamente
        self.progresso.status = StatusProgresso.EM_ANDAMENTO
        self.progresso.save()


class NotaSaude(models.Model):
    """
    Registro histórico da nota de saúde do aluno (1-5).
    Usado para colorir o nó no Graph View.
    """
    aluno = models.ForeignKey(
        'usuarios.Usuario', 
        on_delete=models.CASCADE, 
        related_name='notas_saude'
    )
    nota = models.IntegerField(
        help_text="Nota de 1 (vermelho) a 5 (verde)"
    )
    data = models.DateTimeField(auto_now_add=True)
    automatica = models.BooleanField(
        default=False, 
        help_text="True se gerada automaticamente por inatividade"
    )
    observacao = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-data']
        verbose_name = 'Nota de Saúde'
        verbose_name_plural = 'Notas de Saúde'
    
    def __str__(self):
        tipo = "Auto" if self.automatica else "Manual"
        return f"{self.aluno.email}: Nota {self.nota} ({tipo}) - {self.data.strftime('%d/%m/%Y')}"
    
    @classmethod
    def get_nota_atual(cls, aluno):
        """Retorna a nota mais recente do aluno ou 3 (padrão)."""
        ultima = cls.objects.filter(aluno=aluno).first()
        return ultima.nota if ultima else 3
    
    @classmethod
    def get_cor_nota(cls, nota):
        """Retorna a cor hex baseada na nota."""
        cores = {
            5: '#28a745',  # Verde
            4: '#7cb342',  # Verde Lima
            3: '#ffc107',  # Amarelo
            2: '#ff9800',  # Laranja
            1: '#dc3545',  # Vermelho
        }
        return cores.get(nota, '#6c757d')  # Cinza como fallback
