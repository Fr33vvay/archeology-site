from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.forms import ProfileForm
from articles.models import FavoriteArticle


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль сохранён.")
            return redirect("account_profile")
    else:
        form = ProfileForm(instance=request.user)
    favorites = (
        FavoriteArticle.objects.filter(user=request.user)
        .select_related("article")
        .order_by("-created_at")
    )
    return render(
        request,
        "account/profile.html",
        {
            "form": form,
            "profile_email": request.user.email,
            "favorites": favorites,
        },
    )
