(function () {
  function csrfToken() {
    var input = document.querySelector("[name=csrfmiddlewaretoken]");
    if (input && input.value) return input.value;
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function updateButton(button, liked, count) {
    button.classList.toggle("is-active", liked);
    button.setAttribute("aria-pressed", liked ? "true" : "false");
    var countEl = button.querySelector("[data-like-count]");
    if (countEl) countEl.textContent = String(count);
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.classList.contains("like-form")) {
      return;
    }
    event.preventDefault();
    var button = form.querySelector(".like-button");
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
        if (!response.ok) throw new Error("like failed");
        return response.json();
      })
      .then(function (data) {
        updateButton(button, Boolean(data.liked), data.count);
      })
      .catch(function () {
        form.submit();
      })
      .finally(function () {
        button.disabled = false;
      });
  });
})();
