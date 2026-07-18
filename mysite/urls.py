from django.conf import settings
from django.urls import include, path
from django.contrib import admin

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls

from accounts import views as accounts_views
from articles import editor_views as articles_editor_views
from articles import views as articles_views
from blog import views as blog_views
from search import views as search_views

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("accounts/profile/", accounts_views.profile, name="account_profile"),
    path("accounts/", include("allauth.urls")),
    path("search/", search_views.search, name="search"),
    path("comments/add/<int:page_id>/", articles_views.add_comment, name="comment_add"),
    path(
        "comments/edit/<int:comment_id>/",
        articles_views.edit_comment,
        name="comment_edit",
    ),
    path(
        "comments/delete/<int:comment_id>/",
        articles_views.delete_comment,
        name="comment_delete",
    ),
    path("articles/new/", articles_editor_views.create_article, name="article_create"),
    path(
        "articles/upload-image/",
        articles_editor_views.upload_article_image,
        name="article_upload_image",
    ),
    path(
        "articles/<int:page_id>/edit/",
        articles_editor_views.edit_article,
        name="article_edit",
    ),
    path(
        "articles/<int:page_id>/view/",
        articles_views.record_article_view,
        name="article_view",
    ),
    path("blog/posts/add/", blog_views.add_post, name="blog_post_add"),
    path("blog/posts/edit/<int:post_id>/", blog_views.edit_post, name="blog_post_edit"),
    path("blog/posts/delete/<int:post_id>/", blog_views.delete_post, name="blog_post_delete"),
    path(
        "blog/posts/view/<int:post_id>/",
        blog_views.record_post_view,
        name="blog_post_view",
    ),
    path("blog/posts/like/<int:post_id>/", blog_views.toggle_post_like, name="blog_post_like"),
    path("blog/comments/add/<int:post_id>/", blog_views.add_comment, name="blog_comment_add"),
    path(
        "blog/comments/edit/<int:comment_id>/",
        blog_views.edit_comment,
        name="blog_comment_edit",
    ),
    path(
        "blog/comments/delete/<int:comment_id>/",
        blog_views.delete_comment,
        name="blog_comment_delete",
    ),
    path(
        "blog/comments/like/<int:comment_id>/",
        blog_views.toggle_comment_like,
        name="blog_comment_like",
    ),
]


if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Serve static and media files from development server
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns = urlpatterns + [
    # For anything not caught by a more specific rule above, hand over to
    # Wagtail's page serving mechanism. This should be the last pattern in
    # the list:
    path("", include(wagtail_urls)),
    # Alternatively, if you want Wagtail pages to be served from a subpath
    # of your site, rather than the site root:
    #    path("pages/", include(wagtail_urls)),
]
