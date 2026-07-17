"""Тесты комментариев к статьям."""

import io
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from wagtail.models import Page, Site

from articles.models import ArticleIndexPage, ArticlePage, Comment, CommentImage
from home.models import HomePage

User = get_user_model()
STATIC_JS = Path(__file__).resolve().parents[1] / "mysite" / "static" / "js"


def _png_upload(name="pic.png", size=(20, 20)):
    buf = io.BytesIO()
    Image.new("RGB", size, color=(180, 40, 40)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class CommentModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        home = HomePage(title="Главная", slug="home-comments")
        root.add_child(instance=home)
        home.save_revision().publish()
        Site.objects.update_or_create(
            is_default_site=True,
            defaults={"hostname": "localhost", "root_page": home, "site_name": "Test"},
        )
        index = ArticleIndexPage(title="Статьи", slug="articles-comments")
        home.add_child(instance=index)
        index.save_revision().publish()
        article = ArticlePage(title="Статья", slug="article-comments", intro="intro")
        index.add_child(instance=article)
        article.save_revision().publish()
        cls.article = article
        cls.author = User.objects.create_user(
            username="reader", email="reader@yandex.ru", password="pass-12345"
        )
        cls.other = User.objects.create_user(
            username="other", email="other@yandex.ru", password="pass-12345"
        )
        cls.staff = User.objects.create_user(
            username="staff",
            email="staff@yandex.ru",
            password="pass-12345",
            is_staff=True,
        )

    def test_top_level_comment(self):
        """Корневой комментарий сохраняется без родителя."""
        c = Comment.objects.create(
            article=self.article, author=self.author, body="Первый комментарий"
        )
        self.assertIsNone(c.parent_id)
        self.assertFalse(c.is_deleted)

    def test_reply_to_top_level(self):
        """Ответ на корневой комментарий допускается."""
        parent = Comment.objects.create(
            article=self.article, author=self.author, body="Родитель"
        )
        reply = Comment.objects.create(
            article=self.article, author=self.other, parent=parent, body="Ответ"
        )
        self.assertEqual(reply.parent_id, parent.pk)

    def test_reply_to_reply_rejected(self):
        """Ответ на ответ запрещён (один уровень вложенности)."""
        parent = Comment.objects.create(
            article=self.article, author=self.author, body="Родитель"
        )
        reply = Comment.objects.create(
            article=self.article, author=self.other, parent=parent, body="Ответ"
        )
        nested = Comment(
            article=self.article, author=self.author, parent=reply, body="Вложенный"
        )
        with self.assertRaises(ValidationError):
            nested.save()

    def test_can_delete_author_and_staff(self):
        """Удалять может автор или сотрудник, чужой пользователь — нет."""
        c = Comment.objects.create(
            article=self.article, author=self.author, body="Текст"
        )
        self.assertTrue(c.can_delete(self.author))
        self.assertTrue(c.can_delete(self.staff))
        self.assertFalse(c.can_delete(self.other))

    def test_can_edit_only_author(self):
        """Редактировать может только автор комментария."""
        c = Comment.objects.create(
            article=self.article, author=self.author, body="Текст"
        )
        self.assertTrue(c.can_edit(self.author))
        self.assertFalse(c.can_edit(self.staff))
        self.assertFalse(c.can_edit(self.other))
        c.soft_delete()
        self.assertFalse(c.can_edit(self.author))

    def test_soft_delete(self):
        """Удаление помечает комментарий, не стирает запись."""
        c = Comment.objects.create(
            article=self.article, author=self.author, body="Текст"
        )
        c.soft_delete()
        c.refresh_from_db()
        self.assertTrue(c.is_deleted)


class CommentViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        home = HomePage.objects.first()
        if not home:
            home = HomePage(title="Главная", slug="home-comments-v")
            root.add_child(instance=home)
            home.save_revision().publish()
        index = ArticleIndexPage.objects.child_of(home).first()
        if not index:
            index = ArticleIndexPage(title="Статьи", slug="articles-v")
            home.add_child(instance=index)
            index.save_revision().publish()
        article = ArticlePage(title="Статья для views", slug="article-views", intro="")
        index.add_child(instance=article)
        article.save_revision().publish()
        cls.article = article
        cls.user = User.objects.create_user(
            username="commenter", email="c@yandex.ru", password="pass-12345"
        )

    def test_anonymous_cannot_post(self):
        """Аноним перенаправляется на вход при попытке оставить комментарий."""
        url = f"/comments/add/{self.article.pk}/"
        response = self.client.post(url, {"body": "Привет"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.assertEqual(Comment.objects.count(), 0)

    def test_logged_in_can_post(self):
        """Вошедший пользователь создаёт комментарий."""
        self.client.login(username="commenter", password="pass-12345")
        url = f"/comments/add/{self.article.pk}/"
        response = self.client.post(url, {"body": "Привет всем"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.filter(article=self.article).count(), 1)

    def test_logged_in_can_reply(self):
        """Вошедший пользователь создаёт ответ с parent_id."""
        parent = Comment.objects.create(
            article=self.article, author=self.user, body="Родитель"
        )
        self.client.login(username="commenter", password="pass-12345")
        url = f"/comments/add/{self.article.pk}/"
        response = self.client.post(
            url, {"body": "Это ответ", "parent_id": str(parent.pk)}
        )
        self.assertEqual(response.status_code, 302)
        reply = Comment.objects.get(parent=parent)
        self.assertEqual(reply.body, "Это ответ")

    def test_author_can_delete_own(self):
        """Автор мягко удаляет свой комментарий через POST."""
        c = Comment.objects.create(
            article=self.article, author=self.user, body="Удалить меня"
        )
        self.client.login(username="commenter", password="pass-12345")
        response = self.client.post(f"/comments/delete/{c.pk}/")
        self.assertEqual(response.status_code, 302)
        c.refresh_from_db()
        self.assertTrue(c.is_deleted)

    @override_settings(MEDIA_ROOT="/tmp/archeology-test-media")
    def test_post_with_images(self):
        """К комментарию можно прикрепить до трёх изображений."""
        self.client.login(username="commenter", password="pass-12345")
        url = f"/comments/add/{self.article.pk}/"
        response = self.client.post(
            url,
            {
                "body": "С фото",
                "images": [_png_upload("a.png"), _png_upload("b.png")],
            },
        )
        self.assertEqual(response.status_code, 302)
        comment = Comment.objects.get(article=self.article, body="С фото")
        self.assertEqual(comment.images.count(), 2)

    @override_settings(MEDIA_ROOT="/tmp/archeology-test-media")
    def test_image_only_comment(self):
        """Комментарий только с фото без текста допускается."""
        self.client.login(username="commenter", password="pass-12345")
        url = f"/comments/add/{self.article.pk}/"
        response = self.client.post(url, {"body": "", "images": [_png_upload()]})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.filter(article=self.article).count(), 1)
        self.assertEqual(CommentImage.objects.count(), 1)

    @override_settings(MEDIA_ROOT="/tmp/archeology-test-media")
    def test_rejects_more_than_three_images(self):
        """Больше трёх изображений отклоняется."""
        self.client.login(username="commenter", password="pass-12345")
        url = f"/comments/add/{self.article.pk}/"
        response = self.client.post(
            url,
            {
                "body": "Много фото",
                "images": [
                    _png_upload("1.png"),
                    _png_upload("2.png"),
                    _png_upload("3.png"),
                    _png_upload("4.png"),
                ],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.filter(article=self.article).count(), 0)

    def test_author_can_edit_own(self):
        """Автор меняет текст своего комментария."""
        c = Comment.objects.create(
            article=self.article, author=self.user, body="Было"
        )
        self.client.login(username="commenter", password="pass-12345")
        response = self.client.post(
            f"/comments/edit/{c.pk}/", {"body": "Стало"}
        )
        self.assertEqual(response.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.body, "Стало")

    def test_other_cannot_edit(self):
        """Чужой пользователь не может редактировать комментарий."""
        User.objects.create_user(
            username="intruder", email="i@yandex.ru", password="pass-12345"
        )
        c = Comment.objects.create(
            article=self.article, author=self.user, body="Чужой"
        )
        self.client.login(username="intruder", password="pass-12345")
        response = self.client.post(
            f"/comments/edit/{c.pk}/", {"body": "Взлом"}
        )
        self.assertEqual(response.status_code, 403)
        c.refresh_from_db()
        self.assertEqual(c.body, "Чужой")

    @override_settings(MEDIA_ROOT="/tmp/archeology-test-media")
    def test_edit_can_remove_image(self):
        """При редактировании можно удалить прикреплённое фото."""
        c = Comment.objects.create(
            article=self.article, author=self.user, body="С фото"
        )
        img = CommentImage.objects.create(
            comment=c, image=_png_upload("keep-or-drop.png"), sort_order=0
        )
        self.client.login(username="commenter", password="pass-12345")
        response = self.client.post(
            f"/comments/edit/{c.pk}/",
            {"body": "Без фото", "remove_images": [str(img.pk)]},
        )
        self.assertEqual(response.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.body, "Без фото")
        self.assertEqual(c.images.count(), 0)

    @override_settings(MEDIA_ROOT="/tmp/archeology-test-media")
    def test_edit_rejects_empty_after_removing_all(self):
        """Нельзя сохранить пустой комментарий без текста и фото."""
        c = Comment.objects.create(
            article=self.article, author=self.user, body=""
        )
        img = CommentImage.objects.create(
            comment=c, image=_png_upload("only.png"), sort_order=0
        )
        self.client.login(username="commenter", password="pass-12345")
        response = self.client.post(
            f"/comments/edit/{c.pk}/",
            {"body": "", "remove_images": [str(img.pk)]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CommentImage.objects.filter(pk=img.pk).exists())

    @override_settings(MEDIA_ROOT="/tmp/archeology-test-media")
    def test_comment_image_lightbox_markup(self):
        """У превью фото есть data-full-src и корневой оверлей просмотра."""
        comment = Comment.objects.create(
            article=self.article, author=self.user, body="С фото"
        )
        image = CommentImage.objects.create(
            comment=comment, image=_png_upload("lightbox.png"), sort_order=0
        )
        response = self.client.get(self.article.url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("data-comment-lightbox", html)
        self.assertIn(f'data-full-src="{image.image.url}"', html)
        self.assertIn("data-comment-lightbox-root", html)
        self.assertIn("data-comment-lightbox-img", html)
        self.assertNotIn("data-comment-lightbox-dialog", html)

    def test_lightbox_js_uses_overlay_not_dialog(self):
        """Скрипт просмотра открывает оверлей и берёт URL из data-full-src."""
        source = (STATIC_JS / "comment-images.js").read_text(encoding="utf-8")
        self.assertIn("data-full-src", source)
        self.assertIn("data-comment-lightbox-root", source)
        self.assertIn("lightbox.hidden = false", source)
        self.assertNotIn("showModal", source)
