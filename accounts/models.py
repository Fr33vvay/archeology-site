"""Секреты email: ciphertext + hash (в auth_user.email / account_emailaddress.email — hash)."""

from django.conf import settings
from django.db import models


class UserEmailSecret(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_secret",
        verbose_name="Пользователь",
    )
    email_hash = models.CharField("Хеш email", max_length=64, unique=True, db_index=True)
    ciphertext = models.TextField("Шифротекст")

    class Meta:
        verbose_name = "Секрет email пользователя"
        verbose_name_plural = "Секреты email пользователей"

    def __str__(self):
        return f"email secret user={self.user_id}"


class AddressEmailSecret(models.Model):
    address = models.OneToOneField(
        "account.EmailAddress",
        on_delete=models.CASCADE,
        related_name="email_secret",
        verbose_name="Адрес allauth",
    )
    email_hash = models.CharField("Хеш email", max_length=64, unique=True, db_index=True)
    ciphertext = models.TextField("Шифротекст")

    class Meta:
        verbose_name = "Секрет email адреса"
        verbose_name_plural = "Секреты email адресов"

    def __str__(self):
        return f"email secret address={self.address_id}"
