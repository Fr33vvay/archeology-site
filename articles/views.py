from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from articles.forms import CommentEditForm, CommentForm
from articles.models import ArticlePage, Comment


def _form_error_messages(form, fallback="Не удалось отправить комментарий."):
    errors = []
    for field, field_errors in form.errors.items():
        for err in field_errors:
            errors.append(str(err))
    return errors or [fallback]


def _redirect_to_comments(request, article, *, compose=False, posted=False):
    # Без #comments — иначе браузер скроллит к панели и сбивает место в статье
    params = ["comments=1"]
    if compose:
        params.append("compose=1")
    if posted:
        params.append("posted=1")
    return redirect(article.get_url(request) + "?" + "&".join(params))


@login_required
@require_POST
def add_comment(request, page_id):
    article = get_object_or_404(ArticlePage.objects.live().public(), pk=page_id)
    form = CommentForm(request.POST, request.FILES, article=article)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.article = article
        comment.author = request.user
        comment.save()
        form._save_images(comment)
        if comment.parent_id:
            messages.success(request, "Ответ опубликован.")
            return _redirect_to_comments(request, article)
        messages.success(request, "Комментарий опубликован.")
        # После своего комментария — к низу ленты, чтобы увидеть публикацию
        return _redirect_to_comments(request, article, posted=True)
    for err in _form_error_messages(form):
        messages.error(request, err)
    return _redirect_to_comments(request, article, compose=True)


@login_required
@require_POST
def edit_comment(request, comment_id):
    comment = get_object_or_404(
        Comment.objects.select_related("article").prefetch_related("images"),
        pk=comment_id,
    )
    if not comment.can_edit(request.user):
        return HttpResponseForbidden("Недостаточно прав для редактирования.")
    article = comment.article
    if not article.live:
        raise Http404
    form = CommentEditForm(request.POST, request.FILES, comment=comment)
    if form.is_valid():
        form.save()
        messages.success(request, "Комментарий обновлён.")
    else:
        for err in _form_error_messages(form, "Не удалось сохранить изменения."):
            messages.error(request, err)
    return _redirect_to_comments(request, article)


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
    messages.success(request, "Комментарий удалён.")
    return _redirect_to_comments(request, article)
