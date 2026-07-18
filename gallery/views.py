"""Редактирование подписей фото галереи с сайта (только суперпользователь)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from gallery.models import GalleryPhoto


def _require_superuser(user):
    if not user.is_authenticated or not user.is_superuser:
        return HttpResponseForbidden(
            "Редактировать подписи может только суперпользователь."
        )
    return None


@login_required
@require_http_methods(["GET", "POST"])
def edit_photo_caption(request, photo_id):
    denied = _require_superuser(request.user)
    if denied:
        return denied

    photo = get_object_or_404(
        GalleryPhoto.objects.select_related("page", "image"), pk=photo_id
    )
    folder = photo.page

    if request.method == "POST":
        caption = (request.POST.get("caption") or "").strip()[:255]
        photo.caption = caption
        photo.save(update_fields=["caption"])
        messages.success(request, "Подпись сохранена.")
        return redirect(folder.url or "/")

    return render(
        request,
        "gallery/edit_photo_caption.html",
        {
            "photo": photo,
            "folder": folder,
        },
    )
