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
