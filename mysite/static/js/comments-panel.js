(function () {
  var SCROLL_KEY = "archeologyArticleScrollY";

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
    if (window.history && window.history.replaceState) {
      var url = new URL(window.location.href);
      if (url.searchParams.has("comments")) {
        url.searchParams.delete("comments");
        url.hash = "";
        window.history.replaceState(null, "", url.pathname + url.search);
      }
    }
  }

  // Перед отправкой комментария запоминаем, где читали статью
  document.querySelectorAll("form.comment-form, form.comment-form--reply, form.comment-delete").forEach(function (form) {
    form.addEventListener("submit", function () {
      try {
        sessionStorage.setItem(SCROLL_KEY, String(window.scrollY));
      } catch (e) {
        /* ignore */
      }
    });
  });

  function restoreScroll() {
    var raw = null;
    try {
      raw = sessionStorage.getItem(SCROLL_KEY);
      if (raw !== null) sessionStorage.removeItem(SCROLL_KEY);
    } catch (e) {
      return;
    }
    if (raw === null) return;
    var y = parseInt(raw, 10);
    if (isNaN(y)) return;
    // После раскладки с открытой панелью
    window.requestAnimationFrame(function () {
      window.scrollTo(0, y);
      window.requestAnimationFrame(function () {
        window.scrollTo(0, y);
      });
    });
  }

  openBtn.addEventListener("click", openPanel);
  if (closeBtn) closeBtn.addEventListener("click", closePanel);

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && panel.classList.contains("is-open")) {
      closePanel();
    }
  });

  var openedFromServer =
    panel.classList.contains("is-open") ||
    (layout && layout.classList.contains("is-comments-open"));

  if (openedFromServer) {
    restoreScroll();
    return;
  }

  if (
    panel.getAttribute("data-open-on-load") === "1" ||
    window.location.hash === "#comments"
  ) {
    openPanel();
    restoreScroll();
  }
})();
