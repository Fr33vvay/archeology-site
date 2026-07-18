from django.conf import settings
from django.db import models
from django.utils.text import Truncator

from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page


class BlogIndexPage(Page):
    """Страница «Блог» — лента постов, видна в меню."""

    intro = RichTextField(blank=True, verbose_name="Вступление")

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    parent_page_types = ["home.HomePage"]
    subpage_types = []
    max_count = 1

    class Meta:
        verbose_name = "Блог"
        verbose_name_plural = "Блоги"

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        from blog.forms import BlogCommentForm, BlogPostForm

        images_qs = BlogPostImage.objects.order_by("sort_order", "id")
        comments_qs = BlogComment.objects.select_related("author").order_by("created_at")
        posts = list(
            BlogPost.objects.filter(is_deleted=False)
            .select_related("author")
            .prefetch_related(
                models.Prefetch("images", queryset=images_qs),
                models.Prefetch("comments", queryset=comments_qs),
            )
            .order_by("-created_at")
        )
        user = request.user
        for post in posts:
            post_comments = list(post.comments.all())
            post.comments_count = len(post_comments)
            post.comments_preview = post_comments[:3]
            post.comments_rest = post_comments[3:]
            post.is_liked = post.is_liked_by(user)
            for comment in post_comments:
                comment.is_liked = comment.is_liked_by(user)

        context["posts"] = posts
        context["post_form"] = BlogPostForm()
        context["comment_form"] = BlogCommentForm()
        return context


class BlogPost(models.Model):
    """Пост в блоге: текст без заголовка + до трёх фото. Создаёт только суперпользователь."""

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_posts",
        verbose_name="Автор",
    )
    body = models.TextField("Текст", max_length=5000, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    views_count = models.PositiveIntegerField("Просмотры", default=0, editable=False)
    is_deleted = models.BooleanField(
        "Скрыт на сайте",
        default=False,
        help_text="Мягкое скрытие для посетителей. Чтобы убрать запись совсем, используйте «Удалить».",
    )

    class Meta:
        verbose_name = "Пост"
        verbose_name_plural = "Посты"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.pk} {self.body_preview()}"

    def body_preview(self) -> str:
        """Начало текста поста для списков в админке."""
        text = (self.body or "").strip()
        if not text:
            return "«фото»" if self.pk and self.images.exists() else "—"
        return Truncator(text).words(8, truncate="…")

    body_preview.short_description = "Текст"

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
        return user.is_superuser or user.pk == self.author_id

    def can_edit(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if self.is_deleted:
            return False
        return user.pk == self.author_id

    def likes_count(self) -> int:
        return self.likes.count()

    def is_liked_by(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        return self.likes.filter(user_id=user.pk).exists()

    @property
    def author_label(self) -> str:
        full_name = self.author.get_full_name().strip()
        if full_name:
            return full_name
        if self.author.email:
            return self.author.email
        return self.author.get_username()


class BlogPostImage(models.Model):
    """Фотография к посту (не больше трёх на один пост)."""

    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="Пост",
    )
    image = models.ImageField("Изображение", upload_to="blog_post_images/%Y/%m/")
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Изображение поста"
        verbose_name_plural = "Изображения постов"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"Рис. к посту #{self.post_id}"

    def delete(self, *args, **kwargs):
        storage = self.image.storage
        name = self.image.name
        result = super().delete(*args, **kwargs)
        if name:
            storage.delete(name)
        return result


class BlogComment(models.Model):
    """Плоский комментарий к посту (без ответов и без фото)."""

    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Пост",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_comments",
        verbose_name="Автор",
    )
    body = models.TextField("Текст", max_length=5000)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    is_deleted = models.BooleanField(
        "Скрыт на сайте",
        default=False,
        help_text="Мягкое скрытие для посетителей. Чтобы убрать запись совсем, используйте «Удалить».",
    )

    class Meta:
        verbose_name = "Комментарий к посту"
        verbose_name_plural = "Комментарии к постам"
        ordering = ["created_at"]

    def __str__(self):
        return f"#{self.pk} {self.body_preview()}"

    def body_preview(self) -> str:
        text = (self.body or "").strip()
        return Truncator(text).words(8, truncate="…") if text else "—"

    body_preview.short_description = "Текст"

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
        return user.pk == self.author_id

    def can_edit(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if self.is_deleted:
            return False
        return user.pk == self.author_id

    def likes_count(self) -> int:
        return self.likes.count()

    def is_liked_by(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        return self.likes.filter(user_id=user.pk).exists()

    @property
    def author_label(self) -> str:
        full_name = self.author.get_full_name().strip()
        if full_name:
            return full_name
        if self.author.email:
            return self.author.email
        return self.author.get_username()


class BlogPostUniqueView(models.Model):
    """Уникальный просмотр поста блога по visitor_key (пользователь или cookie vid)."""

    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name="unique_views",
        verbose_name="Пост",
    )
    visitor_key = models.CharField("Ключ посетителя", max_length=64)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Уникальный просмотр поста"
        verbose_name_plural = "Уникальные просмотры постов"
        constraints = [
            models.UniqueConstraint(
                fields=["post", "visitor_key"],
                name="unique_blog_post_visitor_view",
            ),
        ]

    def __str__(self):
        return f"{self.visitor_key} → пост #{self.post_id}"


class BlogPostLike(models.Model):
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name="likes", verbose_name="Пост")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_post_likes",
        verbose_name="Пользователь",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Лайк поста"
        verbose_name_plural = "Лайки постов"
        constraints = [
            models.UniqueConstraint(fields=["post", "user"], name="unique_blog_post_like"),
        ]

    def __str__(self):
        return f"{self.user} → пост #{self.post_id}"


class BlogCommentLike(models.Model):
    comment = models.ForeignKey(
        BlogComment, on_delete=models.CASCADE, related_name="likes", verbose_name="Комментарий"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_comment_likes",
        verbose_name="Пользователь",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Лайк комментария"
        verbose_name_plural = "Лайки комментариев"
        constraints = [
            models.UniqueConstraint(fields=["comment", "user"], name="unique_blog_comment_like"),
        ]

    def __str__(self):
        return f"{self.user} → комментарий #{self.comment_id}"
