from django import forms

from articles.models import Comment


class CommentForm(forms.ModelForm):
    # IntegerField надёжнее ModelChoiceField для скрытого parent из HTML-формы ответа
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

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("Введите текст комментария.")
        return body

    def clean(self):
        cleaned = super().clean()
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
        if commit:
            comment.save()
        return comment
