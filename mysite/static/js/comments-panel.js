(function () {
  var panel = document.querySelector("[data-comments-panel]");
  if (!panel) return;

  var layout = document.querySelector("[data-article-layout]");
  var openBtn = panel.querySelector("[data-comments-open]");
  var closeBtn = panel.querySelector("[data-comments-close]");
  var drawer = panel.querySelector("[data-comments-drawer]");
  if (!openBtn || !drawer) return;

  function openPanel() {
    panel.classList.add("is-open");
    if (layout) layout.classList.add("is-comments-open");
    drawer.hidden = false;
    openBtn.setAttribute("aria-expanded", "true");
    openBtn.hidden = true;
  }

  function closePanel() {
    panel.classList.remove("is-open");
    if (layout) layout.classList.remove("is-comments-open");
    drawer.hidden = true;
    openBtn.setAttribute("aria-expanded", "false");
    openBtn.hidden = false;
    // Убираем ?comments=1 из адреса, чтобы обновление не открывало панель снова
    if (window.history && window.history.replaceState) {
      var url = new URL(window.location.href);
      if (url.searchParams.has("comments")) {
        url.searchParams.delete("comments");
        url.hash = "";
        window.history.replaceState(null, "", url.pathname + url.search);
      }
    }
  }

  openBtn.addEventListener("click", openPanel);
  if (closeBtn) closeBtn.addEventListener("click", closePanel);

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && panel.classList.contains("is-open")) {
      closePanel();
    }
  });

  // Уже открыто с сервера (?comments=1) — ничего не трогаем, без повторной подгонки
  if (panel.classList.contains("is-open") || layout.classList.contains("is-comments-open")) {
    return;
  }

  if (
    panel.getAttribute("data-open-on-load") === "1" ||
    window.location.hash === "#comments"
  ) {
    openPanel();
  }
})();
