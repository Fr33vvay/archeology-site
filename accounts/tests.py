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

    def test_confirmation_email_mentions_site_not_admin(self):
        """В письме подтверждения — коренцвит.рф, без admin и example.com."""
        from django.contrib.sites.models import Site
        from django.core import mail
        from django.test.utils import override_settings

        Site.objects.update_or_create(
            id=1,
            defaults={"domain": "коренцвит.рф", "name": "коренцвит.рф"},
        )
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            ACCOUNT_EMAIL_VERIFICATION="mandatory",
            ACCOUNT_CONFIRM_EMAIL_ON_GET=False,
        ):
            response = self.client.post(
                "/accounts/signup/",
                {
                    "email": "mail-check@yandex.ru",
                    "password1": "StrongPass-12345",
                    "password2": "StrongPass-12345",
                    "first_name": "Почта",
                    "last_name": "",
                },
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(len(mail.outbox), 1)
            subject = mail.outbox[0].subject
            body = mail.outbox[0].body
            self.assertIn("коренцвит.рф", subject)
            self.assertIn("коренцвит.рф", body)
            self.assertIn("Подтвердить", body)
            self.assertNotIn("example.com", subject)
            self.assertNotIn("example.com", body)
            self.assertNotIn("admin", body.lower())
            self.assertNotIn("xn--", body)


class ProductionSmtpGuardTests(SimpleTestCase):
    def test_production_settings_require_smtp(self):
        """Без EMAIL_HOST_USER/PASSWORD production падает, а не ставит verification=none."""
        env = os.environ.copy()
        env["DJANGO_SECRET_KEY"] = "test-secret-for-smtp-guard"
        env["EMAIL_HOST_USER"] = ""
        env["EMAIL_HOST_PASSWORD"] = ""
        env["EMAIL_ENCRYPTION_KEY"] = "x" * 44
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

    def test_production_settings_require_encryption_key(self):
        """Без EMAIL_ENCRYPTION_KEY production падает громко."""
        from cryptography.fernet import Fernet

        env = os.environ.copy()
        env["DJANGO_SECRET_KEY"] = "test-secret-for-enc-guard"
        env["EMAIL_HOST_USER"] = "smtp@example.com"
        env["EMAIL_HOST_PASSWORD"] = "secret"
        env["EMAIL_ENCRYPTION_KEY"] = ""
        env["FERNET_KEY"] = ""
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
                    "    assert 'EMAIL_ENCRYPTION' in str(exc)\n"
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
        # ключ валидного формата не нужен здесь — только проверка наличия
        _ = Fernet.generate_key()


class WeeklyReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from wagtail.models import Page, Site

        from articles.models import ArticleIndexPage, ArticlePage
        from home.models import HomePage

        root = Page.get_first_root_node()
        home = HomePage.objects.first()
        if not home:
            home = HomePage(title="Главная", slug="home-weekly")
            root.add_child(instance=home)
            home.save_revision().publish()
        Site.objects.update_or_create(
            is_default_site=True,
            defaults={"hostname": "localhost", "root_page": home, "site_name": "Test"},
        )
        index = ArticleIndexPage.objects.child_of(home).first()
        if not index:
            index = ArticleIndexPage(title="Статьи", slug="articles-weekly")
            home.add_child(instance=index)
            index.save_revision().publish()
        article = ArticlePage(title="Недельная", slug="weekly-article", intro="")
        index.add_child(instance=article)
        article.save_revision().publish()
        cls.article = article

    def _last_week_mid(self):
        from datetime import timedelta
        from zoneinfo import ZoneInfo

        from django.utils import timezone

        from accounts.weekly_report import previous_week_bounds

        start, end = previous_week_bounds(timezone.now())
        return start + timedelta(days=2)

    def test_sends_mail_when_activity(self):
        """При активности за прошлую неделю письмо уходит в outbox."""
        from django.core import mail
        from django.core.management import call_command
        from django.test import override_settings
        from django.utils import timezone

        from articles.models import ArticleUniqueView, Comment

        mid = self._last_week_mid()
        user = User.objects.create_user(
            username="weekly-u",
            email="weekly-u@yandex.ru",
            password="pass-12345",
            first_name="Павел",
            last_name="Иванов",
        )
        User.objects.filter(pk=user.pk).update(date_joined=mid)
        view = ArticleUniqueView.objects.create(
            article=self.article, visitor_key="vid-weekly-1"
        )
        ArticleUniqueView.objects.filter(pk=view.pk).update(created_at=mid)
        comment = Comment.objects.create(
            article=self.article, author=user, body="Комментарий недели"
        )
        Comment.objects.filter(pk=comment.pk).update(created_at=mid)

        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            WEEKLY_REPORT_RECIPIENTS=["a@example.com", "b@example.com"],
        ):
            call_command("send_weekly_report")

        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("Павел", body)
        self.assertIn("Иванов", body)
        self.assertNotIn("weekly-u@yandex.ru", body)
        self.assertIn("Просмотры статей", body)
        self.assertEqual(mail.outbox[0].to, ["a@example.com", "b@example.com"])

    def test_skips_mail_when_silent(self):
        """Если все метрики нулевые, письмо не отправляется."""
        from django.core import mail
        from django.core.management import call_command
        from django.test import override_settings

        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            WEEKLY_REPORT_RECIPIENTS=["a@example.com"],
        ):
            call_command("send_weekly_report")
        self.assertEqual(len(mail.outbox), 0)

    def test_force_sends_even_when_silent(self):
        """Флаг --force отправляет письмо даже при нулевых метриках."""
        from django.core import mail
        from django.core.management import call_command
        from django.test import override_settings

        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            WEEKLY_REPORT_RECIPIENTS=["a@example.com"],
        ):
            call_command("send_weekly_report", force=True)
        self.assertEqual(len(mail.outbox), 1)

    def test_report_period_is_previous_calendar_week(self):
        """Период отчёта — прошлая календарная неделя Europe/Moscow."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from accounts.weekly_report import previous_week_bounds

        # Среда 15 июля 2026 MSK → прошлый пн–вс: 6–12 июля
        now = datetime(2026, 7, 15, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))
        start, end = previous_week_bounds(now)
        self.assertEqual(start.date().isoformat(), "2026-07-06")
        self.assertEqual(end.date().isoformat(), "2026-07-13")


class EmailEncryptionTests(TestCase):
    def test_email_not_stored_as_plaintext_in_db(self):
        """После сохранения в БД email хранится не в открытом виде."""
        from django.db import connection

        user = User.objects.create_user(
            username="enc-user",
            email="secret-mail@yandex.ru",
            password="pass-12345",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT email FROM auth_user WHERE id = %s", [user.pk]
            )
            row = cursor.fetchone()
        raw = row[0]
        self.assertNotEqual(raw, "secret-mail@yandex.ru")
        self.assertNotIn("secret-mail@yandex.ru", raw)
        # Через ORM — расшифрованный
        user.refresh_from_db()
        self.assertEqual(user.email, "secret-mail@yandex.ru")

    def test_login_by_email_works(self):
        """Вход по email и паролю работает с зашифрованным email."""
        User.objects.create_user(
            username="login-enc",
            email="login-enc@yandex.ru",
            password="StrongPass-12345",
        )
        response = self.client.post(
            "/accounts/login/",
            {"login": "login-enc@yandex.ru", "password": "StrongPass-12345"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_signup_works_with_encryption(self):
        """Регистрация сохраняет пользователя и шифрует email."""
        response = self.client.post(
            "/accounts/signup/",
            {
                "email": "signup-enc@yandex.ru",
                "password1": "StrongPass-12345",
                "password2": "StrongPass-12345",
                "first_name": "Анна",
                "last_name": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="signup-enc@yandex.ru")
        self.assertEqual(user.first_name, "Анна")
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT email FROM auth_user WHERE id = %s", [user.pk]
            )
            raw = cursor.fetchone()[0]
        self.assertNotEqual(raw, "signup-enc@yandex.ru")

    def test_profile_shows_plaintext_email(self):
        """В профиле показывается нормальный (расшифрованный) email."""
        User.objects.create_user(
            username="prof-enc",
            email="prof-enc@yandex.ru",
            password="pass-12345",
        )
        self.client.login(username="prof-enc", password="pass-12345")
        response = self.client.get("/accounts/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "prof-enc@yandex.ru")
