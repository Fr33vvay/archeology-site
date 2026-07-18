(function () {
  function csrfToken() {
    var input = document.querySelector("[name=csrfmiddlewaretoken]");
    if (input && input.value) return input.value;
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function showToast(message) {
    var toast = document.getElementById("favorite-toast");
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    toast.classList.add("is-visible");
    window.clearTimeout(showToast._timer);
    showToast._timer = window.setTimeout(function () {
      toast.classList.remove("is-visible");
      toast.hidden = true;
    }, 3200);
  }

  function updateButton(button, favorited) {
    button.classList.toggle("is-active", favorited);
    button.setAttribute("aria-pressed", favorited ? "true" : "false");
    var label = button.querySelector("[data-favorite-label]");
    if (label) label.textContent = favorited ? "Убрать" : "В избранное";
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.hasAttribute("data-favorite-form")) {
      return;
    }
    event.preventDefault();
    var button = form.querySelector("[data-favorite-button]");
    if (!button || button.disabled) return;
    button.disabled = true;
    fetch(form.action, {
      method: "POST",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfToken(),
      },
      body: new FormData(form),
      credentials: "same-origin",
    })
      .then(function (response) {
        if (response.status === 302 || response.redirected) {
          window.location.href = response.url || "/accounts/login/";
          return null;
        }
        if (!response.ok) throw new Error("favorite failed");
        return response.json();
      })
      .then(function (data) {
        if (!data) return;
        updateButton(button, Boolean(data.favorited));
        if (data.toast) showToast(data.toast);
      })
      .catch(function () {
        form.submit();
      })
      .finally(function () {
        button.disabled = false;
      });
  });
})();
