"""Шифрует уже существующие plaintext email в User и EmailAddress."""

from django.db import migrations


def encrypt_existing(apps, schema_editor):
    from accounts.email_crypto import encrypt_email, hash_email, is_email_hash, normalize_email

    User = apps.get_model("auth", "User")
    EmailAddress = apps.get_model("account", "EmailAddress")
    UserEmailSecret = apps.get_model("accounts", "UserEmailSecret")
    AddressEmailSecret = apps.get_model("accounts", "AddressEmailSecret")

    for user in User.objects.all().iterator():
        email = (user.email or "").strip()
        if not email or is_email_hash(email):
            continue
        plain = normalize_email(email)
        UserEmailSecret.objects.update_or_create(
            user_id=user.pk,
            defaults={
                "email_hash": hash_email(plain),
                "ciphertext": encrypt_email(plain),
            },
        )
        User.objects.filter(pk=user.pk).update(email=hash_email(plain))

    for addr in EmailAddress.objects.all().iterator():
        email = (addr.email or "").strip()
        if not email or is_email_hash(email):
            continue
        plain = normalize_email(email)
        AddressEmailSecret.objects.update_or_create(
            address_id=addr.pk,
            defaults={
                "email_hash": hash_email(plain),
                "ciphertext": encrypt_email(plain),
            },
        )
        EmailAddress.objects.filter(pk=addr.pk).update(email=hash_email(plain))


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_email_secrets"),
        ("account", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(encrypt_existing, noop_reverse),
    ]
