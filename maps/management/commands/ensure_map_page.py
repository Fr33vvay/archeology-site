"""Создаёт страницу «Карта» под Home, если её ещё нет."""

from django.core.management.base import BaseCommand
from wagtail.models import Site

from home.models import HomePage
from maps.models import MapPage


class Command(BaseCommand):
    help = "Создаёт MapPage (slug=map) в меню, если отсутствует"

    def handle(self, *args, **options):
        home = HomePage.objects.live().first()
        if not home:
            site = Site.objects.filter(is_default_site=True).first()
            home = site.root_page.specific if site and site.root_page else None
        if not home or not isinstance(home, HomePage):
            self.stdout.write(self.style.WARNING("HomePage не найдена — пропуск."))
            return

        existing = MapPage.objects.child_of(home).first()
        if existing:
            if not existing.show_in_menus or not existing.live:
                existing.show_in_menus = True
                revision = existing.save_revision()
                revision.publish()
            self.stdout.write(self.style.SUCCESS(f"MapPage уже есть: /{existing.slug}/"))
            return

        page = MapPage(
            title="Карта",
            slug="map",
            intro="<p>Объекты на карте Санкт-Петербурга.</p>",
            show_in_menus=True,
        )
        home.add_child(instance=page)
        page.save_revision().publish()
        self.stdout.write(self.style.SUCCESS("Создана страница Карта: /map/"))
