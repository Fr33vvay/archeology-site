"""Тесты карты объектов: точки, страница карты, права, ссылки в статьях."""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from wagtail.models import Page, Site

from articles.models import ArticleIndexPage, ArticlePage
from home.models import HomePage
from maps.models import MapPage, MapPoint

User = get_user_model()


class MapTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        home = HomePage(title="Главная", slug="home-map")
        root.add_child(instance=home)
        home.save_revision().publish()
        Site.objects.update_or_create(
            is_default_site=True,
            defaults={"hostname": "localhost", "root_page": home, "site_name": "Test"},
        )
        index = ArticleIndexPage(title="Статьи", slug="articles-map", show_in_menus=True)
        home.add_child(instance=index)
        index.save_revision().publish()
        article = ArticlePage(
            title="Статья с картой",
            slug="article-map",
            intro="intro",
            body=[{"type": "paragraph", "value": "<p>Текст статьи</p>"}],
        )
        index.add_child(instance=article)
        article.save_revision().publish()
        map_page = MapPage(
            title="Карта",
            slug="map",
            intro="<p>Карта объектов</p>",
            show_in_menus=True,
        )
        home.add_child(instance=map_page)
        map_page.save_revision().publish()
        cls.home = HomePage.objects.get(pk=home.pk)
        cls.index = ArticleIndexPage.objects.get(pk=index.pk)
        cls.article = ArticlePage.objects.get(pk=article.pk)
        cls.map_page = MapPage.objects.get(pk=map_page.pk)
        cls.superuser = User.objects.create_superuser(
            username="map-admin", email="map-admin@yandex.ru", password="pass-12345"
        )
        cls.reader = User.objects.create_user(
            username="map-reader", email="map-reader@yandex.ru", password="pass-12345"
        )


class MapPointCreateTests(MapTestBase):
    def test_superuser_can_create_map_point(self):
        """Суперпользователь создаёт точку на карте через API."""
        self.client.login(username="map-admin", password="pass-12345")
        response = self.client.post(
            "/maps/points/",
            data=json.dumps(
                {
                    "article_id": self.article.pk,
                    "lat": "59.9500",
                    "lon": "30.3167",
                    "title": "Петропавловская крепость",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(MapPoint.objects.count(), 1)
        point = MapPoint.objects.get()
        self.assertEqual(point.article_id, self.article.pk)
        self.assertEqual(point.title, "Петропавловская крепость")
        self.assertEqual(point.lat, Decimal("59.9500"))
        self.assertEqual(point.lon, Decimal("30.3167"))
        self.assertTrue(point.anchor_id)
        self.assertEqual(data["id"], point.pk)
        self.assertIn("point=", data["map_url"])
        self.assertIn(point.anchor_id, data["anchor_id"])

    def test_regular_user_cannot_create_map_point(self):
        """Обычный пользователь не может создавать точки на карте."""
        self.client.login(username="map-reader", password="pass-12345")
        response = self.client.post(
            "/maps/points/",
            data=json.dumps(
                {
                    "article_id": self.article.pk,
                    "lat": "59.95",
                    "lon": "30.31",
                    "title": "Точка",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(MapPoint.objects.count(), 0)


class MapPageViewTests(MapTestBase):
    def test_map_page_returns_200_with_points(self):
        """Страница карты отдаёт 200 и список точек в контексте."""
        point = MapPoint.objects.create(
            article=self.article,
            lat=Decimal("59.9400"),
            lon=Decimal("30.3200"),
            title="Эрмитаж",
            anchor_id="map-point-hermitage",
        )
        response = self.client.get(self.map_page.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(point, response.context["map_points"])
        html = response.content.decode()
        self.assertIn("Эрмитаж", html)
        self.assertIn(str(point.pk), html)

    def test_map_page_focuses_point_from_query(self):
        """Query ?point=<id> передаёт id точки для фокуса карты."""
        point = MapPoint.objects.create(
            article=self.article,
            lat=Decimal("59.93"),
            lon=Decimal("30.30"),
            title="Фокус",
            anchor_id="map-point-focus",
        )
        response = self.client.get(f"{self.map_page.url}?point={point.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["focus_point_id"], point.pk)

    def test_map_marker_links_to_article_anchor(self):
        """У точки на карте есть ссылка на статью с якорем."""
        point = MapPoint.objects.create(
            article=self.article,
            lat=Decimal("59.94"),
            lon=Decimal("30.31"),
            title="Якорь",
            anchor_id="map-point-anchor-test",
        )
        response = self.client.get(self.map_page.url)
        self.assertEqual(response.status_code, 200)
        points_json = response.context["map_points_json"]
        found = next(p for p in points_json if p["id"] == point.pk)
        self.assertIn(f"#{point.anchor_id}", found["article_url"])
        self.assertTrue(found["article_url"].startswith(self.article.url.rstrip("/")) or self.article.url in found["article_url"] or found["article_url"].endswith(f"#{point.anchor_id}"))

    @override_settings(YANDEX_MAPS_API_KEY="")
    def test_map_page_without_api_key_returns_200(self):
        """Без ключа Яндекс.Карт страница карты отдаёт 200 и понятное сообщение."""
        response = self.client.get(self.map_page.url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("временно недоступна", html.lower())


class MapArticleLinkTests(MapTestBase):
    def test_article_shows_map_link(self):
        """Статья показывает ссылку на карту с фокусом на точку."""
        point = MapPoint.objects.create(
            article=self.article,
            lat=Decimal("59.95"),
            lon=Decimal("30.32"),
            title="Крепость",
            anchor_id="map-point-krepost",
        )
        body_html = (
            f'<p>Текст. '
            f'<a class="map-point-link" href="/map/?point={point.pk}">На карте: Крепость</a></p>'
        )
        self.article.body = [{"type": "paragraph", "value": body_html}]
        self.article.save_revision().publish()
        response = self.client.get(self.article.url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(f"point={point.pk}", html)
        self.assertIn("map-point-link", html)
        self.assertIn(f'id="{point.anchor_id}"', html)

    def test_save_article_removes_orphan_map_points(self):
        """При сохранении статьи удаляются точки, ссылок на которые нет в тексте."""
        keep = MapPoint.objects.create(
            article=self.article,
            lat=Decimal("59.95"),
            lon=Decimal("30.32"),
            title="Оставить",
            anchor_id="map-point-keep",
        )
        orphan = MapPoint.objects.create(
            article=self.article,
            lat=Decimal("59.90"),
            lon=Decimal("30.20"),
            title="Удалить",
            anchor_id="map-point-orphan",
        )
        self.client.login(username="map-admin", password="pass-12345")
        body = (
            f'<p><a class="map-point-link" href="/map/?point={keep.pk}">На карте</a></p>'
        )
        response = self.client.post(
            f"/articles/{self.article.pk}/edit/",
            {
                "title": self.article.title,
                "intro": "intro",
                "blocks_json": json.dumps([{"type": "paragraph", "value": body}]),
                "action": "draft",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MapPoint.objects.filter(pk=keep.pk).exists())
        self.assertFalse(MapPoint.objects.filter(pk=orphan.pk).exists())

    def test_editor_exposes_map_point_ui_for_superuser(self):
        """В редакторе суперпользователя есть UI для точки на карте."""
        self.client.login(username="map-admin", password="pass-12345")
        response = self.client.get(f"/articles/{self.article.pk}/edit/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Точка на карте", html)
        self.assertIn("data-map-point-url", html)


class MapNavTests(MapTestBase):
    def test_map_in_navigation(self):
        """Пункт «Карта» присутствует в меню сайта."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(self.map_page.url, html)
        self.assertIn("Карта", html)
