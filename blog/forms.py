from django import forms

from articles.forms import validate_comment_images
from blog.models import BlogComment, BlogPost, BlogPostImage

MAX_POST_IMAGES = 3


class BlogPostForm(forms.ModelForm):
    class Meta:
        model = BlogPost
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "О чём расскажете?",
                    "class": "comment-textarea",
                }
            ),
        }
        labels = {"body": "Текст"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleaned_images = []

    def clean_body(self):
        return (self.cleaned_data.get("body") or "").strip()

    def clean(self):
        cleaned = super().clean()
        body = cleaned.get("body") or ""
        files = self.files.getlist("images") if self.files else []
        try:
            self.cleaned_images = validate_comment_images(files, max_count=MAX_POST_IMAGES)
        except forms.ValidationError as exc:
            self.add_error(None, exc)
            self.cleaned_images = []

        if not body and not self.cleaned_images:
            raise forms.ValidationError(
                "Введите текст или прикрепите хотя бы одно изображение."
            )
        return cleaned

    def save(self, commit=True):
        post = super().save(commit=False)
        if not post.body:
            post.body = ""
        if commit:
            post.save()
            self._save_images(post)
        return post

    def _save_images(self, post):
        for index, uploaded in enumerate(self.cleaned_images):
            BlogPostImage.objects.create(post=post, image=uploaded, sort_order=index)


class BlogPostEditForm(forms.ModelForm):
    """Редактирование текста своего поста (без изменения фото)."""

    class Meta:
        model = BlogPost
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(
                attrs={"rows": 4, "class": "comment-textarea", "placeholder": "Текст поста"}
            ),
        }
        labels = {"body": "Текст"}

    def clean_body(self):
        return (self.cleaned_data.get("body") or "").strip()

    def clean(self):
        cleaned = super().clean()
        body = cleaned.get("body") or ""
        if not body and not self.instance.images.exists():
            raise forms.ValidationError(
                "Оставьте текст или хотя бы одно изображение."
            )
        return cleaned

    def save(self, commit=True):
        post = super().save(commit=False)
        if commit:
            post.save(update_fields=["body"], skip_validation=True)
        return post


class BlogCommentForm(forms.ModelForm):
    class Meta:
        model = BlogComment
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Ваш комментарий",
                    "class": "comment-textarea",
                }
            ),
        }
        labels = {"body": "Комментарий"}

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("Введите текст комментария.")
        return body
