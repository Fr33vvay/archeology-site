"""Тесты редактирования подписей фото галереи с сайта."""

import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image as PILImage
from wagtail.images.models import Image as WagtailImage
from wagtail.models import Page, Site

from gallery.models import GalleryFolderPage, GalleryIndexPage, GalleryPhoto
from home.models import HomePage

User = get_user_model()


def _wagtail_image(name="g.png"):
    buf = io.BytesIO()
    PILImage.new("RGB", (40, 40), color=(90, 120, 60)).save(buf, format="PNG")
    return WagtailImage.objects.create(
        title=name,
        file=SimpleUploadedFile(name, buf.getvalue(), content_type="image/png"),
    )


@override_settings(MEDIA_ROOT="/tmp/archeology-gallery-test-media")
class GalleryCaptionEditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        home = HomePage.objects.first()
        if not home:
            home = HomePage(title="Главная", slug="home-gallery")
            root.add_child(instance=home)
            home.save_revision().publish()
        Site.objects.update_or_create(
            is_default_site=True,
            defaults={"hostname": "localhost", "root_page": home, "site_name": "Test"},
        )
        index = GalleryIndexPage.objects.child_of(home).first()
        if not index:
            index = GalleryIndexPage(title="Галерея", slug="gallery-edit")
            home.add_child(instance=index)
            index.save_revision().publish()
        folder = GalleryFolderPage(title="Папка", slug="folder-edit", year=2024, place="Поле")
        index.add_child(instance=folder)
        folder.save_revision().publish()
        cls.folder = folder
        cls.superuser = User.objects.create_superuser(
            username="gal-admin", email="gal-admin@yandex.ru", password="pass-12345"
        )
        cls.user = User.objects.create_user(
            username="gal-user", email="gal-user@yandex.ru", password="pass-12345"
        )

    def setUp(self):
        self.image = _wagtail_image("caption-photo.png")
        self.photo = GalleryPhoto.objects.create(
            page=self.folder,
            image=self.image,
            caption="Старая подпись",
            sort_order=0,
        )

    def test_superuser_can_update_caption(self):
        """Суперпользователь меняет подпись фото через POST."""
        self.client.login(username="gal-admin", password="pass-12345")
        response = self.client.post(
            f"/gallery/photos/{self.photo.pk}/edit/",
            {"caption": "Новая подпись раскопок"},
        )
        self.assertEqual(response.status_code, 302)
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.caption, "Новая подпись раскопок")

    def test_regular_user_forbidden(self):
        """Обычный пользователь получает 403 при правке подписи."""
        self.client.login(username="gal-user", password="pass-12345")
        response = self.client.post(
            f"/gallery/photos/{self.photo.pk}/edit/",
            {"caption": "Чужая правка"},
        )
        self.assertEqual(response.status_code, 403)
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.caption, "Старая подпись")

    def test_guest_redirects_to_login(self):
        """Гость перенаправляется на вход."""
        response = self.client.post(
            f"/gallery/photos/{self.photo.pk}/edit/",
            {"caption": "Аноним"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_updated_caption_visible_on_folder_page(self):
        """После правки новая подпись видна на странице папки."""
        self.client.login(username="gal-admin", password="pass-12345")
        self.client.post(
            f"/gallery/photos/{self.photo.pk}/edit/",
            {"caption": "Видимая подпись"},
        )
        response = self.client.get(self.folder.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Видимая подпись")

    def test_edit_link_renders_before_caption_for_superuser(self):
        """У суперпользователя кнопка правки идёт сразу после картинки, до подписи."""
        self.client.login(username="gal-admin", password="pass-12345")
        response = self.client.get(self.folder.url)
        html = response.content.decode()
        edit_pos = html.find('class="photo-card__edit"')
        caption_pos = html.find("<figcaption>")
        self.assertNotEqual(edit_pos, -1)
        self.assertNotEqual(caption_pos, -1)
        self.assertLess(edit_pos, caption_pos)

    def test_edit_link_hidden_for_regular_user(self):
        """Обычному пользователю кнопка правки подписи не показывается."""
        self.client.login(username="gal-user", password="pass-12345")
        response = self.client.get(self.folder.url)
        self.assertNotContains(response, "Изменить подпись")
