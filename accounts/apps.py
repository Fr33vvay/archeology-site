from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Аккаунты"

    def ready(self):
        from accounts.encryption_hooks import install_email_encryption_hooks

        install_email_encryption_hooks()
