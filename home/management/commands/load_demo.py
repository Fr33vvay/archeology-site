"""Создаёт демо-структуру сайта, две статьи, папку галереи и двух редакторов."""

from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image as PILImage
from wagtail.images.models import Image
from wagtail.models import Page, Site

from articles.models import ArticleIndexPage, ArticlePage
from gallery.models import GalleryFolderPage, GalleryIndexPage, GalleryPhoto
from home.models import ContactPage, HomePage
from maps.models import MapPage


def make_image(title: str, color: tuple[int, int, int], filename: str) -> Image:
    existing = Image.objects.filter(title=title).first()
    if existing:
        return existing

    buf = BytesIO()
    img = PILImage.new("RGB", (1200, 800), color)
    img.save(buf, format="JPEG", quality=85)
    return Image.objects.create(
        title=title,
        file=ContentFile(buf.getvalue(), name=filename),
    )


class Command(BaseCommand):
    help = "Загрузить демо-контент и создать пользователей admin / editor"

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@example.ru", "is_staff": True, "is_superuser": True},
        )
        if created or not admin.has_usable_password():
            admin.set_password("admin-change-me")
            admin.save()
            self.stdout.write("Пользователь admin / admin-change-me")

        editors = (
            Group.objects.filter(name="Editors").first()
            or Group.objects.filter(name="Редакторы").first()
        )
        editor, created = User.objects.get_or_create(
            username="editor",
            defaults={"email": "editor@example.ru", "is_staff": True},
        )
        if created or not editor.has_usable_password():
            editor.set_password("editor-change-me")
            editor.save()
            self.stdout.write("Пользователь editor / editor-change-me")
        if editors:
            editor.groups.add(editors)
        else:
            editor.is_superuser = True
            editor.save(update_fields=["is_superuser"])

        root = Page.get_first_root_node()
        home = HomePage.objects.live().first()
        if not home:
            home = HomePage(
                title="Главная",
                slug="home",
                hero_title="Научный архив археологических исследований",
                intro=(
                    "<p>Собрание публикаций, полевых материалов и иллюстраций. "
                    "Сайт создан как личный архив многолетней научной работы.</p>"
                ),
            )
            root.add_child(instance=home)
            home.save_revision().publish()
        else:
            home.hero_title = home.hero_title or "Научный архив археологических исследований"
            if not home.intro:
                home.intro = (
                    "<p>Собрание публикаций, полевых материалов и иллюстраций. "
                    "Сайт создан как личный архив многолетней научной работы.</p>"
                )
            home.save_revision().publish()

        Site.objects.update_or_create(
            is_default_site=True,
            defaults={
                "hostname": "localhost",
                "port": 80,
                "root_page": home,
                "site_name": "Научный архив",
            },
        )

        cover = make_image("Демо: раскоп", (107, 79, 42), "demo-cover.jpg")
        photo_a = make_image("Демо: находка", (90, 110, 95), "demo-find.jpg")
        photo_b = make_image("Демо: план", (70, 85, 110), "demo-plan.jpg")

        if not home.hero_image_id:
            home.hero_image = cover
            home.save_revision().publish()

        articles_index = ArticleIndexPage.objects.child_of(home).first()
        if not articles_index:
            articles_index = ArticleIndexPage(
                title="Статьи",
                slug="articles",
                intro="<p>Научные статьи и заметки.</p>",
                show_in_menus=True,
            )
            home.add_child(instance=articles_index)
            articles_index.save_revision().publish()
        else:
            articles_index.show_in_menus = True
            articles_index.save_revision().publish()

        gallery_index = GalleryIndexPage.objects.child_of(home).first()
        if not gallery_index:
            gallery_index = GalleryIndexPage(
                title="Галерея",
                slug="gallery",
                intro="<p>Иллюстрации по папкам, отдельно от статей.</p>",
                show_in_menus=True,
            )
            home.add_child(instance=gallery_index)
            gallery_index.save_revision().publish()
        else:
            gallery_index.show_in_menus = True
            gallery_index.save_revision().publish()

        contact = ContactPage.objects.child_of(home).first()
        if not contact:
            contact = ContactPage(
                title="Контакты",
                slug="contacts",
                intro="<p>По вопросам материалов архива пишите на почту.</p>",
                email="archive@example.ru",
                phone="+7 (000) 000-00-00",
                address="Научное учреждение",
                show_in_menus=True,
            )
            home.add_child(instance=contact)
            contact.save_revision().publish()
        else:
            contact.show_in_menus = True
            contact.save_revision().publish()

        map_page = MapPage.objects.child_of(home).first()
        if not map_page:
            map_page = MapPage(
                title="Карта",
                slug="map",
                intro="<p>Объекты на карте Санкт-Петербурга.</p>",
                show_in_menus=True,
            )
            home.add_child(instance=map_page)
            map_page.save_revision().publish()
        else:
            map_page.show_in_menus = True
            map_page.save_revision().publish()

        if not ArticlePage.objects.child_of(articles_index).filter(slug="demo-article-1").exists():
            a1 = ArticlePage(
                title="Демо: Методика фиксации находок",
                slug="demo-article-1",
                intro="Краткий демо-текст о полевой фиксации и иллюстрациях в статье.",
                body=[
                    {"type": "heading", "value": "Введение"},
                    {
                        "type": "paragraph",
                        "value": (
                            "<p>Это демонстрационная статья. Здесь удобно сочетать текст "
                            "с иллюстрациями: подписи не ломают вёрстку, фото занимают "
                            "свою ширину колонки.</p>"
                        ),
                    },
                    {
                        "type": "image",
                        "value": {"image": cover.pk, "caption": "Пример иллюстрации с подписью"},
                    },
                    {
                        "type": "quote",
                        "value": "Аккуратная фиксация — основа последующей публикации.",
                    },
                    {
                        "type": "gallery",
                        "value": {
                            "title": "Примеры кадров",
                            "images": [
                                {"image": photo_a.pk, "caption": "Находка"},
                                {"image": photo_b.pk, "caption": "План участка"},
                            ],
                        },
                    },
                ],
            )
            articles_index.add_child(instance=a1)
            a1.save_revision().publish()

        if not ArticlePage.objects.child_of(articles_index).filter(slug="demo-article-2").exists():
            a2 = ArticlePage(
                title="Демо: Заметки о стратиграфии",
                slug="demo-article-2",
                intro="Вторая демо-публикация для проверки списка статей и поиска.",
                body=[
                    {
                        "type": "paragraph",
                        "value": (
                            "<p>Вторая демонстрационная статья. Её можно удалить или "
                            "отредактировать в админке Wagtail.</p>"
                        ),
                    },
                ],
            )
            articles_index.add_child(instance=a2)
            a2.save_revision().publish()

        # После публикации статей сигнал мог добавить папки в галерею —
        # обновляем numchild, иначе add_child падает на конфликте path.
        gallery_index.refresh_from_db()
        folder = GalleryFolderPage.objects.child_of(gallery_index).filter(slug="demo-folder").first()
        if not folder:
            folder = GalleryFolderPage(
                title="Демо: Экспедиция",
                slug="demo-folder",
                year=2022,
                place="Полевой лагерь",
                intro="<p>Пример папки галереи с несколькими фотографиями.</p>",
            )
            gallery_index.add_child(instance=folder)
            folder.save_revision().publish()
        else:
            folder = GalleryFolderPage.objects.get(pk=folder.pk)

        if folder.photos.count() == 0:
            GalleryPhoto.objects.create(page=folder, image=photo_a, caption="Находка", sort_order=0)
            GalleryPhoto.objects.create(page=folder, image=photo_b, caption="План", sort_order=1)
            folder.save_revision().publish()

        self.stdout.write(self.style.SUCCESS("Демо-контент готов."))
