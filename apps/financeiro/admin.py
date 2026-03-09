from django.contrib import admin

from .models import Contrato, Parcela, PropostaRenegociacao


class ParcelaInline(admin.TabularInline):
    model = Parcela
    extra = 1
    fields = (
        "numero",
        "tipo_parcela",
        "valor",
        "data_vencimento",
        "data_pagamento",
        "ativa",
        "ja_renegociada",
        "parcela_origem",
        "status_dinamico",
        "link_pagamento_ou_pix",
        "asaas_invoice_url",
    )
    readonly_fields = ("status_dinamico",)


@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ("id", "aluno", "valor_total_negociado", "data_assinatura", "metodo_pagamento", "status", "asaas_customer_id")
    list_filter = ("status", "metodo_pagamento", "data_assinatura")
    search_fields = ("aluno__nome", "aluno__email")
    inlines = [ParcelaInline]


@admin.register(Parcela)
class ParcelaAdmin(admin.ModelAdmin):
    list_display = (
        "contrato",
        "numero",
        "tipo_parcela",
        "valor",
        "data_vencimento",
        "data_pagamento",
        "ativa",
        "ja_renegociada",
        "parcela_origem",
        "status_dinamico",
    )
    list_filter = ("tipo_parcela", "data_vencimento", "data_pagamento", "ativa", "ja_renegociada")
    search_fields = ("contrato__aluno__nome", "contrato__aluno__email")
    readonly_fields = ("status_dinamico",)


@admin.register(PropostaRenegociacao)
class PropostaRenegociacaoAdmin(admin.ModelAdmin):
    list_display = ("id", "contrato", "parcela_alvo", "tipo_renegociacao", "criada_por", "criada_em")
    list_filter = ("tipo_renegociacao", "criada_em")
    search_fields = ("contrato__aluno__nome", "contrato__aluno__email")
