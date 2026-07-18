"""Тесты поиска: статьи, блог, поиск по вхождению."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from wagtail.models import Page, Site

from articles.models import ArticleIndexPage, ArticlePage
from blog.models import BlogIndexPage, BlogPost
from home.models import HomePage

User = get_user_model()


class SearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        home = HomePage.objects.first()
        if not home:
            home = HomePage(title="Главная", slug="home-search")
            root.add_child(instance=home)
            home.save_revision().publish()
        Site.objects.update_or_create(
            is_default_site=True,
            defaults={"hostname": "localhost", "root_page": home, "site_name": "Test"},
        )
        index = ArticleIndexPage.objects.child_of(home).first()
        if not index:
            index = ArticleIndexPage(title="Статьи", slug="articles-search")
            home.add_child(instance=index)
            index.save_revision().publish()
        blog_index = BlogIndexPage.objects.child_of(home).first()
        if not blog_index:
            blog_index = BlogIndexPage(title="Блог", slug="blog-search")
            home.add_child(instance=blog_index)
            blog_index.save_revision().publish()

        article = ArticlePage(
            title="Раскопки у горки",
            slug="gorka-article",
            intro="Кратко про горку",
        )
        index.add_child(instance=article)
        article.body = [
            {
                "type": "paragraph",
                "value": "<p>На склоне горки найдены артефакты.</p>",
            }
        ]
        article.save_revision().publish()
        cls.article = article
        cls.blog_index = blog_index

        cls.author = User.objects.create_user(
            username="search-author",
            email="search-author@yandex.ru",
            password="pass-12345",
        )
        cls.post = BlogPost.objects.create(
            author=cls.author,
            body="Сегодня осмотрели холм и горку у реки.",
        )

    def test_blog_post_found_by_body_word(self):
        """Пост блога находится по слову из текста."""
        response = self.client.get("/search/", {"query": "холм"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "холм")
        self.assertContains(response, self.post.body[:20])

    def test_substring_finds_article(self):
        """Подстрока «горк» находит статью со словом «горка»."""
        response = self.client.get("/search/", {"query": "горк"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.article.title)

    def test_substring_finds_blog_post(self):
        """Подстрока «горк» находит пост блога со словом «горку»."""
        response = self.client.get("/search/", {"query": "горк"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "горку")

    def test_search_case_insensitive(self):
        """Поиск не зависит от регистра запроса."""
        response = self.client.get("/search/", {"query": "ГОРК"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.article.title)
        self.assertContains(response, "горку")
