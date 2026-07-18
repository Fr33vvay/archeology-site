import logging

from allauth.account.adapter import DefaultAccountAdapter
from django import forms

from accounts.email_domains import is_russian_email

logger = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):
    def clean_email(self, email):
        email = super().clean_email(email)
        if email and not is_russian_email(email):
            raise forms.ValidationError(
                "Регистрация доступна только с российской почты "
                "(например Yandex, Mail.ru, Rambler) или адреса в зоне .ru."
            )
        return email

    def send_mail(self, template_prefix, email, context):
        """Не роняем регистрацию, если почтовый сервер недоступен."""
        try:
            return super().send_mail(template_prefix, email, context)
        except OSError:
            logger.exception("Не удалось отправить письмо на %s", email)
            return None
