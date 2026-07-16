from django.dispatch import receiver
from wagtail.signals import page_published

from articles.models import ArticlePage


@receiver(page_published)
def sync_gallery_on_article_publish(sender, instance, **kwargs):
    """После публикации статьи обновляет связанную папку галереи."""
    if not isinstance(instance, ArticlePage):
        return
    from articles.gallery_sync import sync_gallery_folder_for_article

    sync_gallery_folder_for_article(instance)
