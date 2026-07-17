from django import forms

from articles.models import Comment


class CommentForm(forms.ModelForm):
    parent = forms.ModelChoiceField(
        queryset=Comment.objects.none(),
        required=False,
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = Comment
        fields = ("body", "parent")
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
        if article is not None:
            self.fields["parent"].queryset = Comment.objects.filter(
                article=article,
                parent__isnull=True,
                is_deleted=False,
            )

    def clean_parent(self):
        parent = self.cleaned_data.get("parent")
        if parent and parent.is_deleted:
            raise forms.ValidationError("Нельзя ответить на удалённый комментарий.")
        return parent

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("Введите текст комментария.")
        return body
