from django.contrib import admin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('email', 'nome', 'role', 'telefone', 'pode_aprovar_financeiro', 'ativo', 'data_cadastro')
    search_fields = ('email', 'nome', 'telefone')
    list_filter = ('role', 'ativo', 'pode_aprovar_financeiro')
    list_editable = ('role', 'pode_aprovar_financeiro', 'ativo')
    readonly_fields = ('data_cadastro',)
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('email', 'nome', 'foto', 'telefone')
        }),
        ('Acesso', {
            'fields': ('senha', 'role', 'pode_aprovar_financeiro', 'ativo')
        }),
        ('Datas', {
            'fields': ('data_cadastro',),
            'classes': ('collapse',)
        }),
    )
