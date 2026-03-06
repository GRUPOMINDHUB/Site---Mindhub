from django.contrib import admin

from .models import (
    EnvioOnboarding,
    NotificacaoInterna,
    PerfilEmpresarial,
    PropostaFinanceira,
    PropostaFinanceiraParcela,
)


@admin.register(PerfilEmpresarial)
class PerfilEmpresarialAdmin(admin.ModelAdmin):
    list_display = ("aluno", "nome_empresa", "nicho", "monitor_responsavel_snapshot", "atualizado_em")
    search_fields = ("aluno__nome", "aluno__email", "nome_empresa", "cnpj")
    list_filter = ("nicho",)


class PropostaFinanceiraParcelaInline(admin.TabularInline):
    model = PropostaFinanceiraParcela
    extra = 0


@admin.register(PropostaFinanceira)
class PropostaFinanceiraAdmin(admin.ModelAdmin):
    list_display = ("aluno", "criada_por", "status", "criada_em", "aprovada_por")
    search_fields = ("aluno__nome", "aluno__email", "criada_por__nome", "criada_por__email")
    list_filter = ("status", "criada_em")
    inlines = [PropostaFinanceiraParcelaInline]


@admin.register(NotificacaoInterna)
class NotificacaoInternaAdmin(admin.ModelAdmin):
    list_display = ("destinatario", "tipo", "titulo", "lida", "criada_em")
    search_fields = ("destinatario__nome", "destinatario__email", "titulo", "mensagem")
    list_filter = ("tipo", "lida")


@admin.register(EnvioOnboarding)
class EnvioOnboardingAdmin(admin.ModelAdmin):
    list_display = ("aluno", "canal", "destinatario", "status", "criado_em")
    search_fields = ("aluno__nome", "aluno__email", "destinatario")
    list_filter = ("canal", "status")
