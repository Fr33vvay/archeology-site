"""Тесты комментариев к статьям."""

import io
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from wagtail.models import Page, Site

from articles.models import ArticleIndexPage, ArticlePage, ArticleUniqueView, Comment, CommentImage
from home.models import HomePage
from mysite.unique_views import VID_COOKIE

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

    @override_settings(MEDIA_ROOT="/tmp/archeology-test-media")
    def test_rejects_image_with_html_extension(self):
        """Файл с расширением .html отклоняется, даже если внутри валидный PNG."""
        from django import forms as django_forms

        from articles.forms import validate_comment_images

        evil = _png_upload("evil.html")
        with self.assertRaises(django_forms.ValidationError) as ctx:
            validate_comment_images([evil])
        self.assertIn("JPEG", str(ctx.exception))

    @override_settings(MEDIA_ROOT="/tmp/archeology-test-media")
    def test_saves_image_with_safe_extension(self):
        """Валидный PNG сохраняется с расширением .png, а не с исходным регистром имени."""
        self.client.login(username="commenter", password="pass-12345")
        url = f"/comments/add/{self.article.pk}/"
        response = self.client.post(
            url,
            {"body": "Нормальное фото", "images": [_png_upload("Photo.PNG")]},
        )
        self.assertEqual(response.status_code, 302)
        image = CommentImage.objects.get(comment__body="Нормальное фото")
        self.assertTrue(image.image.name.lower().endswith(".png"))

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


class LibreOfficeFootnoteConvertTests(TestCase):
    """Конвертация сносок LibreOffice в формат #fn-/#fnref-."""

    def test_convert_lo_footnotes_endnotes(self):
        """Тела sdendnote выносятся в ol, ссылки в тексте ведут на #fn-N."""
        from articles.lo_footnotes import convert_lo_footnotes

        raw = (
            "<p>Абзац"
            '<a class="sdendnoteanc" name="sdendnote1anc" href="#sdendnote1sym">'
            "<sup>1</sup></a>.</p>"
            '<div id="sdendnote1"><p class="sdendnote-western">'
            '<a class="sdendnotesym" name="sdendnote1sym" href="#sdendnote1anc">1</a>'
            "Книга А.</p></div>"
        )
        html, notes = convert_lo_footnotes(raw)
        self.assertIn('href="#fn-1"', html)
        self.assertNotIn("sdendnote", html)
        self.assertIn("Книга А.", notes)
        self.assertIn('href="#fnref-1"', notes)
        self.assertIn("<ol>", notes)

    def test_convert_lo_footnotes_keeps_emphasis_in_body(self):
        """В тексте сноски сохраняется курсив."""
        from articles.lo_footnotes import convert_lo_footnotes

        raw = (
            '<div id="sdfootnote1"><p>'
            '<a class="sdfootnotesym" name="sdfootnote1sym" href="#sdfootnote1anc">1</a>'
            "<i>Автор</i> Текст.</p></div>"
            '<p><a class="sdfootnoteanc" name="sdfootnote1anc" href="#sdfootnote1sym">'
            "<sup>1</sup></a></p>"
        )
        _html, notes = convert_lo_footnotes(raw)
        self.assertIn("<i>Автор</i>", notes)


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

    def test_editor_and_lists_have_no_article_cover(self):
        """У статей нет обложки: ни в редакторе, ни в списках на сайте."""
        field_names = {f.name for f in ArticlePage._meta.get_fields()}
        self.assertNotIn("cover", field_names)
        self.client.login(username="editor-admin", password="pass-12345")
        edit_html = self.client.get(f"/articles/{self.article.pk}/edit/").content.decode()
        self.assertNotIn("cover_id", edit_html)
        self.assertNotIn("Обложка", edit_html)
        self.assertNotIn("data-cover", edit_html)
        index_html = self.client.get(self.index.url).content.decode()
        self.assertNotIn("card__cover", index_html)
        home_html = self.client.get("/").content.decode()
        self.assertNotIn("card__cover", home_html)
        source = (STATIC_JS / "article-editor.js").read_text(encoding="utf-8")
        self.assertNotIn("data-cover-file", source)
        self.assertNotIn("обложку", source)

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


class ArticleUniqueViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        home = HomePage(title="Главная", slug="home-views")
        root.add_child(instance=home)
        home.save_revision().publish()
        Site.objects.update_or_create(
            is_default_site=True,
            defaults={"hostname": "localhost", "root_page": home, "site_name": "Test"},
        )
        index = ArticleIndexPage(title="Статьи", slug="articles-views")
        home.add_child(instance=index)
        index.save_revision().publish()
        article = ArticlePage(title="Статья для просмотров", slug="article-views", intro="intro")
        index.add_child(instance=article)
        article.save_revision().publish()
        cls.article = article
        cls.user = User.objects.create_user(
            username="viewer", email="viewer@yandex.ru", password="pass-12345"
        )

    def test_guest_view_sets_cookie_and_increments_once(self):
        """Гость получает cookie vid; повторный POST не увеличивает счётчик статьи."""
        url = f"/articles/{self.article.pk}/view/"
        first = self.client.post(url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), {"count": 1, "created": True})
        self.assertIn(VID_COOKIE, first.cookies)
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 1)

        second = self.client.post(url)
        self.assertEqual(second.json(), {"count": 1, "created": False})
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 1)
        self.assertEqual(ArticleUniqueView.objects.filter(article=self.article).count(), 1)

    def test_different_guests_increment_separately(self):
        """Разные cookie vid считаются разными посетителями статьи."""
        url = f"/articles/{self.article.pk}/view/"
        self.client.post(url)
        self.client.cookies.clear()
        self.client.post(url)
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 2)

    def test_logged_in_user_uses_user_key(self):
        """Залогиненный пользователь учитывается по ключу u:{pk}."""
        self.client.login(username="viewer", password="pass-12345")
        url = f"/articles/{self.article.pk}/view/"
        response = self.client.post(url)
        self.assertEqual(response.json()["created"], True)
        view = ArticleUniqueView.objects.get(article=self.article)
        self.assertEqual(view.visitor_key, f"u:{self.user.pk}")
        again = self.client.post(url)
        self.assertEqual(again.json(), {"count": 1, "created": False})

    def test_unpublished_article_returns_404(self):
        """Неопубликованная статья недоступна для учёта просмотра."""
        self.article.unpublish()
        response = self.client.post(f"/articles/{self.article.pk}/view/")
        self.assertEqual(response.status_code, 404)

    def test_owner_view_does_not_increment(self):
        """Владелец статьи (owner) не создаёт UniqueView и не увеличивает счётчик."""
        self.article.owner = self.user
        self.article.save(update_fields=["owner"])
        self.client.login(username="viewer", password="pass-12345")
        response = self.client.post(f"/articles/{self.article.pk}/view/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"count": 0, "created": False})
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 0)
        self.assertEqual(ArticleUniqueView.objects.filter(article=self.article).count(), 0)

    def test_other_user_increments_article_view(self):
        """Другой залогиненный пользователь увеличивает счётчик статьи."""
        owner = User.objects.create_user(
            username="owner", email="owner@yandex.ru", password="pass-12345"
        )
        self.article.owner = owner
        self.article.save(update_fields=["owner"])
        self.client.login(username="viewer", password="pass-12345")
        response = self.client.post(f"/articles/{self.article.pk}/view/")
        self.assertEqual(response.json(), {"count": 1, "created": True})
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 1)

    def test_guest_increments_when_owner_set(self):
        """Гость увеличивает счётчик статьи даже если у неё задан owner."""
        self.article.owner = self.user
        self.article.save(update_fields=["owner"])
        response = self.client.post(f"/articles/{self.article.pk}/view/")
        self.assertEqual(response.json(), {"count": 1, "created": True})
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 1)


class FavoriteArticleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        home = HomePage.objects.first()
        if not home:
            home = HomePage(title="Главная", slug="home-fav")
            root.add_child(instance=home)
            home.save_revision().publish()
        Site.objects.update_or_create(
            is_default_site=True,
            defaults={"hostname": "localhost", "root_page": home, "site_name": "Test"},
        )
        index = ArticleIndexPage.objects.child_of(home).first()
        if not index:
            index = ArticleIndexPage(title="Статьи", slug="articles-fav")
            home.add_child(instance=index)
            index.save_revision().publish()
        article = ArticlePage(title="Избранная статья", slug="fav-article", intro="intro")
        index.add_child(instance=article)
        article.save_revision().publish()
        other = ArticlePage(title="Чужая статья", slug="other-fav-article", intro="")
        index.add_child(instance=other)
        other.save_revision().publish()
        cls.article = article
        cls.other_article = other
        cls.user = User.objects.create_user(
            username="fav-user", email="fav@yandex.ru", password="pass-12345"
        )
        cls.other = User.objects.create_user(
            username="fav-other", email="fav-other@yandex.ru", password="pass-12345"
        )

    def test_add_and_remove_favorite(self):
        """Пользователь добавляет статью в избранное и убирает её."""
        from articles.models import FavoriteArticle

        self.client.login(username="fav-user", password="pass-12345")
        add = self.client.post(
            f"/articles/{self.article.pk}/favorite/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(add.status_code, 200)
        self.assertTrue(add.json()["favorited"])
        self.assertEqual(
            FavoriteArticle.objects.filter(user=self.user, article=self.article).count(),
            1,
        )
        remove = self.client.post(
            f"/articles/{self.article.pk}/favorite/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(remove.status_code, 200)
        self.assertFalse(remove.json()["favorited"])
        self.assertEqual(
            FavoriteArticle.objects.filter(user=self.user, article=self.article).count(),
            0,
        )

    def test_user_sees_only_own_favorites(self):
        """В профиле видны только свои избранные статьи."""
        from articles.models import FavoriteArticle

        FavoriteArticle.objects.create(user=self.user, article=self.article)
        FavoriteArticle.objects.create(user=self.other, article=self.other_article)
        self.client.login(username="fav-user", password="pass-12345")
        response = self.client.get("/accounts/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.article.title)
        self.assertNotContains(response, self.other_article.title)

    def test_guest_favorite_redirects_to_login(self):
        """Гость при toggle избранного перенаправляется на вход."""
        response = self.client.post(f"/articles/{self.article.pk}/favorite/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_toggle_returns_json_for_ajax(self):
        """AJAX-запрос получает JSON с флагом favorited и сообщением."""
        self.client.login(username="fav-user", password="pass-12345")
        response = self.client.post(
            f"/articles/{self.article.pk}/favorite/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["favorited"])
        self.assertIn("toast", data)
        self.assertIn("профиле", data["toast"].lower())

    def test_profile_remove_favorite(self):
        """Из профиля можно удалить статью из избранного."""
        from articles.models import FavoriteArticle

        fav = FavoriteArticle.objects.create(user=self.user, article=self.article)
        self.client.login(username="fav-user", password="pass-12345")
        response = self.client.post(f"/articles/favorites/{fav.pk}/remove/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(FavoriteArticle.objects.filter(pk=fav.pk).exists())

    def test_cannot_remove_others_favorite(self):
        """Нельзя удалить чужое избранное."""
        from articles.models import FavoriteArticle

        fav = FavoriteArticle.objects.create(user=self.other, article=self.article)
        self.client.login(username="fav-user", password="pass-12345")
        response = self.client.post(f"/articles/favorites/{fav.pk}/remove/")
        self.assertIn(response.status_code, (403, 404))
        self.assertTrue(FavoriteArticle.objects.filter(pk=fav.pk).exists())


class PapaImportTitleTests(TestCase):
    """Проверяет очистку заголовка статьи из имени файла импорта."""

    def setUp(self):
        import tempfile

        self._tmp = Path(tempfile.mkdtemp(prefix="papa-test-"))

    def tearDown(self):
        import shutil

        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_title_from_filename_strips_illustration_noise(self):
        """Из имени файла убираются пометки про картинки и копии."""
        from articles.management.commands.import_papa_articles import title_from_filename

        self.assertEqual(title_from_filename("Трезини. Картинки.docx"), "Трезини")
        self.assertEqual(title_from_filename("Филлимонов картинки — копия.doc"), "Филлимонов")
        self.assertEqual(title_from_filename("Растрелли с ил..odt"), "Растрелли")
        self.assertEqual(title_from_filename("Шердом илл.doc"), "Шердом")

    def test_parse_html_keeps_paragraph_and_image_order(self):
        """Разбор HTML LibreOffice чередует текст и картинки."""
        from articles.management.commands.import_papa_articles import parse_html_document

        html = self._tmp / "sample.html"
        jpg = self._tmp / "pic.jpg"
        Image.new("RGB", (40, 30), color=(10, 20, 30)).save(jpg, format="JPEG")
        html.write_text(
            "<html><body>"
            "<p>Первый абзац статьи.</p>"
            '<p><img src="pic.jpg"/></p>'
            "<p>Рис. 1. Подпись</p>"
            "<p>Второй абзац.</p>"
            "</body></html>",
            encoding="utf-8",
        )
        parsed = parse_html_document(html, "Тест")
        types = [b["type"] for b in parsed.blocks]
        self.assertEqual(types, ["paragraph", "image", "paragraph"])
        self.assertEqual(parsed.blocks[1]["value"]["caption"], "Рис. 1. Подпись")

    def test_parse_html_standalone_img_between_paragraphs(self):
        """Картинка между абзацами (типичный HTML LibreOffice) попадает в блоки."""
        from articles.management.commands.import_papa_articles import parse_html_document

        html = self._tmp / "between.html"
        jpg = self._tmp / "solo.jpg"
        Image.new("RGB", (40, 30), color=(10, 20, 30)).save(jpg, format="JPEG")
        html.write_text(
            "<html><body>"
            "<p>Текст до.</p>"
            '<img src="solo.jpg"/>'
            "<p>Текст после.</p>"
            "</body></html>",
            encoding="utf-8",
        )
        parsed = parse_html_document(html, "Тест")
        self.assertEqual([b["type"] for b in parsed.blocks], ["paragraph", "image", "paragraph"])

    def test_parse_html_converts_libreoffice_endnotes(self):
        """Сноски LibreOffice (sdendnote) становятся #fn-/#fnref- в тексте и списке."""
        from articles.management.commands.import_papa_articles import parse_html_document

        html = self._tmp / "notes.html"
        html.write_text(
            "<html><body>"
            "<p>Текст"
            '<sup><a class="sdendnoteanc" name="sdendnote1anc" '
            'href="#sdendnote1sym"><sup>1</sup></a></sup>.</p>'
            '<div id="sdendnote1"><p class="sdendnote-western">'
            '<a class="sdendnotesym" name="sdendnote1sym" href="#sdendnote1anc">1</a>'
            "Источник А.</p></div>"
            "</body></html>",
            encoding="utf-8",
        )
        parsed = parse_html_document(html, "Со сносками")
        joined = "".join(b["value"] for b in parsed.blocks if b["type"] == "paragraph")
        self.assertIn('href="#fn-1"', joined)
        self.assertIn("<sup>1</sup>", joined)
        self.assertIn('href="#fnref-1"', joined)
        self.assertIn("Источник А.", joined)
        self.assertNotIn("sdendnote", joined)

    def test_parse_html_converts_libreoffice_footnotes(self):
        """Обычные сноски LibreOffice (sdfootnote) тоже конвертируются."""
        from articles.management.commands.import_papa_articles import parse_html_document

        html = self._tmp / "footnotes.html"
        html.write_text(
            "<html><body>"
            "<p>Факт"
            '<a class="sdfootnoteanc" name="sdfootnote2anc" '
            'href="#sdfootnote2sym"><sup>2</sup></a>.</p>'
            '<div id="sdfootnote2"><p class="sdfootnote-western">'
            '<a class="sdfootnotesym" name="sdfootnote2sym" href="#sdfootnote2anc">2</a>'
            "Примечание Б.</p></div>"
            "</body></html>",
            encoding="utf-8",
        )
        parsed = parse_html_document(html, "Сноски")
        joined = "".join(b["value"] for b in parsed.blocks if b["type"] == "paragraph")
        self.assertIn('href="#fn-2"', joined)
        self.assertIn('href="#fnref-2"', joined)
        self.assertIn("Примечание Б.", joined)
        self.assertNotIn("sdfootnote", joined)
