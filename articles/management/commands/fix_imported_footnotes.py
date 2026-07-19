"""Пересобирает тело импортированных статей из HTML LibreOffice с рабочими сносками."""

from __future__ import annotations

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from wagtail.images.models import Image as WagtailImage

from articles.management.commands.import_papa_articles import (
    HTML_SUFFIXES,
    ParsedDoc,
    materialize_blocks,
    parse_html_document,
    title_from_filename,
)
from articles.models import ArticlePage


def _existing_image_ids(page: ArticlePage) -> list[int]:
    ids: list[int] = []
    for block in page.body:
        if block.block_type != "image":
            continue
        image = block.value.get("image")
        if image is None:
            continue
        pk = image.pk if isinstance(image, WagtailImage) else int(image)
        ids.append(pk)
    return ids


def _reuse_images(parsed_blocks: list[dict], old_image_ids: list[int], article_title: str, owner) -> list:
    """Подставляет уже загруженные картинки по порядку; недостающие создаёт заново."""
    result: list[dict] = []
    reused = 0
    need_materialize: list[dict] = []
    placeholders: list[int] = []

    for block in parsed_blocks:
        if block["type"] != "image":
            result.append(block)
            continue
        caption = (block["value"].get("caption") or "")[:255]
        if reused < len(old_image_ids):
            result.append(
                {
                    "type": "image",
                    "value": {"image": old_image_ids[reused], "caption": caption},
                }
            )
            reused += 1
            continue
        placeholders.append(len(result))
        result.append({"type": "image", "value": {"image": None, "caption": caption}})
        need_materialize.append(block)

    if need_materialize:
        materialized = materialize_blocks(
            ParsedDoc(title=article_title, intro="", blocks=need_materialize),
            article_title,
            owner,
        )
        for idx, mat in zip(placeholders, materialized):
            result[idx] = mat

    return [b for b in result if not (b["type"] == "image" and b["value"]["image"] is None)]


class Command(BaseCommand):
    help = (
        "Для статей, импортированных из HTML LibreOffice, заново собирает body "
        "с конвертацией сносок в #fn-/#fnref- (картинки по возможности сохраняет)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "html_dir",
            type=str,
            help="Каталог с подкаталогами .html (как /tmp/papa-html)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что будет обновлено",
        )
        parser.add_argument(
            "--slug",
            action="append",
            default=[],
            help="Ограничить slug статьи (можно несколько раз)",
        )

    def handle(self, *args, **options):
        html_dir = Path(options["html_dir"]).expanduser().resolve()
        if not html_dir.is_dir():
            raise CommandError(f"Каталог не найден: {html_dir}")

        dry_run = options["dry_run"]
        only_slugs = set(options["slug"] or [])

        html_files = sorted(
            p for p in html_dir.rglob("*") if p.is_file() and p.suffix.lower() in HTML_SUFFIXES
        )
        if not html_files:
            raise CommandError(f"В {html_dir} нет .html")

        # title → html path (первый подходящий)
        by_title: dict[str, Path] = {}
        for hp in html_files:
            title = title_from_filename(hp.name)
            by_title.setdefault(title, hp)

        User = get_user_model()
        owner = User.objects.filter(is_superuser=True).order_by("pk").first()

        updated: list[str] = []
        skipped: list[str] = []

        articles = ArticlePage.objects.live().specific()
        if only_slugs:
            articles = articles.filter(slug__in=only_slugs)

        for page in articles:
            html_path = by_title.get(page.title)
            if html_path is None:
                skipped.append(f"{page.slug}: нет HTML для title «{page.title}»")
                continue

            parsed = parse_html_document(html_path, page.title)
            has_fn = any(
                b["type"] == "paragraph" and "#fn-" in b["value"] for b in parsed.blocks
            )
            source_html = html_path.read_text(encoding="utf-8", errors="replace").lower()
            source_has_notes = "sdfootnote" in source_html or "sdendnote" in source_html

            if not source_has_notes and not has_fn:
                skipped.append(f"{page.slug}: в источнике нет сносок")
                continue

            n_fn_refs = sum(
                b["value"].count('href="#fn-')
                for b in parsed.blocks
                if b["type"] == "paragraph"
            )
            self.stdout.write(
                f"{'DRY ' if dry_run else ''}"
                f"UPDATE {page.slug} «{page.title}» ← {html_path.name} refs={n_fn_refs}"
            )

            if dry_run:
                updated.append(f"{page.slug} (dry-run, refs={n_fn_refs})")
                continue

            old_images = _existing_image_ids(page)
            body = _reuse_images(parsed.blocks, old_images, page.title, owner)

            with transaction.atomic():
                page.body = body
                if not page.intro and parsed.intro:
                    page.intro = parsed.intro
                revision = page.save_revision(user=owner, log_action=True)
                revision.publish(user=owner)

            updated.append(f"{page.slug} → refs={n_fn_refs}, blocks={len(body)}")
            self.stdout.write(self.style.SUCCESS(f"OK {page.slug}"))

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("=== ИТОГ ==="))
        self.stdout.write(f"Обновлено: {len(updated)}")
        for line in updated:
            self.stdout.write(f"  + {line}")
        self.stdout.write(f"Пропущено: {len(skipped)}")
        for line in skipped:
            self.stdout.write(f"  - {line}")
