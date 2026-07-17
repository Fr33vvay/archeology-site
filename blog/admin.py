from django.contrib import admin, messages

from blog.models import BlogComment, BlogPost, BlogPostImage


class BlogPostImageInline(admin.TabularInline):
    model = BlogPostImage
    extra = 0
    fields = ("image", "sort_order")


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("id", "body_preview", "author", "is_deleted", "created_at")
    list_filter = ("is_deleted", "created_at")
    search_fields = ("body", "author__email", "author__username")
    raw_id_fields = ("author",)
    readonly_fields = ("created_at",)
    inlines = (BlogPostImageInline,)
    actions = ("soft_delete_selected", "hard_delete_selected")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("images")

    @admin.action(description="Пометить удалёнными (мягко)")
    def soft_delete_selected(self, request, queryset):
        updated = 0
        for post in queryset.filter(is_deleted=False):
            post.soft_delete()
            updated += 1
        self.message_user(request, f"Помечено удалёнными: {updated}.", messages.SUCCESS)

    @admin.action(description="Удалить из базы навсегда")
    def hard_delete_selected(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"Удалено навсегда: {count}.", messages.WARNING)


@admin.register(BlogComment)
class BlogCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "body_preview", "author", "is_deleted", "created_at")
    list_filter = ("is_deleted", "created_at")
    search_fields = ("body", "author__email", "author__username")
    raw_id_fields = ("post", "author")
    readonly_fields = ("created_at",)
    actions = ("soft_delete_selected", "hard_delete_selected")

    @admin.action(description="Пометить удалёнными (мягко)")
    def soft_delete_selected(self, request, queryset):
        updated = 0
        for comment in queryset.filter(is_deleted=False):
            comment.soft_delete()
            updated += 1
        self.message_user(request, f"Помечено удалёнными: {updated}.", messages.SUCCESS)

    @admin.action(description="Удалить из базы навсегда")
    def hard_delete_selected(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"Удалено навсегда: {count}.", messages.WARNING)
