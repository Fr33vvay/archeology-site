from django.contrib import admin

from maps.models import MapPoint


@admin.register(MapPoint)
class MapPointAdmin(admin.ModelAdmin):
    list_display = ("title", "article", "lat", "lon", "anchor_id", "updated_at")
    list_filter = ("article",)
    search_fields = ("title", "anchor_id", "article__title")
