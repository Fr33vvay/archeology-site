from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from articles.forms import CommentForm
from articles.models import ArticlePage, Comment


@login_required
@require_POST
def add_comment(request, page_id):
    article = get_object_or_404(ArticlePage.objects.live().public(), pk=page_id)
    form = CommentForm(request.POST, article=article)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.article = article
        comment.author = request.user
        comment.save()
        messages.success(request, "Комментарий опубликован.")
    else:
        messages.error(request, "Не удалось отправить комментарий. Проверьте текст.")
    return redirect(article.url + "#comments")


@login_required
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    if not comment.can_delete(request.user):
        return HttpResponseForbidden("Недостаточно прав для удаления.")
    article = comment.article
    if not article.live:
        raise Http404
    comment.soft_delete()
    return redirect(article.url + "#comments")
