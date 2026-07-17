from django import forms

from articles.models import Comment, CommentImage

MAX_COMMENT_IMAGES = 3
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def validate_comment_images(files, max_count=MAX_COMMENT_IMAGES):
    """Проверяет список загруженных файлов; возвращает очищенный список."""
    images = [f for f in files if f]
    if len(images) > max_count:
        raise forms.ValidationError(
            f"Можно прикрепить не больше {MAX_COMMENT_IMAGES} изображений."
        )
    cleaned = []
    for uploaded in images:
        content_type = getattr(uploaded, "content_type", "") or ""
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise forms.ValidationError(
                "Допустимы только JPEG, PNG, WebP или GIF."
            )
        if uploaded.size > MAX_IMAGE_BYTES:
            raise forms.ValidationError(
                "Каждое изображение — не больше 5 МБ."
            )
        cleaned.append(uploaded)
    return cleaned


class CommentForm(forms.ModelForm):
    parent_id = forms.IntegerField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Comment
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Ваш комментарий",
                    "class": "comment-textarea",
                }
            ),
        }
        labels = {"body": "Комментарий"}

    def __init__(self, *args, article=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.article = article
        self.parent_comment = None
        self.cleaned_images = []

    def clean_body(self):
        return (self.cleaned_data.get("body") or "").strip()

    def clean(self):
        cleaned = super().clean()
        body = cleaned.get("body") or ""
        files = self.files.getlist("images") if self.files else []
        try:
            self.cleaned_images = validate_comment_images(files)
        except forms.ValidationError as exc:
            self.add_error(None, exc)
            self.cleaned_images = []

        if not body and not self.cleaned_images:
            raise forms.ValidationError(
                "Введите текст или прикрепите хотя бы одно изображение."
            )

        parent_id = cleaned.get("parent_id")
        if not parent_id:
            self.parent_comment = None
            return cleaned
        if self.article is None:
            raise forms.ValidationError("Не указана статья.")
        parent = (
            Comment.objects.filter(
                pk=parent_id,
                article=self.article,
                parent__isnull=True,
            )
            .select_related("author")
            .first()
        )
        if parent is None:
            raise forms.ValidationError(
                "Нельзя ответить на этот комментарий (возможно, это уже ответ)."
            )
        if parent.is_deleted:
            raise forms.ValidationError("Нельзя ответить на удалённый комментарий.")
        self.parent_comment = parent
        return cleaned

    def save(self, commit=True):
        comment = super().save(commit=False)
        comment.parent = self.parent_comment
        if not comment.body:
            comment.body = ""
        if commit:
            comment.save()
            self._save_images(comment)
        return comment

    def _save_images(self, comment):
        for index, uploaded in enumerate(self.cleaned_images):
            CommentImage.objects.create(
                comment=comment,
                image=uploaded,
                sort_order=index,
            )


class CommentEditForm(forms.Form):
    body = forms.CharField(
        required=False,
        label="Комментарий",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": "comment-textarea",
                "placeholder": "Ваш комментарий",
            }
        ),
    )

    def __init__(self, *args, comment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.comment = comment
        self.cleaned_images = []
        self.remove_image_ids = set()
        self.kept_images = []

    def clean_body(self):
        return (self.cleaned_data.get("body") or "").strip()

    def clean(self):
        cleaned = super().clean()
        if self.comment is None:
            raise forms.ValidationError("Не указан комментарий.")

        body = cleaned.get("body") or ""
        existing = list(self.comment.images.all())
        existing_ids = {img.pk for img in existing}

        raw_ids = self.data.getlist("remove_images")
        remove_ids = set()
        for raw in raw_ids:
            try:
                image_id = int(raw)
            except (TypeError, ValueError):
                continue
            if image_id in existing_ids:
                remove_ids.add(image_id)

        kept = [img for img in existing if img.pk not in remove_ids]
        slots = MAX_COMMENT_IMAGES - len(kept)
        files = self.files.getlist("images") if self.files else []
        try:
            new_images = validate_comment_images(files, max_count=max(slots, 0))
        except forms.ValidationError as exc:
            self.add_error(None, exc)
            new_images = []

        if slots < 0:
            self.add_error(None, "Можно оставить не больше трёх изображений.")
        elif len(files) > slots:
            # validate уже кинет при max_count, но на всякий случай
            pass

        if not body and not kept and not new_images:
            raise forms.ValidationError(
                "Оставьте текст или хотя бы одно изображение."
            )

        self.remove_image_ids = remove_ids
        self.kept_images = kept
        self.cleaned_images = new_images
        return cleaned

    def save(self):
        comment = self.comment
        comment.body = self.cleaned_data.get("body") or ""
        comment.save(update_fields=["body"], skip_validation=True)

        for image in comment.images.filter(pk__in=self.remove_image_ids):
            image.delete()

        next_order = 0
        if self.kept_images:
            next_order = max(img.sort_order for img in self.kept_images) + 1
        for offset, uploaded in enumerate(self.cleaned_images):
            CommentImage.objects.create(
                comment=comment,
                image=uploaded,
                sort_order=next_order + offset,
            )
        return comment
