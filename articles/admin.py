from django.contrib import admin

from articles.models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "article", "author", "parent", "is_deleted", "created_at")
    list_filter = ("is_deleted", "created_at")
    search_fields = ("body", "author__email", "author__username", "article__title")
    raw_id_fields = ("article", "author", "parent")
    readonly_fields = ("created_at",)
