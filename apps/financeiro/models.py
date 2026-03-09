from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ContratoStatus(models.TextChoices):
    ATIVO = "ATIVO", "Ativo"
    CANCELADO = "CANCELADO", "Cancelado"


class MetodoPagamentoContrato(models.TextChoices):
    PIX = "PIX", "Pix"
    BOLETO = "BOLETO", "Boleto"
    CARTAO = "CARTAO", "Cartao"
    TRANSFERENCIA = "TRANSFERENCIA", "Transferencia"
    DINHEIRO = "DINHEIRO", "Dinheiro"


class TipoParcela(models.TextChoices):
    ENTRADA = "ENTRADA", "Entrada"
    RECORRENTE = "RECORRENTE", "Recorrente"


class OrigemParcela(models.TextChoices):
    CADASTRO = "CADASTRO", "Cadastro"
    RENEGOCIACAO = "RENEGOCIACAO", "Renegociacao"


class TipoRenegociacao(models.TextChoices):
    ADIAR = "ADIAR", "Adiar"
    QUEBRAR = "QUEBRAR", "Quebrar"


class ParcelaStatus(models.TextChoices):
    PAGO = "PAGO", "Pago"
    PENDENTE = "PENDENTE", "Pendente"
    ATRASADO = "ATRASADO", "Atrasado"
    INADIMPLENTE = "INADIMPLENTE", "Inadimplente"
    CANCELADA_RENEGOCIACAO = "CANCELADA_RENEGOCIACAO", "Cancelada (renegociacao)"
    CANCELADO = "CANCELADO", "Cancelado"


class Contrato(models.Model):
    aluno = models.OneToOneField(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="contrato",
        limit_choices_to={"role": "ALUNO"},
        help_text="Aluno vinculado a este contrato",
    )
    valor_total_negociado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Valor total negociado no contrato",
    )
    data_assinatura = models.DateField(default=timezone.now)
    observacoes_gerais = models.TextField(blank=True)
    metodo_pagamento = models.CharField(
        max_length=20,
        choices=MetodoPagamentoContrato.choices,
        default=MetodoPagamentoContrato.PIX,
    )
    status = models.CharField(
        max_length=20,
        choices=ContratoStatus.choices,
        default=ContratoStatus.ATIVO,
    )
    contrato_assinado = models.FileField(upload_to="contratos_assinados/", null=True, blank=True)
    comprovante_entrada = models.FileField(upload_to="comprovantes_entrada/", null=True, blank=True)
    asaas_customer_id = models.CharField(max_length=80, blank=True)
    criado_por = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contratos_criados",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Contrato"
        verbose_name_plural = "Contratos"

    def __str__(self):
        return f"Contrato {self.id} - {self.aluno.email}"

    def clean(self):
        if self.aluno and not self.aluno.is_aluno:
            raise ValidationError("Apenas usuarios com role ALUNO podem ter contrato.")

    def parcelas_ordenadas(self):
        return self.parcelas.filter(ativa=True).order_by("data_vencimento", "numero")

    def parcelas_por_status(self, status: str, referencia=None):
        return [
            parcela
            for parcela in self.parcelas_ordenadas()
            if parcela.get_status(referencia) == status
        ]

    def possui_status(self, status: str, referencia=None) -> bool:
        return any(
            parcela.get_status(referencia) == status
            for parcela in self.parcelas_ordenadas()
        )

    def parcela_referencia(self, referencia=None):
        if self.status == ContratoStatus.CANCELADO:
            return self.parcelas_ordenadas().first()

        prioridades = [
            ParcelaStatus.INADIMPLENTE,
            ParcelaStatus.ATRASADO,
            ParcelaStatus.PENDENTE,
        ]
        for status in prioridades:
            parcelas = self.parcelas_por_status(status, referencia)
            if parcelas:
                return parcelas[0]

        return self.parcelas_ordenadas().last()


class Parcela(models.Model):
    contrato = models.ForeignKey(
        Contrato,
        on_delete=models.CASCADE,
        related_name="parcelas",
    )
    numero = models.IntegerField(help_text="Número da parcela (1, 2, 3...)")
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data_vencimento = models.DateField()
    data_pagamento = models.DateField(
        null=True,
        blank=True,
        help_text="Preencha quando a parcela for paga",
    )
    link_pagamento_ou_pix = models.CharField(
        max_length=500,
        blank=True,
        help_text="Link de cobrança ou chave PIX",
    )
    comprovante = models.FileField(
        upload_to="comprovantes_pagamento/",
        null=True,
        blank=True,
    )
    observacoes = models.TextField(blank=True)
    tipo_parcela = models.CharField(max_length=20, choices=TipoParcela.choices, default=TipoParcela.RECORRENTE)
    origem = models.CharField(max_length=20, choices=OrigemParcela.choices, default=OrigemParcela.CADASTRO)
    asaas_payment_id = models.CharField(max_length=80, blank=True)
    asaas_invoice_url = models.URLField(blank=True)
    sincronizada_asaas_em = models.DateTimeField(null=True, blank=True)
    ativa = models.BooleanField(default=True)
    parcela_origem = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parcelas_derivadas",
    )
    ja_renegociada = models.BooleanField(default=False)

    class Meta:
        ordering = ["data_vencimento", "numero"]
        verbose_name = "Parcela"
        verbose_name_plural = "Parcelas"
        unique_together = ["contrato", "numero"]

    def __str__(self):
        return f"Parcela {self.numero} - Contrato {self.contrato.id}"

    def get_status(self, referencia=None) -> str:
        referencia = referencia or timezone.localdate()

        if self.contrato.status == ContratoStatus.CANCELADO:
            return ParcelaStatus.CANCELADO
        if not self.ativa:
            if self.ja_renegociada:
                return ParcelaStatus.CANCELADA_RENEGOCIACAO
            return ParcelaStatus.CANCELADO
        if self.data_pagamento:
            return ParcelaStatus.PAGO
        if referencia <= self.data_vencimento:
            return ParcelaStatus.PENDENTE

        dias = (referencia - self.data_vencimento).days
        if 1 <= dias <= 7:
            return ParcelaStatus.ATRASADO
        return ParcelaStatus.INADIMPLENTE

    def dias_atraso(self, referencia=None) -> int:
        if self.data_pagamento or not self.ativa or self.contrato.status == ContratoStatus.CANCELADO:
            return 0

        referencia = referencia or timezone.localdate()
        return max((referencia - self.data_vencimento).days, 0)

    @property
    def status_dinamico(self) -> str:
        return self.get_status()


class PropostaRenegociacao(models.Model):
    contrato = models.ForeignKey(
        Contrato,
        on_delete=models.CASCADE,
        related_name="propostas_renegociacao",
    )
    parcela_alvo = models.ForeignKey(
        Parcela,
        on_delete=models.CASCADE,
        related_name="propostas_renegociacao",
    )
    tipo_renegociacao = models.CharField(max_length=20, choices=TipoRenegociacao.choices)
    dados_fatiamento = models.JSONField(null=True, blank=True)
    criada_por = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="propostas_renegociacao_criadas",
    )
    observacoes = models.TextField(blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "Proposta de renegociacao"
        verbose_name_plural = "Propostas de renegociacao"

    def __str__(self):
        return f"Renegociacao {self.get_tipo_renegociacao_display()} - Parcela {self.parcela_alvo_id}"

    def clean(self):
        if self.tipo_renegociacao == TipoRenegociacao.QUEBRAR and not self.dados_fatiamento:
            raise ValidationError({"dados_fatiamento": "Fatiamento obrigatorio para renegociacao do tipo QUEBRAR."})
