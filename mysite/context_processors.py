from wagtail.models import Site

# Порядок пунктов меню после «Главная» (по slug страницы).
NAV_SLUG_ORDER = (
    "articles",
    "blog",
    "gallery",
    "contacts",
    "author",
)


def site_navigation(request):
    """Пункты меню из дерева страниц текущего сайта."""
    site = Site.find_for_request(request)
    if not site:
        return {"nav_pages": [], "site_root": None}

    root = site.root_page
    pages = list(root.get_children().live().public().specific().in_menu())
    order = {slug: index for index, slug in enumerate(NAV_SLUG_ORDER)}
    pages.sort(key=lambda page: order.get(page.slug, 100 + page.path))
    return {
        "nav_pages": pages,
        "site_root": root,
    }
