import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from accounts.email_domains import is_russian_email

User = get_user_model()
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RussianEmailTests(SimpleTestCase):
    def test_allows_yandex_and_mailru(self):
        """Разрешены популярные российские почтовые домены."""
        self.assertTrue(is_russian_email("user@yandex.ru"))
        self.assertTrue(is_russian_email("user@ya.ru"))
        self.assertTrue(is_russian_email("user@mail.ru"))
        self.assertTrue(is_russian_email("user@inbox.ru"))

    def test_allows_ru_corporate(self):
        """Разрешены корпоративные адреса в зоне .ru."""
        self.assertTrue(is_russian_email("ivan@spbu.ru"))

    def test_blocks_foreign(self):
        """Иностранные почтовые сервисы отклоняются."""
        self.assertFalse(is_russian_email("user@gmail.com"))
        self.assertFalse(is_russian_email("user@outlook.com"))
        self.assertFalse(is_russian_email("user@icloud.com"))


class ProfileAndSignupTests(TestCase):
    def test_signup_rejects_foreign_email(self):
        """Регистрация с нероссийской почтой отклоняется на форме."""
        response = self.client.post(
            "/accounts/signup/",
            {
                "email": "user@gmail.com",
                "password1": "StrongPass-12345",
                "password2": "StrongPass-12345",
                "first_name": "Иван",
                "last_name": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "российской почты")
        self.assertEqual(User.objects.filter(email="user@gmail.com").count(), 0)

    def test_signup_requires_first_name(self):
        """При регистрации имя обязательно, фамилия — нет."""
        response = self.client.post(
            "/accounts/signup/",
            {
                "email": "new@yandex.ru",
                "password1": "StrongPass-12345",
                "password2": "StrongPass-12345",
                "first_name": "",
                "last_name": "Иванов",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(email="new@yandex.ru").count(), 0)

        response = self.client.post(
            "/accounts/signup/",
            {
                "email": "new@yandex.ru",
                "password1": "StrongPass-12345",
                "password2": "StrongPass-12345",
                "first_name": "Иван",
                "last_name": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="new@yandex.ru")
        self.assertEqual(user.first_name, "Иван")
        self.assertEqual(user.last_name, "")

    def test_signup_succeeds_without_smtp(self):
        """При verification=none регистрация не падает даже без рабочего SMTP."""
        from django.core import mail
        from django.test.utils import override_settings

        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
            EMAIL_HOST="127.0.0.1",
            EMAIL_PORT=9,
            ACCOUNT_EMAIL_VERIFICATION="none",
        ):
            response = self.client.post(
                "/accounts/signup/",
                {
                    "email": "nosmtp@yandex.ru",
                    "password1": "StrongPass-12345",
                    "password2": "StrongPass-12345",
                    "first_name": "Без",
                    "last_name": "Почты",
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="nosmtp@yandex.ru").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_mandatory_verification_sends_email_and_blocks_login(self):
        """При mandatory уходит письмо, войти нельзя, пока email не подтверждён."""
        from allauth.account.models import EmailAddress
        from django.core import mail
        from django.test.utils import override_settings

        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            ACCOUNT_EMAIL_VERIFICATION="mandatory",
        ):
            response = self.client.post(
                "/accounts/signup/",
                {
                    "email": "verify-me@yandex.ru",
                    "password1": "StrongPass-12345",
                    "password2": "StrongPass-12345",
                    "first_name": "Проверка",
                    "last_name": "",
                },
            )
            self.assertEqual(response.status_code, 302)
            user = User.objects.get(email="verify-me@yandex.ru")
            self.assertFalse(user.is_active)
            self.assertEqual(len(mail.outbox), 1)
            self.assertIn("verify-me@yandex.ru", mail.outbox[0].to)

            self.assertFalse(
                EmailAddress.objects.get(email="verify-me@yandex.ru").verified
            )
            self.client.post(
                "/accounts/login/",
                {
                    "login": "verify-me@yandex.ru",
                    "password": "StrongPass-12345",
                },
            )
            self.assertNotIn("_auth_user_id", self.client.session)

            from allauth.account.adapter import get_adapter
            from django.test import RequestFactory

            addr = EmailAddress.objects.get(email="verify-me@yandex.ru")
            request = RequestFactory().get("/")
            # middleware сообщений нужен для confirm_email
            from django.contrib.messages.storage.fallback import FallbackStorage
            from django.contrib.sessions.backends.db import SessionStore

            request.session = SessionStore()
            request._messages = FallbackStorage(request)
            get_adapter().confirm_email(request, addr)
            user.refresh_from_db()
            addr.refresh_from_db()
            self.assertTrue(user.is_active)
            self.assertTrue(addr.verified)

            login_ok = self.client.post(
                "/accounts/login/",
                {
                    "login": "verify-me@yandex.ru",
                    "password": "StrongPass-12345",
                },
            )
            self.assertEqual(login_ok.status_code, 302)
            self.assertIn("_auth_user_id", self.client.session)

    def test_verification_sent_page_uses_site_style(self):
        """Страница «подтвердите почту» оформлена в стиле сайта, не дефолтом allauth."""
        from django.test.utils import override_settings

        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            ACCOUNT_EMAIL_VERIFICATION="mandatory",
        ):
            response = self.client.post(
                "/accounts/signup/",
                {
                    "email": "styled@yandex.ru",
                    "password1": "StrongPass-12345",
                    "password2": "StrongPass-12345",
                    "first_name": "Стиль",
                    "last_name": "",
                },
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Подтвердите почту")
        self.assertContains(response, "page-title")
        self.assertContains(response, "auth-box")
        self.assertNotContains(response, "allauth")

    def test_profile_edit(self):
        """Вошедший пользователь меняет имя и фамилию на странице профиля."""
        user = User.objects.create_user(
            username="profile-user",
            email="p@yandex.ru",
            password="pass-12345",
            first_name="Старое",
        )
        self.client.login(username="profile-user", password="pass-12345")
        response = self.client.post(
            "/accounts/profile/",
            {"first_name": "Новое", "last_name": "Имя"},
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Новое")
        self.assertEqual(user.last_name, "Имя")

    def test_profile_nav_link(self):
        """В шапке для вошедшего пользователя есть ссылка «Профиль»."""
        User.objects.create_user(
            username="nav-user", email="n@yandex.ru", password="pass-12345"
        )
        self.client.login(username="nav-user", password="pass-12345")
        response = self.client.get("/")
        self.assertContains(response, "Профиль")
        self.assertContains(response, "/accounts/profile/")

    def test_confirm_email_get_does_not_verify(self):
        """GET по ссылке подтверждения только показывает форму, не подтверждает адрес."""
        from allauth.account.models import EmailAddress, EmailConfirmationHMAC
        from django.core import mail
        from django.test.utils import override_settings

        self.assertFalse(settings.ACCOUNT_CONFIRM_EMAIL_ON_GET)

        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            ACCOUNT_EMAIL_VERIFICATION="mandatory",
            ACCOUNT_CONFIRM_EMAIL_ON_GET=False,
        ):
            response = self.client.post(
                "/accounts/signup/",
                {
                    "email": "get-confirm@yandex.ru",
                    "password1": "StrongPass-12345",
                    "password2": "StrongPass-12345",
                    "first_name": "Гет",
                    "last_name": "",
                },
            )
            self.assertEqual(response.status_code, 302)
            addr = EmailAddress.objects.get(email="get-confirm@yandex.ru")
            self.assertFalse(addr.verified)
            key = EmailConfirmationHMAC(addr).key
            get_resp = self.client.get(f"/accounts/confirm-email/{key}/")
            self.assertEqual(get_resp.status_code, 200)
            self.assertContains(get_resp, "Подтвердить")
            addr.refresh_from_db()
            self.assertFalse(addr.verified)

            post_resp = self.client.post(f"/accounts/confirm-email/{key}/")
            self.assertEqual(post_resp.status_code, 302)
            addr.refresh_from_db()
            self.assertTrue(addr.verified)
            self.assertGreaterEqual(len(mail.outbox), 1)


class ProductionSmtpGuardTests(SimpleTestCase):
    def test_production_settings_require_smtp(self):
        """Без EMAIL_HOST_USER/PASSWORD production падает, а не ставит verification=none."""
        env = os.environ.copy()
        env["DJANGO_SECRET_KEY"] = "test-secret-for-smtp-guard"
        env["EMAIL_HOST_USER"] = ""
        env["EMAIL_HOST_PASSWORD"] = ""
        env.pop("DJANGO_SETTINGS_MODULE", None)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from django.core.exceptions import ImproperlyConfigured\n"
                    "try:\n"
                    "    import mysite.settings.production  # noqa: F401\n"
                    "except ImproperlyConfigured as exc:\n"
                    "    assert 'EMAIL_HOST' in str(exc)\n"
                    "    raise SystemExit(0)\n"
                    "raise SystemExit('expected ImproperlyConfigured')\n"
                ),
            ],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
