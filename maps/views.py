"""API точек карты (только суперпользователь)."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from articles.models import ArticlePage
from maps.models import MapPage, MapPoint


def _require_superuser(user):
    if not user.is_authenticated or not user.is_superuser:
        return HttpResponseForbidden("Точки на карте может создавать только суперпользователь.")
    return None


def _map_page_url(request) -> str:
    page = MapPage.objects.live().public().first()
    if page:
        return page.get_url(request) or page.url or "/map/"
    return "/map/"


def serialize_map_points_for_editor(request=None) -> list[dict]:
    """Список всех точек для модалки редактора: id, title, lat, lon, map_url."""
    map_base = _map_page_url(request).rstrip("/") if request is not None else "/map"
    points = MapPoint.objects.order_by("title", "id")
    return [
        {
            "id": point.pk,
            "title": point.title,
            "lat": float(point.lat),
            "lon": float(point.lon),
            "map_url": f"{map_base}/?point={point.pk}",
        }
        for point in points
    ]


@login_required
@require_http_methods(["GET", "POST"])
def create_map_point(request):
    denied = _require_superuser(request.user)
    if denied:
        return denied

    if request.method == "GET":
        return JsonResponse(serialize_map_points_for_editor(request), safe=False)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректный JSON."}, status=400)

    article_id = payload.get("article_id")
    title = (payload.get("title") or "").strip()
    if not article_id:
        return JsonResponse({"error": "Укажите статью."}, status=400)
    if not title:
        return JsonResponse({"error": "Укажите подпись точки."}, status=400)

    try:
        lat = Decimal(str(payload.get("lat")))
        lon = Decimal(str(payload.get("lon")))
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({"error": "Некорректные координаты."}, status=400)

    if not (Decimal("-90") <= lat <= Decimal("90") and Decimal("-180") <= lon <= Decimal("180")):
        return JsonResponse({"error": "Координаты вне допустимого диапазона."}, status=400)

    article = get_object_or_404(ArticlePage.objects.all(), pk=article_id)
    point = MapPoint(
        article=article,
        lat=lat.quantize(Decimal("0.000001")),
        lon=lon.quantize(Decimal("0.000001")),
        title=title[:255],
        anchor_id=f"pending-{uuid.uuid4().hex[:12]}",
    )
    point.save()
    point.assign_anchor_id()
    point.save(update_fields=["anchor_id", "updated_at"])

    map_base = _map_page_url(request).rstrip("/")
    map_url = f"{map_base}/?point={point.pk}"
    return JsonResponse(
        {
            "id": point.pk,
            "title": point.title,
            "lat": str(point.lat),
            "lon": str(point.lon),
            "anchor_id": point.anchor_id,
            "map_url": map_url,
            "article_id": article.pk,
        },
        status=201,
    )


@login_required
@require_http_methods(["DELETE", "POST"])
def delete_map_point(request, point_id):
    denied = _require_superuser(request.user)
    if denied:
        return denied

    point = get_object_or_404(MapPoint, pk=point_id)
    point.delete()
    return JsonResponse({"ok": True})
