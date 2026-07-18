from dataclasses import dataclass

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.template.response import TemplateResponse
from django.utils.text import Truncator
from wagtail.models import Page

from articles.models import ArticlePage
from blog.models import BlogIndexPage, BlogPost


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    kind: str  # page | article | blog


def _contains(text: str, query: str) -> bool:
    """Проверка вхождения без учёта регистра (в т.ч. кириллица)."""
    return query.casefold() in (text or "").casefold()


def _snippet(text: str, query: str, limit: int = 160) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    lowered = text.casefold()
    q = query.casefold()
    pos = lowered.find(q)
    if pos < 0:
        return Truncator(text).chars(limit, truncate="…")
    start = max(0, pos - 40)
    chunk = text[start : start + limit]
    if start > 0:
        chunk = "…" + chunk
    if start + limit < len(text):
        chunk = chunk + "…"
    return chunk


def run_search(query: str) -> list[SearchHit]:
    """Поиск по вхождению (без учёта регистра) по страницам, статьям и постам блога."""
    q = (query or "").strip()
    if not q:
        return []

    hits: list[SearchHit] = []
    seen_page_ids: set[int] = set()

    for article in ArticlePage.objects.live().public().specific():
        body_text = str(article.body) if article.body else ""
        if not (
            _contains(article.title, q)
            or _contains(article.intro, q)
            or _contains(body_text, q)
        ):
            continue
        seen_page_ids.add(article.pk)
        snippet_src = article.intro or ""
        if not _contains(snippet_src, q):
            snippet_src = body_text or article.title
        hits.append(
            SearchHit(
                title=article.title,
                url=article.url,
                snippet=_snippet(snippet_src, q),
                kind="article",
            )
        )

    for page in Page.objects.live().public().exclude(pk__in=seen_page_ids).specific():
        if isinstance(page, ArticlePage):
            continue
        if not _contains(page.title, q):
            continue
        hits.append(
            SearchHit(
                title=page.title,
                url=page.url,
                snippet=getattr(page, "search_description", "") or "",
                kind="page",
            )
        )

    blog_index = BlogIndexPage.objects.live().public().first()
    blog_url = blog_index.url if blog_index else "/blog/"
    for post in BlogPost.objects.filter(is_deleted=False).order_by("-created_at"):
        if not _contains(post.body, q):
            continue
        hits.append(
            SearchHit(
                title=Truncator(post.body).words(8, truncate="…") or f"Пост #{post.pk}",
                url=f"{blog_url}#post-{post.pk}",
                snippet=_snippet(post.body, q),
                kind="blog",
            )
        )

    return hits


def search(request):
    search_query = request.GET.get("query", None)
    page = request.GET.get("page", 1)

    if search_query:
        search_results = run_search(search_query)
    else:
        search_results = []

    paginator = Paginator(search_results, 10)
    try:
        search_results = paginator.page(page)
    except PageNotAnInteger:
        search_results = paginator.page(1)
    except EmptyPage:
        search_results = paginator.page(paginator.num_pages)

    return TemplateResponse(
        request,
        "search/search.html",
        {
            "search_query": search_query,
            "search_results": search_results,
        },
    )
