from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Parcela

@receiver(post_save, sender=Parcela)
def atualizar_saude_aluno_inadimplente(sender, instance, created, **kwargs):
    """
    Signal disparado sempre que uma Parcela for salva ou criada.
    Verifica se o aluno possui alguma parcela ATRASADA ou INADIMPLENTE.
    Em caso positivo, força (ou cria) uma Nota de Saúde = 1 (Crítico).
    """
    contrato = instance.contrato
    if contrato.status == 'CANCELADO':
        return
        
    aluno = contrato.aluno
    
    # Busca todas as parcelas do contrato
    parcelas = contrato.parcelas.all()
    
    tem_problema = False
    for p in parcelas:
        status = p.status_dinamico
        if status in ['ATRASADO', 'INADIMPLENTE']:
            tem_problema = True
            break
            
    if tem_problema:
        # Força nota de saúde do aluno para 1
        from apps.trilha.models import NotaSaude
        
        # Opcional: verificar a última nota para não ficar cirando milhares de notas 1 seguidas.
        ultima_nota = NotaSaude.objects.filter(aluno=aluno).order_by('-data').first()
        
        if not ultima_nota or ultima_nota.nota != 1:
            NotaSaude.objects.create(
                aluno=aluno,
                nota=1,
                automatica=True,
                observacao="[FINANCEIRO] Nota reduzida automaticamente devido a parcela atrasada ou inadimplente."
            )
