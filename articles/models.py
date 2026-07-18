from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import Truncator

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
    intro = models.CharField("Краткое описание", max_length=500, blank=True)
    body = StreamField(
        [
            ("heading", blocks.CharBlock(form_classname="title", label="Заголовок")),
            ("paragraph", blocks.RichTextBlock(label="Текст", features=[
                "h3", "h4", "bold", "italic", "underline", "ol", "ul", "hr", "link",
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
        help_text="Маленькая картинка в списках статей (на главной и в разделе «Статьи»). "
        "Внутри самой статьи не показывается — иллюстрации добавляйте в «Содержание».",
    )

    search_fields = Page.search_fields + [
        index.SearchField("intro"),
        index.SearchField("body"),
    ]

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("cover"),
        FieldPanel("body"),
    ]

    parent_page_types = ["articles.ArticleIndexPage"]
    subpage_types = []

    class Meta:
        verbose_name = "Статья"
        verbose_name_plural = "Статьи"

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        from articles.forms import CommentForm

        images_qs = CommentImage.objects.order_by("sort_order", "id")
        roots = (
            Comment.objects.filter(article=self, parent__isnull=True)
            .select_related("author")
            .prefetch_related(
                models.Prefetch("images", queryset=images_qs),
                models.Prefetch(
                    "replies",
                    queryset=(
                        Comment.objects.select_related("author")
                        .prefetch_related(models.Prefetch("images", queryset=images_qs))
                        .order_by("created_at")
                    ),
                ),
            )
            .order_by("created_at")
        )
        roots_list = list(roots)
        context["comments"] = roots_list
        context["comments_preview"] = roots_list[:3]
        context["comment_form"] = CommentForm()
        context["comments_count"] = Comment.objects.filter(article=self).count()
        has_unpublished = False
        if request.user.is_authenticated and request.user.is_superuser and self.live:
            latest = self.get_latest_revision()
            live_rev = self.live_revision
            has_unpublished = bool(latest and live_rev and latest.pk != live_rev.pk)
        context["has_unpublished_draft"] = has_unpublished
        return context


class Comment(models.Model):
    article = models.ForeignKey(
        ArticlePage,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Статья",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="article_comments",
        verbose_name="Автор",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
        verbose_name="Ответ на",
    )
    body = models.TextField("Текст", max_length=5000, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    is_deleted = models.BooleanField(
        "Скрыт на сайте",
        default=False,
        help_text="Мягкое скрытие для посетителей. Чтобы убрать запись совсем, используйте «Удалить».",
    )

    class Meta:
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        ordering = ["created_at"]

    def __str__(self):
        return f"#{self.pk} {self.body_preview()}"

    def article_preview(self) -> str:
        """Короткое название статьи для списков в админке."""
        title = getattr(self.article, "title", "") or ""
        return Truncator(title).words(4, truncate="…")

    article_preview.short_description = "Статья"
    article_preview.admin_order_field = "article__title"

    def body_preview(self) -> str:
        """Начало текста комментария для списков в админке."""
        text = (self.body or "").strip()
        if not text:
            return "«фото»" if self.pk and self.images.exists() else "—"
        return Truncator(text).words(8, truncate="…")

    body_preview.short_description = "Текст"

    def clean(self):
        if self.parent_id:
            parent = self.parent
            if parent is None:
                return
            if parent.parent_id is not None:
                raise ValidationError("Отвечать можно только на комментарий верхнего уровня.")
            if parent.article_id != self.article_id:
                raise ValidationError("Ответ должен относиться к той же статье.")

    def save(self, *args, skip_validation=False, **kwargs):
        if not skip_validation:
            self.full_clean()
        return super().save(*args, **kwargs)

    def soft_delete(self):
        self.is_deleted = True
        return self.save(update_fields=["is_deleted"], skip_validation=True)

    def can_delete(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if self.is_deleted:
            return False
        return user.is_staff or user.pk == self.author_id

    def can_edit(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if self.is_deleted:
            return False
        return user.pk == self.author_id

    @property
    def author_label(self) -> str:
        full_name = self.author.get_full_name().strip()
        if full_name:
            return full_name
        if self.author.email:
            return self.author.email
        return self.author.get_username()


class CommentImage(models.Model):
    """Иллюстрация к комментарию (не больше трёх на один комментарий)."""

    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="Комментарий",
    )
    image = models.ImageField("Изображение", upload_to="comment_images/%Y/%m/")
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Изображение комментария"
        verbose_name_plural = "Изображения комментариев"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"Рис. к комментарию #{self.comment_id}"

    def delete(self, *args, **kwargs):
        storage = self.image.storage
        name = self.image.name
        result = super().delete(*args, **kwargs)
        if name:
            storage.delete(name)
        return result
