from django.db import models

from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page

from articles.models import ArticlePage


class HomePage(Page):
    hero_title = models.CharField(
        "Заголовок на главной",
        max_length=200,
        blank=True,
        help_text="Если пусто — используется название страницы",
    )
    intro = RichTextField(blank=True, verbose_name="Краткий текст")
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Фото на главной",
    )

    content_panels = Page.content_panels + [
        FieldPanel("hero_title"),
        FieldPanel("intro"),
        FieldPanel("hero_image"),
    ]

    max_count = 1
    subpage_types = [
        "articles.ArticleIndexPage",
        "gallery.GalleryIndexPage",
        "blog.BlogIndexPage",
        "home.AuthorPage",
        "home.ContactPage",
    ]

    class Meta:
        verbose_name = "Главная"
        verbose_name_plural = "Главные"

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["latest_articles"] = (
            ArticlePage.objects.live().public().order_by("-first_published_at")[:3]
        )
        return context


class AuthorPage(Page):
    """Страница «Об авторе» с портретом и биографическим текстом."""

    portrait = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Фотография",
    )
    body = RichTextField(verbose_name="Текст")

    content_panels = Page.content_panels + [
        FieldPanel("portrait"),
        FieldPanel("body"),
    ]

    parent_page_types = ["home.HomePage"]
    subpage_types = []
    max_count = 1

    class Meta:
        verbose_name = "Об авторе"
        verbose_name_plural = "Об авторе"


class ContactPage(Page):
    intro = RichTextField(blank=True, verbose_name="Текст")
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Телефон", max_length=64, blank=True)
    address = models.CharField("Адрес / учреждение", max_length=255, blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        MultiFieldPanel(
            [
                FieldPanel("email"),
                FieldPanel("phone"),
                FieldPanel("address"),
            ],
            heading="Контакты",
        ),
    ]

    parent_page_types = ["home.HomePage"]
    subpage_types = []
    max_count = 1

    class Meta:
        verbose_name = "Контакты"
        verbose_name_plural = "Контакты"
