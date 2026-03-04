from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from datetime import date

class Contrato(models.Model):
    """
    Modelo que representa o contrato financeiro de um aluno.
    """
    STATUS_CHOICES = [
        ('ATIVO', 'Ativo'),
        ('CANCELADO', 'Cancelado'),
    ]

    aluno = models.OneToOneField(
        'usuarios.Usuario',
        on_delete=models.CASCADE,
        related_name='contrato',
        limit_choices_to={'role': 'ALUNO'},
        help_text="Aluno vinculado a este contrato"
    )
    valor_total_negociado = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Valor total negociado no contrato"
    )
    data_assinatura = models.DateField(default=timezone.now)
    observacoes_gerais = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='ATIVO'
    )
    
    class Meta:
        verbose_name = 'Contrato'
        verbose_name_plural = 'Contratos'
        
    def __str__(self):
        return f"Contrato {self.id} - {self.aluno.email}"


class Parcela(models.Model):
    """
    Modelo que representa uma parcela de um contrato.
    """
    contrato = models.ForeignKey(
        Contrato,
        on_delete=models.CASCADE,
        related_name='parcelas'
    )
    numero = models.IntegerField(help_text="Número da parcela (1, 2, 3...)")
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data_vencimento = models.DateField()
    data_pagamento = models.DateField(
        null=True, 
        blank=True,
        help_text="Preencha quando a parcela for paga"
    )
    link_pagamento_ou_pix = models.CharField(
        max_length=500, 
        blank=True,
        help_text="Link de cobrança ou chave PIX"
    )
    comprovante = models.FileField(
        upload_to='comprovantes_pagamento/',
        null=True,
        blank=True
    )
    observacoes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['data_vencimento', 'numero']
        verbose_name = 'Parcela'
        verbose_name_plural = 'Parcelas'
        unique_together = ['contrato', 'numero'] # Não pode ter duas parcelas número 1 pro mesmo contrato
        
    def __str__(self):
        return f"Parcela {self.numero} - Contrato {self.contrato.id}"

    @property
    def status_dinamico(self):
        """
        Calcula o status da parcela dinamicamente baseado nas datas e status do contrato.
        """
        if self.contrato.status == 'CANCELADO':
            return 'CANCELADO'
            
        if self.data_pagamento is not None:
            return 'PAGO'
            
        hoje = timezone.localtime(timezone.now()).date()
        
        if hoje <= self.data_vencimento:
            return 'PENDENTE'
            
        dias_atraso = (hoje - self.data_vencimento).days
        
        if 1 <= dias_atraso <= 7:
            return 'ATRASADO'
            
        return 'INADIMPLENTE'
