(function () {
  var SCROLL_KEY = "archeologyArticleScrollY";
  var MOBILE_MAX = 1039;

  var panel = document.querySelector("[data-comments-panel]");
  if (!panel) return;

  var layout = document.querySelector("[data-article-layout]");
  var articleTop = document.querySelector("[data-article-top]");
  var openBtn = panel.querySelector("[data-comments-open]");
  var closeBtn = panel.querySelector("[data-comments-close]");
  var collapseBtn = panel.querySelector("[data-comments-collapse]");
  var drawer = panel.querySelector("[data-comments-drawer]");
  var navLink = document.querySelector("[data-comments-nav]");
  if (!openBtn || !drawer) return;

  function isMobile() {
    return window.matchMedia("(max-width: " + MOBILE_MAX + "px)").matches;
  }

  function headerOffset() {
    var header = document.querySelector(".site-header");
    if (!header) return 0;
    return Math.ceil(header.getBoundingClientRect().height) + 8;
  }

  /** Мгновенный скролл к элементу с учётом липкой шапки */
  function jumpToElement(el) {
    if (!el) return;
    var top = el.getBoundingClientRect().top + window.scrollY - headerOffset();
    window.scrollTo(0, Math.max(0, top));
  }

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

  function collapseAndGoUp() {
    closePanel();
    jumpToElement(articleTop || document.body);
  }

  function scrollToComments() {
    openPanel();
    jumpToElement(panel);
  }

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
    window.requestAnimationFrame(function () {
      window.scrollTo(0, y);
      window.requestAnimationFrame(function () {
        window.scrollTo(0, y);
      });
    });
  }

  openBtn.addEventListener("click", openPanel);
  if (closeBtn) closeBtn.addEventListener("click", closePanel);
  if (collapseBtn) collapseBtn.addEventListener("click", collapseAndGoUp);

  if (navLink) {
    navLink.addEventListener("click", function (event) {
      event.preventDefault();
      scrollToComments();
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && panel.classList.contains("is-open") && !isMobile()) {
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

  if (isMobile()) {
    openPanel();
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
