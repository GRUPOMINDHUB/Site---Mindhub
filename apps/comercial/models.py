from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.usuarios.models import RoleChoices


class NichoEmpresa(models.TextChoices):
    RESTAURANTE = "RESTAURANTE", "Restaurante"
    CAFE = "CAFE", "Cafe"
    LANCHONETE = "LANCHONETE", "Lanchonete"
    DELIVERY = "DELIVERY", "Delivery"
    PADARIA = "PADARIA", "Padaria"
    OUTRO = "OUTRO", "Outro"


class DificuldadeDiagnostico(models.TextChoices):
    ESTOQUE = "ESTOQUE", "Estoque"
    FINANCEIRO = "FINANCEIRO", "Financeiro"
    PRECIFICACAO = "PRECIFICACAO", "Precificacao"
    GESTAO_PESSOAS = "GESTAO_PESSOAS", "Gestao de Pessoas"
    CMV = "CMV", "CMV"
    FICHA_TECNICA = "FICHA_TECNICA", "Ficha Tecnica"


class TipoNotificacao(models.TextChoices):
    ONBOARDING = "ONBOARDING", "Onboarding"
    PROPOSTA_FINANCEIRA = "PROPOSTA_FINANCEIRA", "Proposta Financeira"
    SISTEMA = "SISTEMA", "Sistema"


class StatusPropostaFinanceira(models.TextChoices):
    PENDENTE = "PENDENTE", "Pendente"
    APROVADA = "APROVADA", "Aprovada"
    REJEITADA = "REJEITADA", "Rejeitada"


class CanalOnboarding(models.TextChoices):
    EMAIL = "EMAIL", "E-mail"
    WHATSAPP = "WHATSAPP", "WhatsApp"


class StatusEnvioOnboarding(models.TextChoices):
    PREPARADO = "PREPARADO", "Preparado"
    ENVIADO = "ENVIADO", "Enviado"
    ERRO = "ERRO", "Erro"


class PerfilEmpresarial(models.Model):
    aluno = models.OneToOneField(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="perfil_empresarial",
        limit_choices_to={"role": RoleChoices.ALUNO},
    )
    nome_empresa = models.CharField(max_length=200)
    telefone_empresa = models.CharField(max_length=20, blank=True)
    cnpj = models.CharField(max_length=18, blank=True)
    endereco = models.CharField(max_length=255, blank=True)
    nicho = models.CharField(max_length=30, choices=NichoEmpresa.choices, default=NichoEmpresa.OUTRO)
    nome_representante = models.CharField(max_length=200, blank=True)
    cpf_representante = models.CharField(max_length=14, blank=True)
    dificuldades = models.JSONField(default=list, blank=True)
    observacoes = models.TextField(blank=True)
    monitor_responsavel_snapshot = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfis_empresariais_snapshot",
        limit_choices_to={"role": RoleChoices.MONITOR},
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Perfil empresarial"
        verbose_name_plural = "Perfis empresariais"

    def __str__(self):
        return self.nome_empresa or self.aluno.email

    def clean(self):
        if self.aluno and not self.aluno.is_aluno:
            raise ValidationError("Perfil empresarial so pode ser vinculado a aluno.")

        escolhas_validas = {choice[0] for choice in DificuldadeDiagnostico.choices}
        invalidas = [item for item in self.dificuldades if item not in escolhas_validas]
        if invalidas:
            raise ValidationError({"dificuldades": "Diagnostico contem opcoes invalidas."})


class NotificacaoInterna(models.Model):
    destinatario = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="notificacoes_recebidas",
    )
    tipo = models.CharField(max_length=30, choices=TipoNotificacao.choices, default=TipoNotificacao.SISTEMA)
    titulo = models.CharField(max_length=255)
    mensagem = models.TextField()
    url_destino = models.CharField(max_length=255, blank=True)
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notificacoes_relacionadas",
        limit_choices_to={"role": RoleChoices.ALUNO},
    )
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)
    lida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["lida", "-criada_em"]
        verbose_name = "Notificacao interna"
        verbose_name_plural = "Notificacoes internas"

    def marcar_como_lida(self):
        if not self.lida:
            self.lida = True
            self.lida_em = timezone.now()
            self.save(update_fields=["lida", "lida_em"])


class PropostaFinanceira(models.Model):
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="propostas_financeiras",
        limit_choices_to={"role": RoleChoices.ALUNO},
    )
    contrato = models.ForeignKey(
        "financeiro.Contrato",
        on_delete=models.CASCADE,
        related_name="propostas_financeiras",
    )
    criada_por = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="propostas_financeiras_criadas",
    )
    status = models.CharField(max_length=20, choices=StatusPropostaFinanceira.choices, default=StatusPropostaFinanceira.PENDENTE)
    motivo = models.TextField()
    observacao_monitor = models.TextField(blank=True)
    observacao_admin = models.TextField(blank=True)
    aprovada_por = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="propostas_financeiras_aprovadas",
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    aprovada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "Proposta financeira"
        verbose_name_plural = "Propostas financeiras"

    def clean(self):
        if self.criada_por and not self.criada_por.is_monitor:
            raise ValidationError("A proposta financeira deve ser criada por monitor.")
        if self.aluno and not self.aluno.is_aluno:
            raise ValidationError("Proposta financeira so pode ser vinculada a aluno.")


class PropostaFinanceiraParcela(models.Model):
    proposta = models.ForeignKey(
        PropostaFinanceira,
        on_delete=models.CASCADE,
        related_name="parcelas_propostas",
    )
    numero = models.IntegerField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data_vencimento = models.DateField()
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ["numero"]
        unique_together = [("proposta", "numero")]
        verbose_name = "Parcela proposta"
        verbose_name_plural = "Parcelas propostas"


class EnvioOnboarding(models.Model):
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="envios_onboarding",
        limit_choices_to={"role": RoleChoices.ALUNO},
    )
    canal = models.CharField(max_length=20, choices=CanalOnboarding.choices)
    destinatario = models.CharField(max_length=255)
    mensagem = models.TextField()
    status = models.CharField(max_length=20, choices=StatusEnvioOnboarding.choices, default=StatusEnvioOnboarding.PREPARADO)
    erro = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    enviado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Envio de onboarding"
        verbose_name_plural = "Envios de onboarding"
