"""Выставляет django.contrib.sites.Site на коренцвит.рф (не example.com)."""

from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand

SITE_DOMAIN = "коренцвит.рф"
SITE_NAME = "коренцвит.рф"


class Command(BaseCommand):
    help = "Обновляет Site(id=SITE_ID): domain и name = коренцвит.рф"

    def handle(self, *args, **options):
        site, created = Site.objects.update_or_create(
            id=1,
            defaults={"domain": SITE_DOMAIN, "name": SITE_NAME},
        )
        action = "создан" if created else "обновлён"
        self.stdout.write(
            self.style.SUCCESS(
                f"Site {action}: id={site.id} domain={site.domain!r} name={site.name!r}"
            )
        )
