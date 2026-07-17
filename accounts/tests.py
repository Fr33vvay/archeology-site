from django.test import SimpleTestCase

from accounts.email_domains import is_russian_email


class RussianEmailTests(SimpleTestCase):
    def test_allows_yandex_and_mailru(self):
        self.assertTrue(is_russian_email("user@yandex.ru"))
        self.assertTrue(is_russian_email("user@ya.ru"))
        self.assertTrue(is_russian_email("user@mail.ru"))
        self.assertTrue(is_russian_email("user@inbox.ru"))

    def test_allows_ru_corporate(self):
        self.assertTrue(is_russian_email("ivan@spbu.ru"))

    def test_blocks_foreign(self):
        self.assertFalse(is_russian_email("user@gmail.com"))
        self.assertFalse(is_russian_email("user@outlook.com"))
        self.assertFalse(is_russian_email("user@icloud.com"))
