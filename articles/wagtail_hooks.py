from wagtail.admin.panels import FieldPanel, FieldRowPanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from articles.models import Comment


class CommentViewSet(SnippetViewSet):
    """Комментарии в боковом меню Wagtail — можно просматривать и удалять."""

    model = Comment
    icon = "comment"
    menu_label = "Комментарии"
    menu_name = "comments"
    menu_order = 250
    add_to_admin_menu = True
    list_display = ("id", "article", "author", "is_deleted", "created_at")
    list_filter = ("is_deleted", "created_at")
    search_fields = ("body", "author__email", "author__first_name", "author__last_name")
    ordering = ("-created_at",)
    copy_view_enabled = False
    panels = [
        FieldPanel("article"),
        FieldRowPanel(
            [
                FieldPanel("author"),
                FieldPanel("parent"),
            ]
        ),
        FieldPanel("body"),
        FieldPanel("is_deleted"),
        FieldPanel("created_at", read_only=True),
    ]


register_snippet(CommentViewSet)
