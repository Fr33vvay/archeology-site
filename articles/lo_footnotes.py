"""Конвертация сносок/концевых примечаний LibreOffice → формат сайта (#fn- / #fnref-)."""

from __future__ import annotations

import html as html_module
import re
from html.parser import HTMLParser

# Тела сносок в HTML Writer: <div id="sdfootnote1">…</div> / sdendnote
_BODY_DIV_RE = re.compile(
    r'<div\b[^>]*\bid\s*=\s*["\']sd(?:end|foot)note(\d+)["\'][^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)

# Ссылка в тексте: class/name/href с sdfootnoteNanc / sdendnoteNsym
_REF_A_RE = re.compile(
    r'<a\b[^>]*\b(?:'
    r'class\s*=\s*["\'][^"\']*sd(?:end|foot)noteanc[^"\']*["\']|'
    r'(?:name|id)\s*=\s*["\']sd(?:end|foot)note\d+anc["\']|'
    r'href\s*=\s*["\']#sd(?:end|foot)note\d+sym["\']'
    r')[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)

_NUM_IN_REF_RE = re.compile(r"sd(?:end|foot)note(\d+)", re.IGNORECASE)
_SYM_LINK_RE = re.compile(
    r'<a\b[^>]*\b(?:'
    r'class\s*=\s*["\'][^"\']*sd(?:end|foot)notesym[^"\']*["\']|'
    r'(?:name|id)\s*=\s*["\']sd(?:end|foot)note\d+sym["\']|'
    r'href\s*=\s*["\']#sd(?:end|foot)note\d+anc["\']'
    r')[^>]*>.*?</a>',
    re.IGNORECASE | re.DOTALL,
)

# Лишняя обёртка <sup> вокруг уже готовой ссылки сноски
_NESTED_SUP_REF_RE = re.compile(
    r"<sup>\s*(<a\b[^>]*href\s*=\s*[\"']#fn-\d+[\"'][^>]*>.*?</a>)\s*</sup>",
    re.IGNORECASE | re.DOTALL,
)

_EMPTY_A_RE = re.compile(r'<a\b[^>]*href\s*=\s*["\']["\'][^>]*>\s*</a>', re.IGNORECASE)

_ALLOWED_INLINE = {"b", "strong", "i", "em", "u", "sup", "sub", "br"}


class _InlineCleaner(HTMLParser):
    """Оставляет только безопасную инлайн-разметку и текст."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "br":
            self.parts.append("<br>")
        elif tag in _ALLOWED_INLINE:
            self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _ALLOWED_INLINE and tag != "br":
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if data:
            self.parts.append(html_module.escape(data))


def _clean_inline_html(fragment: str) -> str:
    parser = _InlineCleaner()
    parser.feed(f"<div>{fragment}</div>")
    parser.close()
    text = "".join(parser.parts)
    text = re.sub(r"[\t\r\f]+", " ", text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _extract_bodies(html: str) -> tuple[str, dict[int, str]]:
    bodies: dict[int, str] = {}

    def repl(match: re.Match[str]) -> str:
        n = int(match.group(1))
        raw = match.group(2)
        raw = _SYM_LINK_RE.sub("", raw, count=1)
        text = _clean_inline_html(raw)
        if text:
            # Несколько <p> внутри одного div склеиваем
            if n in bodies and bodies[n]:
                bodies[n] = f"{bodies[n]} {text}"
            else:
                bodies[n] = text
        return ""

    cleaned = _BODY_DIV_RE.sub(repl, html)
    return cleaned, bodies


def _replace_refs(html: str) -> str:
    def repl(match: re.Match[str]) -> str:
        whole = match.group(0)
        num_m = _NUM_IN_REF_RE.search(whole)
        if not num_m:
            return whole
        n = num_m.group(1)
        inner = match.group(1)
        label_m = re.search(r"<sup>\s*(.*?)\s*</sup>", inner, flags=re.IGNORECASE | re.DOTALL)
        if label_m:
            label = re.sub(r"<[^>]+>", "", label_m.group(1)).strip()
        else:
            label = re.sub(r"<[^>]+>", "", inner).strip()
        if not label:
            label = n
        return f'<a href="#fn-{n}"><sup>{html_module.escape(label)}</sup></a>'

    return _REF_A_RE.sub(repl, html)


def build_footnotes_block(bodies: dict[int, str]) -> str:
    """HTML блока списка сносок в формате сайта."""
    if not bodies:
        return ""
    items = []
    for n in sorted(bodies):
        items.append(f'<li>{bodies[n]} <a href="#fnref-{n}">↩</a></li>')
    return "<p></p><ol>" + "".join(items) + "</ol>"


def convert_lo_footnotes(html: str) -> tuple[str, str]:
    """
    Преобразует сноски LibreOffice в якоря #fn- / #fnref-.

    Returns:
        (html_без_тел_сносок_с_заменой_ссылок, html_блока_ol_или_пустая_строка)
    """
    if not html:
        return html, ""
    if "sdfootnote" not in html.lower() and "sdendnote" not in html.lower():
        return html, ""

    html, bodies = _extract_bodies(html)
    html = _replace_refs(html)
    html = _NESTED_SUP_REF_RE.sub(r"\1", html)
    html = _EMPTY_A_RE.sub("", html)
    return html, build_footnotes_block(bodies)


def convert_lo_footnotes_in_richtext(html: str) -> str:
    """
    Конвертирует уже импортированный rich text со ссылками sdendnote/sdfootnote.

    Тела сносок, лежащие отдельными абзацами вида
    ``<a href="#sdendnote1anc">1</a> текст``, собираются в один ``<ol>``.
    """
    if not html:
        return html
    low = html.lower()
    if "sdfootnote" not in low and "sdendnote" not in low:
        return html

    bodies: dict[int, str] = {}

    # Абзац-тело: <p>…<a href="#sdendnoteNanc">N</a> текст…</p>
    body_para_re = re.compile(
        r"<p\b[^>]*>\s*"
        r'(?:<a\b[^>]*href\s*=\s*["\']#sd(?:end|foot)note(\d+)anc["\'][^>]*>.*?</a>\s*)'
        r"(.*?)</p>",
        re.IGNORECASE | re.DOTALL,
    )

    def take_body(match: re.Match[str]) -> str:
        n = int(match.group(1))
        text = _clean_inline_html(match.group(2))
        if text:
            if n in bodies and bodies[n]:
                bodies[n] = f"{bodies[n]} {text}"
            else:
                bodies[n] = text
        return ""

    html = body_para_re.sub(take_body, html)
    html = _replace_refs(html)
    html = _NESTED_SUP_REF_RE.sub(r"\1", html)
    html = _EMPTY_A_RE.sub("", html)
    # На случай тел без обёртки <p>
    html = _SYM_LINK_RE.sub("", html)

    footnotes = build_footnotes_block(bodies)
    if footnotes:
        html = html.rstrip() + footnotes
    return html
