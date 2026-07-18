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


class FootnoteAnchorTests(TestCase):
    """Рабочие якоря сносок и возврата в текст."""

    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        home = HomePage(title="Главная", slug="home-fn")
        root.add_child(instance=home)
        home.save_revision().publish()
        Site.objects.update_or_create(
            is_default_site=True,
            defaults={"hostname": "localhost", "root_page": home, "site_name": "Test"},
        )
        index = ArticleIndexPage(title="Статьи", slug="articles-fn")
        home.add_child(instance=index)
        index.save_revision().publish()
        article = ArticlePage(
            title="Статья со сносками",
            slug="article-fn",
            intro="intro",
            body=[
                {
                    "type": "paragraph",
                    "value": (
                        '<p>Текст со сноской'
                        '<a href="#fn-1"><sup>1</sup></a>.</p>'
                    ),
                },
                {
                    "type": "paragraph",
                    "value": (
                        "<p></p><ol>"
                        "<li>Источник. "
                        '<a href="#fnref-1">↩</a></li>'
                        "</ol>"
                    ),
                },
            ],
        )
        index.add_child(instance=article)
        article.save_revision().publish()
        cls.article = ArticlePage.objects.get(pk=article.pk)

    def test_apply_footnote_anchors_adds_ids(self):
        """Фильтр ставит id на ссылку в тексте и на пункт списка сносок."""
        from articles.templatetags.article_extras import apply_footnote_anchors

        raw = (
            '<p>Сноска<a href="#fn-1"><sup>1</sup></a></p>'
            '<ol><li>Примечание <a href="#fnref-1">↩</a></li></ol>'
        )
        html = apply_footnote_anchors(raw)
        self.assertIn('id="fnref-1"', html)
        self.assertIn('href="#fn-1"', html)
        self.assertIn('id="fn-1"', html)
        self.assertIn('href="#fnref-1"', html)
        self.assertIn('class="footnote-ref"', html)
        self.assertIn('class="footnote-back"', html)
        self.assertIn('class="footnotes"', html)

    def test_article_page_has_bidirectional_footnote_targets(self):
        """На странице статьи есть цели для перехода к сноске и обратно в текст."""
        response = self.client.get(self.article.url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="fnref-1"', html)
        self.assertIn('id="fn-1"', html)
        self.assertIn('href="#fn-1"', html)
        self.assertIn('href="#fnref-1"', html)
        # Из текста можно уйти к сноске, из сноски — вернуться
        self.assertRegex(html, r'id="fnref-1"[^>]*href="#fn-1"|href="#fn-1"[^>]*id="fnref-1"')
        self.assertRegex(html, r'id="fn-1"[\s\S]*?href="#fnref-1"')


class ArticleEditorViewTests(TestCase):
    """Редактирование статей на сайте: права, черновик и публикация."""

    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        home = HomePage(title="Главная", slug="home-editor")
        root.add_child(instance=home)
        home.save_revision().publish()
        Site.objects.update_or_create(
            is_default_site=True,
            defaults={"hostname": "localhost", "root_page": home, "site_name": "Test"},
        )
        index = ArticleIndexPage(title="Статьи", slug="articles-editor")
        home.add_child(instance=index)
        index.save_revision().publish()
        article = ArticlePage(
            title="Живая статья",
            slug="live-article",
            intro="intro",
            body=[{"type": "paragraph", "value": "<p>Живой текст</p>"}],
        )
        index.add_child(instance=article)
        article.save_revision().publish()
        cls.index = ArticleIndexPage.objects.get(pk=index.pk)
        cls.article = ArticlePage.objects.get(pk=article.pk)
        cls.superuser = User.objects.create_superuser(
            username="editor-admin", email="editor-admin@yandex.ru", password="pass-12345"
        )
        cls.staff = User.objects.create_user(
            username="editor-staff",
            email="editor-staff@yandex.ru",
            password="pass-12345",
            is_staff=True,
        )
        cls.reader = User.objects.create_user(
            username="editor-reader",
            email="editor-reader@yandex.ru",
            password="pass-12345",
        )

    def _blocks_json(self, html):
        import json

        return json.dumps([{"type": "paragraph", "value": html}])

    def test_anonymous_redirected_from_editor(self):
        """Аноним перенаправляется на вход при открытии редактора."""
        response = self.client.get(f"/articles/{self.article.pk}/edit/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_staff_cannot_edit_or_create(self):
        """Сотрудник без суперпользователя не может править и создавать статьи."""
        self.client.login(username="editor-staff", password="pass-12345")
        self.assertEqual(self.client.get(f"/articles/{self.article.pk}/edit/").status_code, 403)
        self.assertEqual(self.client.get("/articles/new/").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/articles/upload-image/",
                {"image": _png_upload("x.png")},
            ).status_code,
            403,
        )

    def test_regular_user_cannot_edit(self):
        """Обычный пользователь не видит редактор статьи."""
        self.client.login(username="editor-reader", password="pass-12345")
        self.assertEqual(self.client.get(f"/articles/{self.article.pk}/edit/").status_code, 403)

    def test_superuser_sees_edit_and_create_buttons(self):
        """Суперпользователь видит кнопки редактирования и создания статьи."""
        self.client.login(username="editor-admin", password="pass-12345")
        article_html = self.client.get(self.article.url).content.decode()
        self.assertIn("Редактировать", article_html)
        self.assertIn(f"/articles/{self.article.pk}/edit/", article_html)
        index_html = self.client.get(self.index.url).content.decode()
        self.assertIn("Новая статья", index_html)
        self.assertIn("/articles/new/", index_html)

    def test_editor_page_has_sidebar_and_rich_text(self):
        """У редактора боковая панель действий и визуальный набор текста."""
        self.client.login(username="editor-admin", password="pass-12345")
        response = self.client.get(f"/articles/{self.article.pk}/edit/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("article-editor__sidebar", html)
        self.assertIn("Сохранить черновик", html)
        self.assertIn("Отмена", html)
        source = (STATIC_JS / "article-editor.js").read_text(encoding="utf-8")
        self.assertIn("contenteditable", source)
        self.assertIn('data-cmd="bold"', source)
        self.assertIn('data-cmd="italic"', source)
        self.assertIn('data-cmd="underline"', source)
        self.assertIn('data-cmd="insertFootnote"', source)
        self.assertIn("Текст сноски", source)
        self.assertIn("Точно удалить этот блок?", source)

    def test_draft_does_not_change_live_html(self):
        """Черновик сохраняется, но live-страница остаётся прежней."""
        self.client.login(username="editor-admin", password="pass-12345")
        response = self.client.post(
            f"/articles/{self.article.pk}/edit/",
            {
                "title": "Живая статья",
                "intro": "intro",
                "blocks_json": self._blocks_json("<p>Текст черновика</p>"),
                "action": "draft",
            },
        )
        self.assertEqual(response.status_code, 302)
        live = self.client.get(self.article.url)
        self.assertEqual(live.status_code, 200)
        html = live.content.decode()
        self.assertIn("Живой текст", html)
        self.assertNotIn("Текст черновика", html)
        self.assertIn("Есть неопубликованный черновик", html)

    def test_publish_updates_live_html(self):
        """Публикация обновляет live-версию статьи."""
        self.client.login(username="editor-admin", password="pass-12345")
        response = self.client.post(
            f"/articles/{self.article.pk}/edit/",
            {
                "title": "Живая статья",
                "intro": "intro",
                "blocks_json": self._blocks_json("<p>Опубликованный текст</p>"),
                "action": "publish",
            },
        )
        self.assertEqual(response.status_code, 302)
        live = self.client.get(self.article.url)
        html = live.content.decode()
        self.assertIn("Опубликованный текст", html)
        self.assertNotIn("Живой текст", html)

    def test_create_draft_is_not_live(self):
        """Новая статья в черновике не попадает в публичный список."""
        self.client.login(username="editor-admin", password="pass-12345")
        before = ArticlePage.objects.child_of(self.index).count()
        response = self.client.post(
            "/articles/new/",
            {
                "title": "Черновик статьи",
                "intro": "скоро",
                "blocks_json": self._blocks_json("<p>Скрытый текст</p>"),
                "action": "draft",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ArticlePage.objects.child_of(self.index).count(), before + 1)
        draft = ArticlePage.objects.get(title="Черновик статьи")
        self.assertFalse(draft.live)
        index_html = self.client.get(self.index.url).content.decode()
        self.assertNotIn("Черновик статьи", index_html)

    def test_create_and_publish_appears_in_index(self):
        """Новая статья после публикации видна в разделе «Статьи»."""
        self.client.login(username="editor-admin", password="pass-12345")
        response = self.client.post(
            "/articles/new/",
            {
                "title": "Новая публикация",
                "intro": "intro",
                "blocks_json": self._blocks_json("<p>Тело новой</p>"),
                "action": "publish",
            },
        )
        self.assertEqual(response.status_code, 302)
        page = ArticlePage.objects.get(title="Новая публикация")
        self.assertTrue(page.live)
        index_html = self.client.get(self.index.url).content.decode()
        self.assertIn("Новая публикация", index_html)

    @override_settings(MEDIA_ROOT="/tmp/archeology-article-editor-media")
    def test_superuser_can_upload_image(self):
        """Суперпользователь загружает изображение для редактора статьи."""
        from wagtail.images.models import Image as WagtailImage

        self.client.login(username="editor-admin", password="pass-12345")
        response = self.client.post(
            "/articles/upload-image/",
            {"image": _png_upload("editor.png"), "title": "Иллюстрация"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("id", data)
        self.assertTrue(WagtailImage.objects.filter(pk=data["id"]).exists())
