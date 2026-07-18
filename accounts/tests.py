from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from accounts.email_domains import is_russian_email

User = get_user_model()


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
            self.assertTrue(User.objects.filter(email="verify-me@yandex.ru").exists())
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

            EmailAddress.objects.filter(email="verify-me@yandex.ru").update(verified=True)
            login_ok = self.client.post(
                "/accounts/login/",
                {
                    "login": "verify-me@yandex.ru",
                    "password": "StrongPass-12345",
                },
            )
            self.assertEqual(login_ok.status_code, 302)
            self.assertIn("_auth_user_id", self.client.session)

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
