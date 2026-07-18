from wagtail.models import Site

# Порядок пунктов меню после «Главная» (по slug страницы).
NAV_SLUG_ORDER = (
    "articles",
    "blog",
    "gallery",
    "contacts",
    "author",
)

DEFAULT_HEADER_TITLE = "Научный архив"
DEFAULT_FOOTER_TEXT = "Научные материалы и иллюстрации. Сайт-архив."


def site_navigation(request):
    """Пункты меню и тексты шапки/подвала."""
    site = Site.find_for_request(request)
    if not site:
        return {
            "nav_pages": [],
            "site_root": None,
            "site_header_title": DEFAULT_HEADER_TITLE,
            "site_footer_text": DEFAULT_FOOTER_TEXT,
        }

    root = site.root_page
    pages = list(root.get_children().live().public().specific().in_menu())
    order = {slug: index for index, slug in enumerate(NAV_SLUG_ORDER)}
    pages.sort(key=lambda page: (order.get(page.slug, 100), page.path))

    header_title = DEFAULT_HEADER_TITLE
    footer_text = DEFAULT_FOOTER_TEXT
    try:
        from django.db.utils import OperationalError, ProgrammingError

        from home.models import SiteBranding

        branding = SiteBranding.for_request(request)
        if branding:
            header_title = branding.header_title or DEFAULT_HEADER_TITLE
            footer_text = branding.footer_text or DEFAULT_FOOTER_TEXT
    except (OperationalError, ProgrammingError):
        pass

    return {
        "nav_pages": pages,
        "site_root": root,
        "site_header_title": header_title,
        "site_footer_text": footer_text,
    }
