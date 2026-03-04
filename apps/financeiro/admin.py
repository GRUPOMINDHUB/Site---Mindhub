from django.contrib import admin
from .models import Contrato, Parcela

class ParcelaInline(admin.TabularInline):
    model = Parcela
    extra = 1
    fields = ('numero', 'valor', 'data_vencimento', 'data_pagamento', 'status_dinamico', 'link_pagamento_ou_pix')
    readonly_fields = ('status_dinamico',)

@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ('id', 'aluno', 'valor_total_negociado', 'data_assinatura', 'status')
    list_filter = ('status', 'data_assinatura')
    search_fields = ('aluno__nome', 'aluno__email')
    inlines = [ParcelaInline]

@admin.register(Parcela)
class ParcelaAdmin(admin.ModelAdmin):
    list_display = ('contrato', 'numero', 'valor', 'data_vencimento', 'data_pagamento', 'status_dinamico')
    list_filter = ('data_vencimento', 'data_pagamento')
    search_fields = ('contrato__aluno__nome', 'contrato__aluno__email')
    readonly_fields = ('status_dinamico',)
