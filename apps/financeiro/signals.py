from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Contrato, Parcela
from .services import sincronizar_nota_saude_financeira


@receiver(post_save, sender=Parcela)
def atualizar_saude_apos_salvar_parcela(sender, instance, **kwargs):
    sincronizar_nota_saude_financeira(instance.contrato.aluno)


@receiver(post_save, sender=Contrato)
def atualizar_saude_apos_salvar_contrato(sender, instance, **kwargs):
    sincronizar_nota_saude_financeira(instance.aluno)
