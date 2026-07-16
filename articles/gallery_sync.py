"""Синхронизация иллюстраций статьи с папкой галереи."""

from __future__ import annotations

from django.db import transaction


def extract_illustrations(article):
    """Возвращает список (image, caption) без дублей, в порядке появления в статье."""
    items = []
    seen = set()

    for block in article.body:
        if block.block_type == "image":
            image = block.value.get("image")
            caption = block.value.get("caption") or ""
            if image and image.pk not in seen:
                seen.add(image.pk)
                items.append((image, caption))
        elif block.block_type == "gallery":
            for item in block.value.get("images") or []:
                image = item.get("image")
                caption = item.get("caption") or ""
                if image and image.pk not in seen:
                    seen.add(image.pk)
                    items.append((image, caption))

    return items


def _slug_taken(parent, slug: str) -> bool:
    return parent.get_children().filter(slug=slug).exists()


def _unique_child_slug(parent, base: str) -> str:
    candidate = base
    n = 2
    while _slug_taken(parent, candidate):
        suffix = f"-{n}"
        candidate = f"{base[:50 - len(suffix)]}{suffix}"
        n += 1
    return candidate


@transaction.atomic
def sync_gallery_folder_for_article(article):
    """
    Создаёт или обновляет папку галереи с названием статьи
    и загружает туда все иллюстрации из содержания.
    """
    from gallery.models import GalleryFolderPage, GalleryIndexPage, GalleryPhoto

    gallery_index = GalleryIndexPage.objects.first()
    if gallery_index is None:
        return None

    illustrations = extract_illustrations(article)
    folder = GalleryFolderPage.objects.filter(source_article=article).first()
    base_slug = f"article-{article.slug}"[:50] or "article"

    if folder is None:
        slug = base_slug if not _slug_taken(gallery_index, base_slug) else _unique_child_slug(
            gallery_index, base_slug
        )
        folder = GalleryFolderPage(
            title=article.title[:255],
            slug=slug,
            draft_title=article.title[:255],
            source_article=article,
            intro=f"<p>Иллюстрации к статье «{article.title}».</p>",
            show_in_menus=False,
        )
        gallery_index.add_child(instance=folder)
    else:
        folder.title = article.title[:255]
        folder.draft_title = article.title[:255]
        folder.intro = f"<p>Иллюстрации к статье «{article.title}».</p>"
        folder.save()

    folder.photos.all().delete()
    for order, (image, caption) in enumerate(illustrations):
        GalleryPhoto.objects.create(
            page=folder,
            image=image,
            caption=(caption or "")[:255],
            sort_order=order,
        )

    folder.save_revision().publish()
    return folder
