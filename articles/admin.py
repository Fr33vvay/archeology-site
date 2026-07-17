from django.contrib import admin, messages

from articles.models import Comment, CommentImage


class CommentImageInline(admin.TabularInline):
    model = CommentImage
    extra = 0
    fields = ("image", "sort_order")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "article_preview",
        "body_preview",
        "author",
        "parent",
        "is_deleted",
        "created_at",
    )
    list_filter = ("is_deleted", "created_at")
    search_fields = (
        "body",
        "author__email",
        "author__username",
        "author__first_name",
        "author__last_name",
        "article__title",
    )
    raw_id_fields = ("article", "author", "parent")
    readonly_fields = ("created_at",)
    inlines = (CommentImageInline,)
    actions = ("soft_delete_selected", "hard_delete_selected")
    list_select_related = ("article", "author")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("images")

    @admin.action(description="Пометить удалёнными (мягко)")
    def soft_delete_selected(self, request, queryset):
        updated = 0
        for comment in queryset.filter(is_deleted=False):
            comment.soft_delete()
            updated += 1
        self.message_user(
            request,
            f"Помечено удалёнными: {updated}.",
            messages.SUCCESS,
        )

    @admin.action(description="Удалить из базы навсегда")
    def hard_delete_selected(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(
            request,
            f"Удалено навсегда: {count}.",
            messages.WARNING,
        )
