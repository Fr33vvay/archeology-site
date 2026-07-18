"""Фильтры для шаблонов статей."""

from __future__ import annotations

import re

from django import template
from django.utils.safestring import mark_safe

from mysite.unique_views import ru_views_word

register = template.Library()


@register.filter(name="ru_views")
def ru_views(count):
    """Склонение: 1 просмотр, 2 просмотра, 5 просмотров."""
    return ru_views_word(count or 0)


def apply_footnote_anchors(html: str) -> str:
    """Проставляет id для ссылок сносок и возврата в текст."""
    if not html:
        return html

    html = str(html)

    html = re.sub(
        r'<a href="#fn-(\d+)">',
        r'<a id="fnref-\1" class="footnote-ref" href="#fn-\1">',
        html,
    )
    html = re.sub(
        r'<a href="#fnref-(\d+)">',
        r'<a class="footnote-back" href="#fnref-\1">',
        html,
    )

    def fix_li(match: re.Match[str]) -> str:
        attrs, content = match.group(1), match.group(2)
        back = re.search(r'href="#fnref-(\d+)"', content)
        if not back:
            return match.group(0)
        if re.search(r'\bid\s*=', attrs):
            return match.group(0)
        n = back.group(1)
        return f'<li id="fn-{n}"{attrs}>{content}</li>'

    html = re.sub(r"<li([^>]*)>(.*?)</li>", fix_li, html, flags=re.DOTALL)

    def wrap_ol(match: re.Match[str]) -> str:
        ol = match.group(0)
        if 'id="fn-' in ol and "class=\"footnotes\"" not in ol and "footnotes" not in ol[:80]:
            return f'<div class="footnotes">{ol}</div>'
        return ol

    html = re.sub(r"<ol\b[^>]*>.*?</ol>", wrap_ol, html, flags=re.DOTALL)
    return html


@register.filter(name="footnote_anchors")
def footnote_anchors(html):
    """Django-фильтр: разметка научных сносок с рабочими якорями."""
    return mark_safe(apply_footnote_anchors(html))
