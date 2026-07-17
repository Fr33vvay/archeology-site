from allauth.account.forms import SignupForm
from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomSignupForm(SignupForm):
    first_name = forms.CharField(
        label="Имя",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        label="Фамилия",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )

    def save(self, request):
        user = super().save(request)
        user.first_name = (self.cleaned_data.get("first_name") or "").strip()
        user.last_name = (self.cleaned_data.get("last_name") or "").strip()
        user.save(update_fields=["first_name", "last_name"])
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name")
        labels = {
            "first_name": "Имя",
            "last_name": "Фамилия",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = False

    def clean_first_name(self):
        value = (self.cleaned_data.get("first_name") or "").strip()
        if not value:
            raise forms.ValidationError("Укажите имя.")
        return value

    def clean_last_name(self):
        return (self.cleaned_data.get("last_name") or "").strip()
