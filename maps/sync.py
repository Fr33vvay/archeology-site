"""Синхронизация точек карты с телом статьи."""

from __future__ import annotations

import re

from maps.models import MapPoint

# Ссылки вида /map/?point=12 или ?point=12
POINT_ID_RE = re.compile(r"[?&]point=(\d+)", re.IGNORECASE)


def extract_map_point_ids(html: str) -> set[int]:
    """Достаёт id точек из HTML тела статьи."""
    return {int(match.group(1)) for match in POINT_ID_RE.finditer(html or "")}


def body_html_from_blocks(blocks) -> str:
    """Собирает HTML из списка блоков StreamField / редактора."""
    parts: list[str] = []
    if not blocks:
        return ""
    for item in blocks:
        if isinstance(item, dict):
            btype = item.get("type")
            value = item.get("value")
            if btype == "paragraph" and value:
                parts.append(str(value))
            elif btype in {"heading", "quote"} and value:
                parts.append(str(value))
            continue
        # StreamValue / StreamChild
        btype = getattr(item, "block_type", None)
        value = getattr(item, "value", None)
        if btype == "paragraph" and value is not None:
            source = getattr(value, "source", None)
            parts.append(source if source is not None else str(value))
        elif btype in {"heading", "quote"} and value is not None:
            parts.append(str(value))
    return "\n".join(parts)


def sync_article_map_points(article, blocks=None) -> int:
    """Удаляет точки статьи, которых больше нет в теле. Возвращает число удалённых."""
    if article is None or not getattr(article, "pk", None):
        return 0
    html = body_html_from_blocks(blocks if blocks is not None else article.body)
    keep_ids = extract_map_point_ids(html)
    qs = MapPoint.objects.filter(article_id=article.pk)
    if keep_ids:
        deleted, _ = qs.exclude(pk__in=keep_ids).delete()
    else:
        deleted, _ = qs.delete()
    return deleted
