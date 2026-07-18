"""Агрегация и текст еженедельного отчёта (Europe/Moscow)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.utils import timezone

from articles.models import ArticleUniqueView, Comment
from blog.models import BlogComment, BlogPostUniqueView

MSK = ZoneInfo("Europe/Moscow")
User = get_user_model()


def previous_week_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Прошлая календарная неделя пн 00:00 — пн 00:00 (конец не включая) в MSK."""
    if now is None:
        now = timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, MSK)
    local = now.astimezone(MSK)
    # weekday: Mon=0 … Sun=6
    this_monday = local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=local.weekday()
    )
    start = this_monday - timedelta(days=7)
    end = this_monday
    return start, end


@dataclass
class WeeklyStats:
    start: datetime
    end: datetime
    article_views: int
    blog_views: int
    comments: int
    registrations: int
    new_users: list[tuple[str, str]]  # (first_name, last_name)

    @property
    def has_activity(self) -> bool:
        return bool(
            self.article_views
            or self.blog_views
            or self.comments
            or self.registrations
        )


def collect_stats(now: datetime | None = None) -> WeeklyStats:
    start, end = previous_week_bounds(now)
    article_views = ArticleUniqueView.objects.filter(
        created_at__gte=start, created_at__lt=end
    ).count()
    blog_views = BlogPostUniqueView.objects.filter(
        created_at__gte=start, created_at__lt=end
    ).count()
    article_comments = Comment.objects.filter(
        created_at__gte=start,
        created_at__lt=end,
        is_deleted=False,
    ).count()
    blog_comments = BlogComment.objects.filter(
        created_at__gte=start,
        created_at__lt=end,
        is_deleted=False,
    ).count()
    users = list(
        User.objects.filter(date_joined__gte=start, date_joined__lt=end)
        .order_by("date_joined")
        .values_list("first_name", "last_name")
    )
    return WeeklyStats(
        start=start,
        end=end,
        article_views=article_views,
        blog_views=blog_views,
        comments=article_comments + blog_comments,
        registrations=len(users),
        new_users=users,
    )


def format_report(stats: WeeklyStats) -> str:
    start_d = stats.start.astimezone(MSK).strftime("%d.%m.%Y")
    # Конец периода — воскресенье (день перед end)
    last_day = (stats.end - timedelta(seconds=1)).astimezone(MSK).strftime("%d.%m.%Y")
    lines = [
        f"Еженедельный отчёт коренцвит.рф",
        f"Период: {start_d} — {last_day} (Europe/Moscow)",
        "",
        f"Просмотры статей: {stats.article_views}",
        f"Просмотры постов блога: {stats.blog_views}",
        f"Новые комментарии: {stats.comments}",
        f"Регистрации: {stats.registrations}",
        "",
        "Новые пользователи:",
    ]
    if stats.new_users:
        for first, last in stats.new_users:
            name = f"{(first or '').strip()} {(last or '').strip()}".strip() or "—"
            lines.append(f"- {name}")
    else:
        lines.append("- (нет)")
    return "\n".join(lines) + "\n"
