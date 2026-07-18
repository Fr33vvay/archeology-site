import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model

from accounts.email_domains import is_russian_email

logger = logging.getLogger(__name__)
User = get_user_model()


class AccountAdapter(DefaultAccountAdapter):
    def clean_email(self, email):
        email = super().clean_email(email)
        if email and not is_russian_email(email):
            raise forms.ValidationError(
                "Регистрация доступна только с российской почты "
                "(например Yandex, Mail.ru, Rambler) или адреса в зоне .ru."
            )
        # Незавершённую регистрацию с тем же адресом можно начать заново
        if email:
            self._purge_pending_signup(email)
        return email

    def _purge_pending_signup(self, email: str) -> None:
        pending = EmailAddress.objects.filter(
            email__iexact=email, verified=False
        ).select_related("user")
        for addr in pending:
            user = addr.user
            if user.is_active or user.is_staff or user.is_superuser:
                continue
            user.delete()

    def save_user(self, request, user, form, commit=True):
        """При обязательном подтверждении почты — неактивен, пока не кликнет ссылку."""
        user = super().save_user(request, user, form, commit=False)
        if getattr(settings, "ACCOUNT_EMAIL_VERIFICATION", "none") == "mandatory":
            user.is_active = False
        if commit:
            user.save()
        return user

    def pre_login(
        self,
        request,
        user,
        *,
        email_verification,
        signal_kwargs,
        email,
        signup,
        redirect_url,
    ):
        # Иначе allauth сразу шлёт на «Аккаунт неактивен» и не доходит до письма.
        if (
            not user.is_active
            and signup
            and getattr(settings, "ACCOUNT_EMAIL_VERIFICATION", "none") == "mandatory"
        ):
            return None
        return super().pre_login(
            request,
            user,
            email_verification=email_verification,
            signal_kwargs=signal_kwargs,
            email=email,
            signup=signup,
            redirect_url=redirect_url,
        )

    def confirm_email(self, request, email_address):
        ok = super().confirm_email(request, email_address)
        if ok:
            user = email_address.user
            if not user.is_active:
                user.is_active = True
                user.save(update_fields=["is_active"])
        return ok

    def send_mail(self, template_prefix, email, context):
        """Не роняем регистрацию, если почтовый сервер недоступен."""
        try:
            return super().send_mail(template_prefix, email, context)
        except OSError:
            logger.exception("Не удалось отправить письмо на %s", email)
            return None
