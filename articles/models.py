from django.db import models

from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Page
from wagtail.search import index


class CaptionImageBlock(blocks.StructBlock):
    image = ImageChooserBlock(label="Иллюстрация")
    caption = blocks.CharBlock(required=False, label="Подпись", max_length=255)

    class Meta:
        icon = "image"
        label = "Иллюстрация"
        template = "articles/blocks/caption_image.html"


class GalleryInlineBlock(blocks.StructBlock):
    title = blocks.CharBlock(required=False, label="Заголовок врезки", max_length=120)
    images = blocks.ListBlock(
        CaptionImageBlock(),
        min_num=1,
        label="Фотографии",
    )

    class Meta:
        icon = "image"
        label = "Галерея-врезка"
        template = "articles/blocks/gallery_inline.html"


class ArticleIndexPage(Page):
    intro = RichTextField(blank=True, verbose_name="Вступление")

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = ["articles.ArticlePage"]
    max_count = 1

    class Meta:
        verbose_name = "Раздел статей"
        verbose_name_plural = "Разделы статей"

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["articles"] = (
            ArticlePage.objects.child_of(self).live().public().order_by("-first_published_at")
        )
        return context


class ArticlePage(Page):
    date = models.DateField("Дата публикации", null=True, blank=True)
    intro = models.CharField("Краткое описание", max_length=500, blank=True)
    body = StreamField(
        [
            ("heading", blocks.CharBlock(form_classname="title", label="Заголовок")),
            ("paragraph", blocks.RichTextBlock(label="Текст", features=[
                "h3", "h4", "bold", "italic", "ol", "ul", "hr", "link",
                "superscript", "subscript",
            ])),
            ("image", CaptionImageBlock()),
            ("quote", blocks.BlockQuoteBlock(label="Цитата")),
            ("gallery", GalleryInlineBlock()),
        ],
        use_json_field=True,
        blank=True,
        verbose_name="Содержание",
    )
    cover = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Обложка",
    )

    search_fields = Page.search_fields + [
        index.SearchField("intro"),
        index.SearchField("body"),
    ]

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("intro"),
        FieldPanel("cover"),
        FieldPanel("body"),
    ]

    parent_page_types = ["articles.ArticleIndexPage"]
    subpage_types = []

    class Meta:
        verbose_name = "Статья"
        verbose_name_plural = "Статьи"
