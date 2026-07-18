"""Фильтры для шаблонов блога."""

from django import template

from mysite.unique_views import ru_views_word

register = template.Library()


@register.filter(name="ru_views")
def ru_views(count):
    """Склонение: 1 просмотр, 2 просмотра, 5 просмотров."""
    return ru_views_word(count or 0)
