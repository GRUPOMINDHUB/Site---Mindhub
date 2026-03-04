from django.apps import AppConfig


class FinanceiroConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.financeiro'

    def ready(self):
        import apps.financeiro.signals
