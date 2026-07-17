from wagtail.admin.panels import FieldPanel, HelpPanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from blog.models import BlogComment, BlogPost


class BlogPostViewSet(SnippetViewSet):
    """Посты блога в боковом меню Wagtail — можно просматривать и скрывать/удалять."""

    model = BlogPost
    icon = "doc-full"
    menu_label = "Посты блога"
    menu_name = "blog-posts"
    menu_order = 260
    add_to_admin_menu = True
    list_display = ("id", "body_preview", "author", "is_deleted", "created_at")
    list_filter = ("is_deleted", "created_at")
    search_fields = ("body", "author__email", "author__first_name", "author__last_name")
    ordering = ("-created_at",)
    copy_view_enabled = False
    inspect_view_enabled = True
    list_per_page = 50
    panels = [
        HelpPanel(
            content=(
                "Публиковать новые посты можно только со страницы «Блог» на сайте. "
                "Здесь можно скрыть пост от посетителей или удалить его совсем."
            )
        ),
        FieldPanel("author"),
        FieldPanel("body"),
        FieldPanel("is_deleted"),
        FieldPanel("created_at", read_only=True),
    ]

    def get_queryset(self, request):
        return BlogPost.objects.select_related("author").prefetch_related("images").all()


class BlogCommentViewSet(SnippetViewSet):
    """Комментарии к постам блога в боковом меню Wagtail."""

    model = BlogComment
    icon = "comment"
    menu_label = "Комментарии блога"
    menu_name = "blog-comments"
    menu_order = 270
    add_to_admin_menu = True
    list_display = ("id", "post", "body_preview", "author", "is_deleted", "created_at")
    list_filter = ("is_deleted", "created_at")
    search_fields = ("body", "author__email", "author__first_name", "author__last_name")
    ordering = ("-created_at",)
    copy_view_enabled = False
    inspect_view_enabled = True
    list_per_page = 50
    panels = [
        HelpPanel(
            content=(
                "Чтобы полностью убрать комментарий, откройте его и нажмите «Удалить». "
                "Галочка «Скрыт на сайте» только прячет текст у посетителей."
            )
        ),
        FieldPanel("post"),
        FieldPanel("author"),
        FieldPanel("body"),
        FieldPanel("is_deleted"),
        FieldPanel("created_at", read_only=True),
    ]

    def get_queryset(self, request):
        return BlogComment.objects.select_related("post", "author").all()


register_snippet(BlogPostViewSet)
register_snippet(BlogCommentViewSet)
