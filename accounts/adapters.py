from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django import forms

from accounts.email_domains import is_russian_email


class AccountAdapter(DefaultAccountAdapter):
    def clean_email(self, email):
        email = super().clean_email(email)
        if email and not is_russian_email(email):
            raise forms.ValidationError(
                "Регистрация доступна только с российской почты "
                "(например Yandex, Mail.ru, Rambler) или адреса в зоне .ru."
            )
        return email


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """VK и другие российские провайдеры — без проверки домена почты VK."""

    def is_open_for_signup(self, request, sociallogin):
        return True
