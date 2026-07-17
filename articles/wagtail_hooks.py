from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.panels import FieldPanel, FieldRowPanel, HelpPanel
from wagtail.snippets.bulk_actions.snippet_bulk_action import SnippetBulkAction
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
    list_display = (
        "id",
        "article_preview",
        "body_preview",
        "author",
        "is_deleted",
        "created_at",
    )
    list_filter = ("is_deleted", "created_at")
    search_fields = (
        "body",
        "author__email",
        "author__first_name",
        "author__last_name",
        "article__title",
    )
    ordering = ("-created_at",)
    copy_view_enabled = False
    inspect_view_enabled = True
    list_per_page = 50
    panels = [
        HelpPanel(
            content=(
                "Чтобы полностью убрать тестовые комментарии с сайта, "
                "отметьте их в списке и выберите действие «Удалить навсегда», "
                "либо откройте комментарий и нажмите «Удалить». "
                "Галочка «Скрыт на сайте» только прячет текст у посетителей."
            )
        ),
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

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("article", "author")
            .prefetch_related("images")
        )


register_snippet(CommentViewSet)


class DeleteCommentsForeverBulkAction(SnippetBulkAction):
    """Явное полное удаление выбранных комментариев из базы."""

    display_name = _("Удалить навсегда")
    aria_label = _("Удалить выбранные комментарии из базы")
    action_type = "delete_comments_forever"
    template_name = "wagtailadmin/bulk_actions/confirmation/delete.html"
    models = [Comment]

    @classmethod
    def execute_action(cls, objects, **kwargs):
        count = 0
        for obj in objects:
            obj.delete()
            count += 1
        return count, 0


hooks.register("register_bulk_action", DeleteCommentsForeverBulkAction)
