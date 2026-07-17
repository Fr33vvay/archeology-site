"""Создаёт или обновляет страницу «Об авторе» с портретом из fixtures."""

from pathlib import Path

from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand
from django.db import transaction
from wagtail.images.models import Image

from home.models import AuthorPage, HomePage

AUTHOR_BODY = """
<p><strong>Виктор Авраамович Коренцвит</strong></p>
<p>Виктор Авраамович Коренцвит (род. 19 июля 1945) — петербургский археолог, историк архитектуры и исследователь истории Санкт-Петербурга. Его называют одним из ведущих специалистов по археологии города и пригородов; много лет он связан с Институтом Петербурга.</p>
<p>Главная тема его работы — ранний Петербург и его дворцово-парковые ансамбли. Коренцвит одним из первых вёл археологические исследования на территории Летнего сада и подготовил историческую основу для комплексной реставрации ансамбля; в профессиональной среде его нередко называют «идеологом» этого проекта. Результаты многолетних раскопок и архивных изысканий он обобщил в книге «Летний сад Петра Великого. Рассказ о прошлом и настоящем» — с сотнями иллюстраций и подробным разбором мифов, которые десятилетиями кочевали из публикации в публикацию.</p>
<p>Помимо Летнего сада, в сферу его интересов входят Ораниенбаум, Петергоф, Царское Село, а также спорные и малоизученные сюжеты истории архитектуры — например, наследие Франческо Фонтана. Среди его работ — исследование дома Ю. М. Фельтена на Мойке: по результатам раскопок и обследования фасада он реконструировал облик здания. Автор более ста статей по истории Петербурга.</p>
<p>Коренцвит активно выступает как просветитель: читает лекции о археологии и реставрации, обсуждает ошибки восстановления памятников — не как обвинитель, а, по собственному определению, как «доброжелательный турист», для которого важно, чтобы городское наследие сохранялось честно и внимательно.</p>
"""

PORTRAIT_TITLE = "Виктор Авраамович Коренцвит"
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "author-portrait.jpg"


class Command(BaseCommand):
    help = "Создать или обновить страницу «Об авторе»"

    @transaction.atomic
    def handle(self, *args, **options):
        home = HomePage.objects.live().first()
        if not home:
            self.stderr.write("Нет главной страницы. Сначала создайте HomePage.")
            return

        if not FIXTURE.is_file():
            self.stderr.write(f"Нет файла портрета: {FIXTURE}")
            return

        portrait = Image.objects.filter(title=PORTRAIT_TITLE).first()
        if not portrait:
            with FIXTURE.open("rb") as f:
                portrait = Image(
                    title=PORTRAIT_TITLE,
                    file=ImageFile(f, name="author-portrait.jpg"),
                )
                portrait.save()
            self.stdout.write("Загружен портрет в медиатеку.")
        else:
            # Обновляем файл, если страница уже была без актуального фото
            with FIXTURE.open("rb") as f:
                portrait.file.save("author-portrait.jpg", ImageFile(f), save=True)
            self.stdout.write("Портрет обновлён.")

        page = AuthorPage.objects.child_of(home).first()
        if not page:
            page = AuthorPage(
                title="Об авторе",
                slug="author",
                body=AUTHOR_BODY.strip(),
                portrait=portrait,
                show_in_menus=True,
            )
            home.add_child(instance=page)
            page.save_revision().publish()
            self.stdout.write(self.style.SUCCESS("Страница «Об авторе» создана."))
        else:
            page.title = "Об авторе"
            page.body = AUTHOR_BODY.strip()
            page.portrait = portrait
            page.show_in_menus = True
            page.save_revision().publish()
            self.stdout.write(self.style.SUCCESS("Страница «Об авторе» обновлена."))
