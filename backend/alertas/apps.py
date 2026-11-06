from django.apps import AppConfig


class AlertasConfig(AppConfig):
    name = 'alertas'
    verbose_name = 'Alertas de segurança (Telegram)'

    def ready(self):
        from . import sinais  # noqa: F401  (registra os receivers)
