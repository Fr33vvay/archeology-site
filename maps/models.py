from decimal import Decimal

from django.db import models
from django.utils.text import slugify

from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page


class MapPage(Page):
    """Страница карты объектов (Санкт-Петербург), одна на сайт."""

    intro = RichTextField(blank=True, verbose_name="Вступление")

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    parent_page_types = ["home.HomePage"]
    subpage_types = []
    max_count = 1

    class Meta:
        verbose_name = "Карта"
        verbose_name_plural = "Карты"

    def get_context(self, request, *args, **kwargs):
        import json

        from django.conf import settings

        context = super().get_context(request, *args, **kwargs)
        points = list(
            MapPoint.objects.select_related("article").order_by("title", "id")
        )
        focus_raw = (request.GET.get("point") or "").strip()
        focus_point_id = None
        if focus_raw.isdigit():
            focus_point_id = int(focus_raw)

        map_points_data = []
        for point in points:
            article_url = ""
            if point.article_id:
                try:
                    base = point.article.get_url(request) or point.article.url or ""
                except Exception:
                    base = point.article.url or ""
                if base:
                    article_url = f"{base.rstrip('/')}#{point.anchor_id}"
            map_points_data.append(
                {
                    "id": point.pk,
                    "lat": float(point.lat),
                    "lon": float(point.lon),
                    "title": point.title,
                    "anchor_id": point.anchor_id,
                    "article_url": article_url,
                    "article_title": point.article.title if point.article_id else "",
                }
            )

        api_key = getattr(settings, "YANDEX_MAPS_API_KEY", "") or ""
        context["map_points"] = points
        context["map_points_json"] = map_points_data
        context["map_points_json_text"] = json.dumps(map_points_data, ensure_ascii=False)
        context["focus_point_id"] = focus_point_id
        context["yandex_maps_api_key"] = api_key
        context["map_available"] = bool(api_key.strip())
        return context


class MapPoint(models.Model):
    """Точка на карте, связанная со статьёй и якорем в тексте."""

    article = models.ForeignKey(
        "articles.ArticlePage",
        on_delete=models.CASCADE,
        related_name="map_points",
        verbose_name="Статья",
    )
    lat = models.DecimalField("Широта", max_digits=9, decimal_places=6)
    lon = models.DecimalField("Долгота", max_digits=9, decimal_places=6)
    title = models.CharField("Подпись", max_length=255)
    anchor_id = models.SlugField("Якорь в статье", max_length=80)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        verbose_name = "Точка на карте"
        verbose_name_plural = "Точки на карте"
        ordering = ["title", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["article", "anchor_id"],
                name="unique_article_map_anchor",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.lat}, {self.lon})"

    @staticmethod
    def make_anchor_id(title: str, point_id: int | None = None) -> str:
        base = slugify(title, allow_unicode=True)[:40] or "point"
        if point_id:
            return f"map-point-{point_id}-{base}"[:80]
        return f"map-point-{base}"[:80]

    def assign_anchor_id(self) -> None:
        """Выставляет якорь после появления pk (уникальный в рамках статьи)."""
        if self.pk and self.anchor_id and str(self.pk) in self.anchor_id:
            return
        base = slugify(self.title, allow_unicode=True)[:40] or "point"
        candidate = f"map-point-{self.pk}-{base}"[:80]
        self.anchor_id = candidate
