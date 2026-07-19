"""Редактирование статей на сайте (только суперпользователь)."""

from __future__ import annotations

import json
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods, require_POST
from PIL import Image as PILImage
from wagtail.images.models import Image as WagtailImage
from wagtail.models import Page

from articles.models import ArticleIndexPage, ArticlePage
from maps.sync import sync_article_map_points
from maps.views import serialize_map_points_for_editor


def _require_superuser(user):
    if not user.is_authenticated or not user.is_superuser:
        return HttpResponseForbidden("Редактировать статьи может только суперпользователь.")
    return None


def _unique_slug(parent: Page, base: str) -> str:
    base = slugify(base)[:180] or "statya"
    slug = base
    n = 2
    while Page.objects.child_of(parent).filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


def _parse_blocks(raw: str) -> list:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError("Некорректные данные блоков.") from exc
    if not isinstance(data, list):
        raise ValueError("Ожидался список блоков.")

    allowed = {"heading", "paragraph", "quote", "image", "gallery"}
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        btype = item.get("type")
        if btype not in allowed:
            continue
        value = item.get("value")
        if btype == "heading":
            text = str(value or "").strip()
            if text:
                result.append({"type": "heading", "value": text})
        elif btype == "paragraph":
            html = str(value or "").strip()
            if html:
                result.append({"type": "paragraph", "value": html})
        elif btype == "quote":
            text = str(value or "").strip()
            if text:
                result.append({"type": "quote", "value": text})
        elif btype == "image":
            if not isinstance(value, dict):
                continue
            image_id = value.get("image")
            if not image_id:
                continue
            result.append(
                {
                    "type": "image",
                    "value": {
                        "image": int(image_id),
                        "caption": str(value.get("caption") or "")[:255],
                    },
                }
            )
        elif btype == "gallery":
            if not isinstance(value, dict):
                continue
            images = []
            for img in value.get("images") or []:
                if not isinstance(img, dict) or not img.get("image"):
                    continue
                images.append(
                    {
                        "image": int(img["image"]),
                        "caption": str(img.get("caption") or "")[:255],
                    }
                )
            if images:
                result.append(
                    {
                        "type": "gallery",
                        "value": {
                            "title": str(value.get("title") or "")[:120],
                            "images": images,
                        },
                    }
                )
    return result


def _blocks_for_editor(page: ArticlePage) -> list:
    """Сериализация StreamField для JS-редактора."""
    out = []
    for block in page.body:
        if block.block_type == "heading":
            out.append({"type": "heading", "value": str(block.value)})
        elif block.block_type == "paragraph":
            source = getattr(block.value, "source", None)
            out.append({"type": "paragraph", "value": source if source is not None else str(block.value)})
        elif block.block_type == "quote":
            out.append({"type": "quote", "value": str(block.value)})
        elif block.block_type == "image":
            img = block.value.get("image")
            out.append(
                {
                    "type": "image",
                    "value": {
                        "image": img.pk if img else None,
                        "caption": block.value.get("caption") or "",
                        "preview_url": img.file.url if img else "",
                    },
                }
            )
        elif block.block_type == "gallery":
            images = []
            for item in block.value.get("images") or []:
                img = item.get("image")
                images.append(
                    {
                        "image": img.pk if img else None,
                        "caption": item.get("caption") or "",
                        "preview_url": img.file.url if img else "",
                    }
                )
            out.append(
                {
                    "type": "gallery",
                    "value": {
                        "title": block.value.get("title") or "",
                        "images": images,
                    },
                }
            )
    return out


def _apply_page_fields(page: ArticlePage, request) -> None:
    title = (request.POST.get("title") or "").strip()
    if not title:
        raise ValueError("Укажите название статьи.")
    page.title = title
    page.intro = (request.POST.get("intro") or "").strip()[:500]
    page.body = _parse_blocks(request.POST.get("blocks_json", "[]"))


@login_required
@require_http_methods(["GET", "POST"])
def edit_article(request, page_id):
    denied = _require_superuser(request.user)
    if denied:
        return denied

    page = get_object_or_404(ArticlePage.objects.all(), pk=page_id)
    # Редактируем последнюю ревизию (черновик), а не только live
    page = page.get_latest_revision_as_object()

    if request.method == "POST":
        action = request.POST.get("action") or "draft"
        try:
            _apply_page_fields(page, request)
        except (ValueError, TypeError) as exc:
            messages.error(request, str(exc))
            return redirect("article_edit", page_id=page_id)

        revision = page.save_revision(user=request.user, log_action=True)
        sync_article_map_points(page, blocks=page.body)
        if action == "publish":
            revision.publish(user=request.user)
            messages.success(request, "Статья опубликована.")
            return redirect(page.get_url(request) or "/")
        messages.success(request, "Черновик сохранён. На сайте пока прежняя версия.")
        return redirect("article_edit", page_id=page_id)

    has_unpublished = False
    if page.live:
        latest = page.get_latest_revision()
        live_rev = page.live_revision
        has_unpublished = bool(latest and live_rev and latest.pk != live_rev.pk)

    return render(
        request,
        "articles/article_edit.html",
        {
            "page": page,
            "article": page,
            "blocks_json": json.dumps(_blocks_for_editor(page), ensure_ascii=False),
            "has_unpublished_draft": has_unpublished,
            "is_new": False,
            "map_point_create_url": "/maps/points/",
            "map_points_editor_json": json.dumps(
                serialize_map_points_for_editor(request), ensure_ascii=False
            ),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def create_article(request):
    denied = _require_superuser(request.user)
    if denied:
        return denied

    parent = ArticleIndexPage.objects.live().first()
    if not parent:
        messages.error(request, "Раздел «Статьи» не найден.")
        return redirect("/")

    if request.method == "POST":
        action = request.POST.get("action") or "draft"
        try:
            title = (request.POST.get("title") or "").strip()
            if not title:
                raise ValueError("Укажите название статьи.")
            article = ArticlePage(
                title=title,
                slug=_unique_slug(parent, title),
                intro=(request.POST.get("intro") or "").strip()[:500],
                live=False,
                owner=request.user,
            )
            article.body = _parse_blocks(request.POST.get("blocks_json", "[]"))
            parent.add_child(instance=article)
            revision = article.save_revision(user=request.user, log_action=True)
            sync_article_map_points(article, blocks=article.body)
            if action == "publish":
                revision.publish(user=request.user)
                messages.success(request, "Статья создана и опубликована.")
                return redirect(article.get_url(request) or "/")
            messages.success(request, "Черновик статьи создан (на сайте ещё не виден).")
            return redirect("article_edit", page_id=article.pk)
        except (ValueError, TypeError) as exc:
            messages.error(request, str(exc))
            return redirect("article_create")

    empty = ArticlePage(title="", intro="")
    return render(
        request,
        "articles/article_edit.html",
        {
            "page": empty,
            "article": empty,
            "blocks_json": "[]",
            "has_unpublished_draft": False,
            "is_new": True,
            "map_point_create_url": "/maps/points/",
            "map_points_editor_json": json.dumps(
                serialize_map_points_for_editor(request), ensure_ascii=False
            ),
        },
    )


@login_required
@require_POST
def upload_article_image(request):
    denied = _require_superuser(request.user)
    if denied:
        return denied

    uploaded = request.FILES.get("image")
    if not uploaded:
        return JsonResponse({"error": "Файл не передан."}, status=400)
    if uploaded.size > 8 * 1024 * 1024:
        return JsonResponse({"error": "Файл больше 8 МБ."}, status=400)

    try:
        PILImage.open(uploaded).verify()
        uploaded.seek(0)
    except Exception:
        return JsonResponse({"error": "Нужен файл изображения."}, status=400)

    title = (request.POST.get("title") or uploaded.name or "Иллюстрация")[:255]
    title = re.sub(r"\.[^.]+$", "", title) or "Иллюстрация"
    image = WagtailImage(title=title, file=uploaded)
    image.save()
    return JsonResponse(
        {
            "id": image.pk,
            "title": image.title,
            "url": image.file.url,
        }
    )
