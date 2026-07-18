"""Общая логика уникальных просмотров (visitor_key + cookie vid)."""

from __future__ import annotations

import re
import uuid

from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import HttpRequest, JsonResponse

VID_COOKIE = "vid"
VID_MAX_AGE = 365 * 24 * 60 * 60
_VID_RE = re.compile(r"^[0-9a-f]{32}$")


def ru_views_word(count: int) -> str:
    """Склонение слова «просмотр» для числа count."""
    n = abs(int(count)) % 100
    if 11 <= n <= 14:
        return "просмотров"
    n = n % 10
    if n == 1:
        return "просмотр"
    if 2 <= n <= 4:
        return "просмотра"
    return "просмотров"


def resolve_visitor_key(request: HttpRequest) -> tuple[str, str | None]:
    """
    Возвращает (visitor_key, новый_vid_или_None).
    Для гостя при отсутствии cookie генерирует UUID hex.
    """
    if request.user.is_authenticated:
        return f"u:{request.user.pk}", None

    existing = request.COOKIES.get(VID_COOKIE, "")
    if _VID_RE.fullmatch(existing):
        return existing, None

    new_vid = uuid.uuid4().hex
    return new_vid, new_vid


def attach_vid_cookie(response: JsonResponse, new_vid: str | None) -> JsonResponse:
    if new_vid:
        response.set_cookie(
            VID_COOKIE,
            new_vid,
            max_age=VID_MAX_AGE,
            samesite="Lax",
            httponly=False,
            path="/",
        )
    return response


def record_unique_view(
    *,
    request: HttpRequest,
    content_obj,
    view_model,
    fk_field: str,
    author_id: int | None = None,
):
    """
    Создаёт запись уникального просмотра и инкрементирует views_count при первом визите.
    Просмотр автора (author_id) не учитывается. Возвращает JsonResponse {count, created}.
    """
    if (
        author_id is not None
        and request.user.is_authenticated
        and request.user.pk == author_id
    ):
        content_obj.refresh_from_db(fields=["views_count"])
        return JsonResponse({"count": content_obj.views_count, "created": False})

    visitor_key, new_vid = resolve_visitor_key(request)
    created = False
    try:
        with transaction.atomic():
            view_model.objects.create(**{fk_field: content_obj, "visitor_key": visitor_key})
            type(content_obj).objects.filter(pk=content_obj.pk).update(
                views_count=F("views_count") + 1
            )
            created = True
    except IntegrityError:
        created = False

    content_obj.refresh_from_db(fields=["views_count"])
    response = JsonResponse({"count": content_obj.views_count, "created": created})
    return attach_vid_cookie(response, new_vid)
