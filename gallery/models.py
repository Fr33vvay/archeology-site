from django.db import models

from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable, Page
from wagtail.search import index


class GalleryIndexPage(Page):
    intro = RichTextField(blank=True, verbose_name="Вступление")

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = ["gallery.GalleryFolderPage"]
    max_count = 1

    class Meta:
        verbose_name = "Раздел галереи"
        verbose_name_plural = "Разделы галереи"

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["folders"] = (
            GalleryFolderPage.objects.child_of(self).live().public().order_by("title")
        )
        return context


class GalleryFolderPage(Page):
    intro = RichTextField(blank=True, verbose_name="Описание папки")
    year = models.PositiveIntegerField("Год", null=True, blank=True)
    place = models.CharField("Место", max_length=255, blank=True)
    source_article = models.OneToOneField(
        "articles.ArticlePage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="gallery_folder",
        verbose_name="Статья-источник",
        help_text="Если заполнено, папка создана автоматически из иллюстраций статьи.",
    )

    search_fields = Page.search_fields + [
        index.SearchField("intro"),
        index.SearchField("place"),
    ]

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("year"),
                FieldPanel("place"),
            ],
            heading="Метаданные",
        ),
        FieldPanel("intro"),
        InlinePanel("photos", label="Фотографии"),
    ]

    parent_page_types = ["gallery.GalleryIndexPage"]
    subpage_types = []

    class Meta:
        verbose_name = "Папка галереи"
        verbose_name_plural = "Папки галереи"

    @property
    def cover_image(self):
        first = self.photos.first()
        return first.image if first else None


class GalleryPhoto(Orderable):
    page = ParentalKey(
        GalleryFolderPage,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="Фото",
    )
    caption = models.CharField("Подпись", max_length=255, blank=True)

    panels = [
        FieldPanel("image"),
        FieldPanel("caption"),
    ]
