"""Тесты блога: посты, комментарии, лайки, мягкое удаление."""

import io
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from wagtail.models import Page, Site

from blog.models import BlogComment, BlogCommentLike, BlogPost, BlogPostImage, BlogPostLike
from home.models import HomePage

from blog.models import BlogIndexPage

User = get_user_model()


def _png_upload(name="pic.png", size=(20, 20)):
    buf = io.BytesIO()
    Image.new("RGB", size, color=(40, 90, 140)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class BlogTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        home = HomePage.objects.first()
        if not home:
            home = HomePage(title="Главная", slug="home-blog")
            root.add_child(instance=home)
            home.save_revision().publish()
        Site.objects.update_or_create(
            is_default_site=True,
            defaults={"hostname": "localhost", "root_page": home, "site_name": "Test"},
        )
        blog_index = BlogIndexPage.objects.child_of(home).first()
        if not blog_index:
            blog_index = BlogIndexPage(title="Блог", slug="blog")
            home.add_child(instance=blog_index)
            blog_index.save_revision().publish()
        cls.blog_index = blog_index
        cls.superuser = User.objects.create_superuser(
            username="admin", email="admin@yandex.ru", password="pass-12345"
        )
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


class BlogPostCreationViewTests(BlogTestBase):
    def test_anonymous_cannot_create_post(self):
        """Аноним перенаправляется на вход при попытке опубликовать пост."""
        response = self.client.post("/blog/posts/add/", {"body": "Привет"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.assertEqual(BlogPost.objects.count(), 0)

    def test_staff_but_not_superuser_cannot_create_post(self):
        """Сотрудник (is_staff), но не суперпользователь — не может публиковать посты."""
        self.client.login(username="staff", password="pass-12345")
        response = self.client.post("/blog/posts/add/", {"body": "Пост от staff"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(BlogPost.objects.count(), 0)

    def test_regular_user_cannot_create_post(self):
        """Обычный вошедший пользователь не может публиковать посты."""
        self.client.login(username="reader", password="pass-12345")
        response = self.client.post("/blog/posts/add/", {"body": "Пост читателя"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(BlogPost.objects.count(), 0)

    def test_superuser_can_create_post(self):
        """Суперпользователь публикует пост."""
        self.client.login(username="admin", password="pass-12345")
        response = self.client.post("/blog/posts/add/", {"body": "Пост от суперюзера"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BlogPost.objects.count(), 1)
        self.assertEqual(BlogPost.objects.first().author, self.superuser)

    @override_settings(MEDIA_ROOT="/tmp/archeology-blog-test-media")
    def test_post_with_up_to_three_images(self):
        """К посту можно прикрепить до трёх фото."""
        self.client.login(username="admin", password="pass-12345")
        response = self.client.post(
            "/blog/posts/add/",
            {
                "body": "С фото",
                "images": [_png_upload("a.png"), _png_upload("b.png"), _png_upload("c.png")],
            },
        )
        self.assertEqual(response.status_code, 302)
        post = BlogPost.objects.get(body="С фото")
        self.assertEqual(post.images.count(), 3)

    @override_settings(MEDIA_ROOT="/tmp/archeology-blog-test-media")
    def test_rejects_more_than_three_images(self):
        """Больше трёх фото к посту отклоняется."""
        self.client.login(username="admin", password="pass-12345")
        response = self.client.post(
            "/blog/posts/add/",
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
        self.assertEqual(BlogPost.objects.filter(body="Много фото").count(), 0)


class BlogPostPermissionTests(BlogTestBase):
    def test_author_can_edit_own_post(self):
        """Автор редактирует свой пост."""
        post = BlogPost.objects.create(author=self.superuser, body="Было")
        self.client.login(username="admin", password="pass-12345")
        response = self.client.post(f"/blog/posts/edit/{post.pk}/", {"body": "Стало"})
        self.assertEqual(response.status_code, 302)
        post.refresh_from_db()
        self.assertEqual(post.body, "Стало")

    def test_other_user_cannot_edit_post(self):
        """Чужой пользователь не может редактировать пост."""
        post = BlogPost.objects.create(author=self.superuser, body="Чужой")
        self.client.login(username="reader", password="pass-12345")
        response = self.client.post(f"/blog/posts/edit/{post.pk}/", {"body": "Взлом"})
        self.assertEqual(response.status_code, 403)
        post.refresh_from_db()
        self.assertEqual(post.body, "Чужой")

    def test_author_can_delete_own_post(self):
        """Автор мягко удаляет свой пост."""
        post = BlogPost.objects.create(author=self.author, body="Удалить меня")
        self.client.login(username="reader", password="pass-12345")
        response = self.client.post(f"/blog/posts/delete/{post.pk}/")
        self.assertEqual(response.status_code, 302)
        post.refresh_from_db()
        self.assertTrue(post.is_deleted)

    def test_superuser_can_delete_others_post(self):
        """Суперпользователь удаляет чужой пост."""
        post = BlogPost.objects.create(author=self.author, body="Не моё")
        self.client.login(username="admin", password="pass-12345")
        response = self.client.post(f"/blog/posts/delete/{post.pk}/")
        self.assertEqual(response.status_code, 302)
        post.refresh_from_db()
        self.assertTrue(post.is_deleted)

    def test_regular_user_cannot_delete_others_post(self):
        """Обычный пользователь не удаляет чужой пост (даже не автор)."""
        post = BlogPost.objects.create(author=self.author, body="Не трогать")
        self.client.login(username="other", password="pass-12345")
        response = self.client.post(f"/blog/posts/delete/{post.pk}/")
        self.assertEqual(response.status_code, 403)
        post.refresh_from_db()
        self.assertFalse(post.is_deleted)

    def test_soft_delete_keeps_record(self):
        """Мягкое удаление не стирает запись из базы."""
        post = BlogPost.objects.create(author=self.author, body="Текст")
        post.soft_delete()
        self.assertTrue(BlogPost.objects.filter(pk=post.pk).exists())
        post.refresh_from_db()
        self.assertTrue(post.is_deleted)


class BlogCommentTests(BlogTestBase):
    def setUp(self):
        self.post = BlogPost.objects.create(author=self.superuser, body="Пост для комментариев")

    def test_anonymous_cannot_comment(self):
        """Аноним не может оставить комментарий."""
        response = self.client.post(
            f"/blog/comments/add/{self.post.pk}/", {"body": "Комментарий"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.assertEqual(BlogComment.objects.count(), 0)

    def test_logged_in_can_comment(self):
        """Вошедший пользователь оставляет комментарий."""
        self.client.login(username="reader", password="pass-12345")
        response = self.client.post(
            f"/blog/comments/add/{self.post.pk}/", {"body": "Отличный пост"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BlogComment.objects.filter(post=self.post).count(), 1)

    def test_author_can_edit_own_comment(self):
        """Автор комментария редактирует свой текст."""
        comment = BlogComment.objects.create(post=self.post, author=self.author, body="Было")
        self.client.login(username="reader", password="pass-12345")
        response = self.client.post(f"/blog/comments/edit/{comment.pk}/", {"body": "Стало"})
        self.assertEqual(response.status_code, 302)
        comment.refresh_from_db()
        self.assertEqual(comment.body, "Стало")

    def test_other_cannot_edit_comment(self):
        """Чужой пользователь не может редактировать комментарий."""
        comment = BlogComment.objects.create(post=self.post, author=self.author, body="Чужой")
        self.client.login(username="other", password="pass-12345")
        response = self.client.post(f"/blog/comments/edit/{comment.pk}/", {"body": "Взлом"})
        self.assertEqual(response.status_code, 403)
        comment.refresh_from_db()
        self.assertEqual(comment.body, "Чужой")

    def test_author_can_delete_own_comment(self):
        """Автор мягко удаляет свой комментарий."""
        comment = BlogComment.objects.create(post=self.post, author=self.author, body="Удалить")
        self.client.login(username="reader", password="pass-12345")
        response = self.client.post(f"/blog/comments/delete/{comment.pk}/")
        self.assertEqual(response.status_code, 302)
        comment.refresh_from_db()
        self.assertTrue(comment.is_deleted)

    def test_other_cannot_delete_comment(self):
        """Чужой пользователь (в т.ч. суперпользователь) не удаляет комментарий по требованиям блога."""
        comment = BlogComment.objects.create(post=self.post, author=self.author, body="Не трогать")
        self.client.login(username="admin", password="pass-12345")
        response = self.client.post(f"/blog/comments/delete/{comment.pk}/")
        self.assertEqual(response.status_code, 403)
        comment.refresh_from_db()
        self.assertFalse(comment.is_deleted)

    def test_comments_preview_shows_first_three(self):
        """В ленте под постом показываются первые три комментария, остальные скрыты для разворота."""
        for i in range(5):
            BlogComment.objects.create(
                post=self.post, author=self.author, body=f"Комментарий {i}"
            )
        self.client.login(username="reader", password="pass-12345")
        response = self.client.get(self.blog_index.url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Комментарий 0", html)
        self.assertIn("Комментарий 1", html)
        self.assertIn("Комментарий 2", html)
        self.assertIn("Комментарий 3", html)
        self.assertIn("Комментарий 4", html)
        self.assertIn("data-comments-toggle", html)
        self.assertIn('class="comment-list comment-list--rest"', html)


class BlogLikeTests(BlogTestBase):
    def setUp(self):
        self.post = BlogPost.objects.create(author=self.superuser, body="Пост для лайков")
        self.comment = BlogComment.objects.create(
            post=self.post, author=self.superuser, body="Комментарий для лайков"
        )

    def test_anonymous_cannot_like_post(self):
        """Аноним не может лайкнуть пост."""
        response = self.client.post(f"/blog/posts/like/{self.post.pk}/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.assertEqual(BlogPostLike.objects.count(), 0)

    def test_like_post_toggle(self):
        """Повторный лайк снимает предыдущий (toggle), дизлайков нет."""
        self.client.login(username="reader", password="pass-12345")
        url = f"/blog/posts/like/{self.post.pk}/"
        self.client.post(url)
        self.assertEqual(BlogPostLike.objects.filter(post=self.post, user=self.author).count(), 1)
        self.client.post(url)
        self.assertEqual(BlogPostLike.objects.filter(post=self.post, user=self.author).count(), 0)

    def test_like_post_ajax_keeps_page(self):
        """AJAX-лайк возвращает JSON и не требует перезагрузки ленты."""
        self.client.login(username="reader", password="pass-12345")
        url = f"/blog/posts/like/{self.post.pk}/"
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"liked": True, "count": 1})

    def test_like_comment_toggle(self):
        """Лайк комментария также переключается повторным нажатием."""
        self.client.login(username="reader", password="pass-12345")
        url = f"/blog/comments/like/{self.comment.pk}/"
        self.client.post(url)
        self.assertEqual(
            BlogCommentLike.objects.filter(comment=self.comment, user=self.author).count(), 1
        )
        self.client.post(url)
        self.assertEqual(
            BlogCommentLike.objects.filter(comment=self.comment, user=self.author).count(), 0
        )

    def test_likes_count_reflects_multiple_users(self):
        """Счётчик лайков считает уникальных пользователей."""
        self.client.login(username="reader", password="pass-12345")
        self.client.post(f"/blog/posts/like/{self.post.pk}/")
        self.client.logout()
        self.client.login(username="other", password="pass-12345")
        self.client.post(f"/blog/posts/like/{self.post.pk}/")
        self.post.refresh_from_db()
        self.assertEqual(self.post.likes_count(), 2)
