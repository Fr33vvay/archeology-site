from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from blog.forms import BlogCommentForm, BlogPostEditForm, BlogPostForm
from blog.models import BlogComment, BlogPost, BlogCommentLike, BlogPostLike
from blog.models import BlogIndexPage


def _form_error_messages(form, fallback="Не удалось выполнить действие."):
    errors = [str(err) for field_errors in form.errors.values() for err in field_errors]
    return errors or [fallback]


def _redirect_to_blog(request, anchor=None):
    blog_page = BlogIndexPage.objects.live().public().first()
    url = blog_page.get_url(request) if blog_page else "/"
    if anchor:
        url = f"{url}#{anchor}"
    return redirect(url)


@login_required
@require_POST
def add_post(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Публиковать посты может только суперпользователь.")
    form = BlogPostForm(request.POST, request.FILES)
    if form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        form._save_images(post)
        messages.success(request, "Пост опубликован.")
        return _redirect_to_blog(request, anchor=f"post-{post.pk}")
    for err in _form_error_messages(form):
        messages.error(request, err)
    return _redirect_to_blog(request)


@login_required
@require_POST
def edit_post(request, post_id):
    post = get_object_or_404(BlogPost, pk=post_id)
    if not post.can_edit(request.user):
        return HttpResponseForbidden("Недостаточно прав для редактирования.")
    form = BlogPostEditForm(request.POST, instance=post)
    if form.is_valid():
        form.save()
        messages.success(request, "Пост обновлён.")
    else:
        for err in _form_error_messages(form, "Не удалось сохранить изменения."):
            messages.error(request, err)
    return _redirect_to_blog(request, anchor=f"post-{post.pk}")


@login_required
@require_POST
def delete_post(request, post_id):
    post = get_object_or_404(BlogPost, pk=post_id)
    if not post.can_delete(request.user):
        return HttpResponseForbidden("Недостаточно прав для удаления.")
    post.soft_delete()
    messages.success(request, "Пост удалён.")
    return _redirect_to_blog(request)


@login_required
@require_POST
def toggle_post_like(request, post_id):
    post = get_object_or_404(BlogPost, pk=post_id, is_deleted=False)
    like, created = BlogPostLike.objects.get_or_create(post=post, user=request.user)
    if not created:
        like.delete()
    return _redirect_to_blog(request, anchor=f"post-{post.pk}")


@login_required
@require_POST
def add_comment(request, post_id):
    post = get_object_or_404(BlogPost, pk=post_id, is_deleted=False)
    form = BlogCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
        messages.success(request, "Комментарий опубликован.")
    else:
        for err in _form_error_messages(form):
            messages.error(request, err)
    return _redirect_to_blog(request, anchor=f"post-{post.pk}")


@login_required
@require_POST
def edit_comment(request, comment_id):
    comment = get_object_or_404(BlogComment.objects.select_related("post"), pk=comment_id)
    if not comment.can_edit(request.user):
        return HttpResponseForbidden("Недостаточно прав для редактирования.")
    form = BlogCommentForm(request.POST, instance=comment)
    if form.is_valid():
        form.save()
        messages.success(request, "Комментарий обновлён.")
    else:
        for err in _form_error_messages(form, "Не удалось сохранить изменения."):
            messages.error(request, err)
    return _redirect_to_blog(request, anchor=f"post-{comment.post_id}")


@login_required
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(BlogComment.objects.select_related("post"), pk=comment_id)
    if not comment.can_delete(request.user):
        return HttpResponseForbidden("Недостаточно прав для удаления.")
    post_id = comment.post_id
    comment.soft_delete()
    messages.success(request, "Комментарий удалён.")
    return _redirect_to_blog(request, anchor=f"post-{post_id}")


@login_required
@require_POST
def toggle_comment_like(request, comment_id):
    comment = get_object_or_404(BlogComment, pk=comment_id, is_deleted=False)
    like, created = BlogCommentLike.objects.get_or_create(comment=comment, user=request.user)
    if not created:
        like.delete()
    return _redirect_to_blog(request, anchor=f"post-{comment.post_id}")
