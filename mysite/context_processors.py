from wagtail.models import Site


def site_navigation(request):
    """Пункты меню из дерева страниц текущего сайта."""
    site = Site.find_for_request(request)
    if not site:
        return {"nav_pages": [], "site_root": None}

    root = site.root_page
    nav_pages = root.get_children().live().public().specific().in_menu()
    return {
        "nav_pages": nav_pages,
        "site_root": root,
    }
