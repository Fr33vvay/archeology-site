"""Сигналы и патчи ORM: прозрачное шифрование User.email и EmailAddress.email."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_init, post_save, pre_save

from accounts.email_crypto import (
    decrypt_email,
    encrypt_email,
    hash_email,
    is_email_hash,
    normalize_email,
)
from accounts.models import AddressEmailSecret, UserEmailSecret

_PATCHED = False


def _decrypt_user(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        secret = instance.email_secret
    except UserEmailSecret.DoesNotExist:
        return
    try:
        instance.__dict__["email"] = decrypt_email(secret.ciphertext)
    except ValueError:
        pass


def _decrypt_address(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        secret = instance.email_secret
    except AddressEmailSecret.DoesNotExist:
        return
    try:
        instance.__dict__["email"] = decrypt_email(secret.ciphertext)
    except ValueError:
        pass


def _user_pre_save(sender, instance, **kwargs):
    email = instance.__dict__.get("email") or ""
    if not email or is_email_hash(email):
        instance._pending_email_plain = None
        return
    plain = normalize_email(email)
    instance._pending_email_plain = plain
    instance.__dict__["email"] = hash_email(plain)


def _user_post_save(sender, instance, **kwargs):
    plain = getattr(instance, "_pending_email_plain", None)
    if not plain:
        return
    UserEmailSecret.objects.update_or_create(
        user=instance,
        defaults={
            "email_hash": hash_email(plain),
            "ciphertext": encrypt_email(plain),
        },
    )
    instance.__dict__["email"] = plain
    instance._pending_email_plain = None


def _address_pre_save(sender, instance, **kwargs):
    email = instance.__dict__.get("email") or ""
    if not email or is_email_hash(email):
        instance._pending_email_plain = None
        return
    plain = normalize_email(email)
    instance._pending_email_plain = plain
    instance.__dict__["email"] = hash_email(plain)


def _address_post_save(sender, instance, **kwargs):
    plain = getattr(instance, "_pending_email_plain", None)
    if not plain:
        return
    AddressEmailSecret.objects.update_or_create(
        address=instance,
        defaults={
            "email_hash": hash_email(plain),
            "ciphertext": encrypt_email(plain),
        },
    )
    instance.__dict__["email"] = plain
    instance._pending_email_plain = None


def _rewrite_email_kwargs(kwargs: dict) -> dict:
    out = dict(kwargs)
    for key in list(out):
        field = key.split("__", 1)[0]
        if field != "email":
            continue
        lookup = key[len("email") :]  # "", "__iexact", "__exact", ...
        if lookup not in ("", "__iexact", "__exact", "__iExact"):
            continue
        val = out.pop(key)
        if val is None:
            out["email"] = val
        elif is_email_hash(str(val)):
            out["email"] = str(val)
        else:
            out["email"] = hash_email(str(val))
    return out


def _patch_queryset(manager):
    qs = manager.get_queryset()
    qs_class = qs.__class__
    if getattr(qs_class, "_email_hash_patched", False):
        return
    original_filter = qs_class.filter
    original_exclude = qs_class.exclude

    def filter(self, *args, **kwargs):
        return original_filter(self, *args, **_rewrite_email_kwargs(kwargs))

    def exclude(self, *args, **kwargs):
        return original_exclude(self, *args, **_rewrite_email_kwargs(kwargs))

    qs_class.filter = filter
    qs_class.exclude = exclude
    qs_class._email_hash_patched = True


def install_email_encryption_hooks():
    global _PATCHED
    if _PATCHED:
        return
    User = get_user_model()
    from allauth.account.models import EmailAddress

    post_init.connect(_decrypt_user, sender=User, weak=False)
    pre_save.connect(_user_pre_save, sender=User, weak=False)
    post_save.connect(_user_post_save, sender=User, weak=False)

    post_init.connect(_decrypt_address, sender=EmailAddress, weak=False)
    pre_save.connect(_address_pre_save, sender=EmailAddress, weak=False)
    post_save.connect(_address_post_save, sender=EmailAddress, weak=False)

    _patch_queryset(User.objects)
    _patch_queryset(EmailAddress.objects)
    _PATCHED = True
