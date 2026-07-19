"""Импорт статей из Word/ODT (через HTML LibreOffice) в ArticlePage."""

from __future__ import annotations

import gc
import html as html_module
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from wagtail.images.models import Image as WagtailImage
from wagtail.models import Page

from articles.models import ArticleIndexPage, ArticlePage

SOURCE_SUFFIXES = {".doc", ".docx", ".odt", ".DOC", ".DOCX", ".ODT"}
HTML_SUFFIXES = {".html", ".htm"}

# Файлы, которые заведомо не статьи или дубликаты (берём парный вариант).
SKIP_FILENAMES = {
    "мои статьи в сети.docx",
    # дубликат «Реставрация Летнего дворца.doc» (тот же размер) — оставляем полное имя
    "реставрация летнего дв. картинки.doc",
    "харлампий — копия.odt",
    "харлампий - копия.odt",
}

# Шум в конце/середине имени файла. «илл»/«ил.» — только отдельным словом (не внутри «Филлимонов»).
TITLE_NOISE_RES = (
    re.compile(r"(?i)\s*[—–-]\s*копия\s*$"),
    re.compile(r"(?i)[,.]?\s*\b(?:картинки|картинка|иллюстрац\w*|копия)\b"),
    # «с ил.» / «с илл.» в конце имени
    re.compile(r"(?i)\s+с\s+илл?\.+\s*$"),
    # отдельное слово «илл» / «ил.» — не часть «Филлимонов»
    re.compile(r"(?i)[,.]?\s*\bилл\b\.?"),
    re.compile(r"(?i)[,.]?\s*\bил\b\.+"),
)
MULTISPACE_RE = re.compile(r"\s+")
TRAILING_PUNCT_RE = re.compile(r"[\s.,;:–—-]+$")

# Простая транслитерация для латиницы в slug (Django slugify без unicode даёт пусто).
_CYR_MAP = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

ALLOWED_INLINE = {
    "b",
    "strong",
    "i",
    "em",
    "u",
    "a",
    "br",
    "sup",
    "sub",
    "ul",
    "ol",
    "li",
}


@dataclass
class ParsedDoc:
    title: str
    intro: str
    blocks: list = field(default_factory=list)  # StreamField-ready dicts with image paths still as Path
    plain_text: str = ""


def title_from_filename(name: str) -> str:
    stem = Path(name).stem
    for pattern in TITLE_NOISE_RES:
        stem = pattern.sub(" ", stem)
    stem = MULTISPACE_RE.sub(" ", stem).strip()
    stem = TRAILING_PUNCT_RE.sub("", stem).strip(" .")
    return stem or Path(name).stem


def transliterate(text: str) -> str:
    out = []
    for ch in text.lower():
        if ch in _CYR_MAP:
            out.append(_CYR_MAP[ch])
        else:
            out.append(ch)
    return "".join(out)


def unique_slug(parent: Page, base: str) -> str:
    latin = transliterate(base)
    slug_base = slugify(latin)[:180] or "statya"
    slug = slug_base
    n = 2
    while Page.objects.child_of(parent).filter(slug=slug).exists():
        slug = f"{slug_base}-{n}"
        n += 1
    return slug


def find_soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    return None


def convert_to_html(source: Path, out_dir: Path, soffice: str, timeout: int = 900) -> Path:
    """Конвертирует документ в HTML LibreOffice; рядом появляются файлы картинок."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # Обычный HTML (картинки отдельными файлами) — меньше пик памяти, чем EmbedImages.
    cmd = [
        soffice,
        "--headless",
        "--norestore",
        "--convert-to",
        "html",
        "--outdir",
        str(out_dir),
        str(source),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"таймаут конвертации ({timeout}s)") from exc

    html_path = out_dir / f"{source.stem}.html"
    if not html_path.exists():
        # LibreOffice может укоротить имя
        candidates = sorted(out_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            err = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"HTML не создан: {err[:400]}")
        html_path = candidates[0]
    if proc.returncode != 0 and not html_path.exists():
        raise RuntimeError((proc.stderr or proc.stdout or "ошибка LibreOffice")[:400])
    return html_path


class _BlockCollector(HTMLParser):
    """Собирает последовательность параграфов/заголовков/картинок из HTML Writer."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events: list[tuple] = []
        self._in_body = False
        self._skip_depth = 0
        self._block_tag: str | None = None
        self._block_parts: list[str] = []
        self._block_has_img = False
        self._block_img_src: str | None = None
        self._capture_inline = False

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        tag = tag.lower()
        if tag == "body":
            self._in_body = True
            return
        if not self._in_body:
            return

        cls = attrs_d.get("class", "")
        if self._skip_depth:
            self._skip_depth += 1
            return
        if tag in {"script", "style", "head"} or "sdfootnote" in cls or tag == "div" and "footnote" in cls:
            self._skip_depth = 1
            return

        if tag in {"p", "h1", "h2", "h3", "h4", "li"} and self._block_tag is None:
            self._block_tag = tag
            self._block_parts = []
            self._block_has_img = False
            self._block_img_src = None
            self._capture_inline = True
            return

        # LibreOffice часто ставит <img> между абзацами, не внутри <p>
        if tag == "img" and not self._capture_inline:
            src = attrs_d.get("src") or ""
            if src:
                self.events.append(("image", src, ""))
            return

        if not self._capture_inline:
            return

        if tag == "img":
            src = attrs_d.get("src") or ""
            if src.startswith("data:"):
                # data-URI сохраняем как спец. метку — разберём позже
                self._block_has_img = True
                self._block_img_src = src
            elif src:
                self._block_has_img = True
                self._block_img_src = src
            return

        if tag == "br":
            self._block_parts.append("<br>")
            return

        if tag in ALLOWED_INLINE:
            if tag == "a":
                href = html_module.escape(attrs_d.get("href") or "", quote=True)
                self._block_parts.append(f'<a href="{href}">')
            else:
                self._block_parts.append(f"<{tag}>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "body":
            self._flush_block()
            self._in_body = False
            return
        if self._skip_depth:
            self._skip_depth -= 1
            return
        if not self._in_body:
            return

        if tag in {"p", "h1", "h2", "h3", "h4", "li"} and self._block_tag == tag:
            self._flush_block()
            return

        if self._capture_inline and tag in ALLOWED_INLINE and tag != "br":
            self._block_parts.append(f"</{tag}>")

    def handle_data(self, data):
        if self._skip_depth or not self._capture_inline:
            return
        if data:
            self._block_parts.append(html_module.escape(data))

    def _flush_block(self):
        if self._block_tag is None:
            return
        raw = "".join(self._block_parts)
        text = re.sub(r"<br\s*/?>", "\n", raw)
        text_plain = re.sub(r"<[^>]+>", "", text)
        text_plain = MULTISPACE_RE.sub(" ", text_plain.replace("\xa0", " ")).strip()

        if self._block_has_img and self._block_img_src:
            self.events.append(("image", self._block_img_src, text_plain))
        elif text_plain:
            if self._block_tag in {"h1", "h2", "h3", "h4"} and len(text_plain) < 120 and not text_plain[0:1].isdigit():
                # Короткие заголовки; нумерованные сноски LO часто в h1 — пропускаем как heading
                if not re.match(r"^\d+\s", text_plain):
                    self.events.append(("heading", text_plain))
                else:
                    self.events.append(("paragraph", f"<p>{raw.strip()}</p>", text_plain))
            else:
                inner = raw.strip()
                if not inner.startswith("<"):
                    inner = f"<p>{inner}</p>"
                elif not inner.startswith("<p"):
                    inner = f"<p>{inner}</p>"
                self.events.append(("paragraph", inner, text_plain))

        self._block_tag = None
        self._block_parts = []
        self._block_has_img = False
        self._block_img_src = None
        self._capture_inline = False


def _looks_like_caption(text: str) -> bool:
    """Подпись — только явные маркеры; обычный короткий абзац не глотаем."""
    if not text or len(text) > 255:
        return False
    low = text.lower().strip()
    return bool(
        re.match(
            r"^(рис\.?|рисунок|илл\.?|иллюстрация|фото|табл\.?|таблица)\b",
            low,
        )
    )


def parse_html_document(html_path: Path, title_hint: str) -> ParsedDoc:
    html = html_path.read_text(encoding="utf-8", errors="replace")
    parser = _BlockCollector()
    parser.feed(html)
    parser.close()

    media_dir = html_path.parent
    blocks: list[dict] = []
    plain_parts: list[str] = []
    pending_caption_for: int | None = None

    for ev in parser.events:
        kind = ev[0]
        if kind == "image":
            src, nearby = ev[1], ev[2]
            image_ref: Path | bytes
            if src.startswith("data:"):
                # data:[mime];base64,...
                try:
                    header, b64 = src.split(",", 1)
                    import base64

                    data = base64.b64decode(b64)
                    image_ref = data
                except Exception:
                    continue
            else:
                # src может быть URL-encoded
                from urllib.parse import unquote

                candidate = media_dir / Path(unquote(src)).name
                if not candidate.exists():
                    candidate = media_dir / unquote(src)
                if not candidate.exists():
                    continue
                image_ref = candidate

            caption = nearby if _looks_like_caption(nearby) else ""
            blocks.append(
                {
                    "type": "image",
                    "value": {"image": image_ref, "caption": caption[:255]},
                }
            )
            pending_caption_for = len(blocks) - 1
        elif kind == "heading":
            text = ev[1]
            blocks.append({"type": "heading", "value": text})
            plain_parts.append(text)
            pending_caption_for = None
        elif kind == "paragraph":
            inner, text = ev[1], ev[2]
            if (
                pending_caption_for is not None
                and blocks[pending_caption_for]["type"] == "image"
                and not blocks[pending_caption_for]["value"]["caption"]
                and _looks_like_caption(text)
            ):
                blocks[pending_caption_for]["value"]["caption"] = text[:255]
                pending_caption_for = None
                continue
            pending_caption_for = None
            blocks.append({"type": "paragraph", "value": inner})
            plain_parts.append(text)

    plain = "\n".join(plain_parts).strip()
    intro = plain[:300].rsplit(" ", 1)[0] if len(plain) > 300 else plain
    intro = intro.strip()[:500]
    return ParsedDoc(title=title_hint, intro=intro, blocks=blocks, plain_text=plain)


def store_wagtail_image(title: str, data: bytes, filename: str, owner) -> WagtailImage | None:
    if not data:
        return None
    # Отсекаем мусор и слишком огромные файлы (>25 МБ на картинку)
    if len(data) > 25 * 1024 * 1024:
        return None
    try:
        from PIL import Image as PILImage
        from io import BytesIO

        img = PILImage.open(BytesIO(data))
        img.verify()
    except Exception:
        return None

    return WagtailImage.objects.create(
        title=title[:255],
        file=ContentFile(data, name=filename),
        uploaded_by_user=owner,
    )


def materialize_blocks(parsed: ParsedDoc, article_title: str, owner) -> list:
    """Заменяет Path/bytes картинок на id Wagtail Image."""
    result = []
    img_n = 0
    for block in parsed.blocks:
        if block["type"] != "image":
            result.append(block)
            continue
        ref = block["value"]["image"]
        caption = block["value"].get("caption") or ""
        img_n += 1
        if isinstance(ref, Path):
            data = ref.read_bytes()
            filename = ref.name
        elif isinstance(ref, (bytes, bytearray)):
            data = bytes(ref)
            filename = f"import-{img_n}.jpg"
        else:
            continue
        wag_img = store_wagtail_image(
            title=f"{article_title} — ил. {img_n}",
            data=data,
            filename=filename,
            owner=owner,
        )
        if wag_img is None:
            continue
        result.append(
            {
                "type": "image",
                "value": {"image": wag_img.pk, "caption": caption[:255]},
            }
        )
    return result


class Command(BaseCommand):
    help = (
        "Импорт статей отца из .doc/.docx/.odt (через LibreOffice→HTML) "
        "или уже сконвертированного каталога .html"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "source_dir",
            type=str,
            help="Каталог с исходниками или с .html + картинками",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только разобрать и вывести план, без записи в БД",
        )
        parser.add_argument(
            "--html-only",
            action="store_true",
            help="Брать только .html из каталога (без вызова LibreOffice)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Обработать не больше N файлов (0 = все)",
        )

    def handle(self, *args, **options):
        source_dir = Path(options["source_dir"]).expanduser().resolve()
        if not source_dir.is_dir():
            raise CommandError(f"Каталог не найден: {source_dir}")

        dry_run = options["dry_run"]
        html_only = options["html_only"]
        limit = options["limit"]

        parent = ArticleIndexPage.objects.live().first()
        if parent is None and not dry_run:
            raise CommandError("ArticleIndexPage не найден — сначала load_demo / ensure структура сайта")

        User = get_user_model()
        owner = User.objects.filter(is_superuser=True).order_by("pk").first()

        soffice = None if html_only else find_soffice()
        html_files = sorted(
            [
                p
                for p in source_dir.rglob("*")
                if p.is_file() and p.suffix.lower() in HTML_SUFFIXES
            ],
            key=lambda p: p.as_posix().lower(),
        )
        source_files = sorted(
            [
                p
                for p in source_dir.iterdir()
                if p.is_file() and p.suffix.lower() in {s.lower() for s in SOURCE_SUFFIXES}
            ],
            key=lambda p: p.name.lower(),
        )

        work_items: list[tuple[str, Path | None, Path | None]] = []
        # (label, source_path|None, html_path|None)
        if html_only or (html_files and not source_files):
            for hp in html_files:
                work_items.append((str(hp.relative_to(source_dir)), None, hp))
        else:
            for sp in source_files:
                work_items.append((sp.name, sp, None))

        if not work_items:
            raise CommandError(f"В {source_dir} нет подходящих файлов")

        imported: list[str] = []
        skipped: list[str] = []

        processed = 0
        for label, source_path, html_path in work_items:
            if limit and processed >= limit:
                break
            processed += 1

            if source_path is not None:
                if source_path.name.lower() in SKIP_FILENAMES:
                    skipped.append(f"{label}: пропуск по списку (не статья / дубликат)")
                    self.stdout.write(self.style.WARNING(f"SKIP {label}: список исключений"))
                    continue
                if source_path.stat().st_size < 5000 and "сети" in source_path.name.lower():
                    skipped.append(f"{label}: слишком маленький / список ссылок")
                    continue

            title = title_from_filename(source_path.name if source_path else html_path.name)

            if parent is not None and ArticlePage.objects.child_of(parent).filter(title=title).exists():
                skipped.append(f"{label}: уже есть статья «{title}»")
                self.stdout.write(self.style.WARNING(f"SKIP {label}: дубликат title «{title}»"))
                continue

            tmp_dir = None
            try:
                if html_path is None:
                    if soffice is None:
                        skipped.append(f"{label}: нет LibreOffice (soffice) для конвертации")
                        self.stdout.write(self.style.WARNING(f"SKIP {label}: нет soffice"))
                        continue
                    tmp_dir = Path(tempfile.mkdtemp(prefix="papa-import-"))
                    self.stdout.write(f"CONVERT {label} …")
                    html_path = convert_to_html(source_path, tmp_dir, soffice)
                else:
                    self.stdout.write(f"PARSE {label} …")

                parsed = parse_html_document(html_path, title)
                if not parsed.plain_text.strip() and not any(b["type"] == "image" for b in parsed.blocks):
                    skipped.append(f"{label}: пустой документ после разбора")
                    self.stdout.write(self.style.WARNING(f"SKIP {label}: пусто"))
                    continue

                n_img = sum(1 for b in parsed.blocks if b["type"] == "image")
                n_p = sum(1 for b in parsed.blocks if b["type"] == "paragraph")
                self.stdout.write(
                    f"  title={parsed.title!r} paragraphs={n_p} images={n_img} intro={parsed.intro[:60]!r}…"
                )

                if dry_run:
                    imported.append(f"{label} → «{parsed.title}» (dry-run)")
                    continue

                with transaction.atomic():
                    body = materialize_blocks(parsed, parsed.title, owner)
                    page = ArticlePage(
                        title=parsed.title,
                        slug=unique_slug(parent, parsed.title),
                        intro=parsed.intro,
                        body=body,
                        owner=owner,
                    )
                    parent.add_child(instance=page)
                    revision = page.save_revision(user=owner, log_action=True)
                    revision.publish(user=owner)
                    url = page.url or f"/articles/{page.slug}/"
                    imported.append(f"{label} → {url} («{parsed.title}», img={n_img})")
                    self.stdout.write(self.style.SUCCESS(f"OK {label} → {url}"))

            except MemoryError:
                skipped.append(f"{label}: нехватка памяти (OOM)")
                self.stdout.write(self.style.ERROR(f"SKIP {label}: OOM"))
            except Exception as exc:  # noqa: BLE001 — импорт должен переживать битые файлы
                skipped.append(f"{label}: {exc}")
                self.stdout.write(self.style.ERROR(f"SKIP {label}: {exc}"))
            finally:
                if tmp_dir and tmp_dir.exists():
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                gc.collect()

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("=== ИТОГ ==="))
        self.stdout.write(f"Импортировано: {len(imported)}")
        for line in imported:
            self.stdout.write(f"  + {line}")
        self.stdout.write(f"Пропущено: {len(skipped)}")
        for line in skipped:
            self.stdout.write(f"  - {line}")
