(function () {
  var SCROLL_KEY = "archeologyArticleScrollY";
  var DRAWER_SCROLL_KEY = "archeologyCommentsDrawerScroll";
  var MOBILE_MAX = 1039;
  var COMMENT_FORM_SELECTOR =
    "form.comment-form, form.comment-form--reply, form.comment-form--compose, form.comment-form--edit, form.comment-delete";

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

  function saveScroll() {
    try {
      sessionStorage.setItem(SCROLL_KEY, String(window.scrollY));
      sessionStorage.setItem(DRAWER_SCROLL_KEY, String(drawer.scrollTop || 0));
    } catch (e) {
      /* ignore */
    }
  }

  // capture: успеваем сохранить скролл до ухода со страницы (в т.ч. после confirm)
  document.addEventListener(
    "submit",
    function (event) {
      var form = event.target;
      if (!form || !form.matches || !form.matches(COMMENT_FORM_SELECTOR)) return;
      saveScroll();
    },
    true
  );

  function restoreScroll() {
    var raw = null;
    var drawerRaw = null;
    try {
      raw = sessionStorage.getItem(SCROLL_KEY);
      drawerRaw = sessionStorage.getItem(DRAWER_SCROLL_KEY);
      if (raw !== null) sessionStorage.removeItem(SCROLL_KEY);
      if (drawerRaw !== null) sessionStorage.removeItem(DRAWER_SCROLL_KEY);
    } catch (e) {
      return;
    }
    var y = raw === null ? null : parseInt(raw, 10);
    var drawerY = drawerRaw === null ? null : parseInt(drawerRaw, 10);

    function apply() {
      if (y !== null && !isNaN(y)) window.scrollTo(0, y);
      if (drawerY !== null && !isNaN(drawerY)) drawer.scrollTop = drawerY;
    }

    window.requestAnimationFrame(function () {
      apply();
      window.requestAnimationFrame(function () {
        apply();
        window.setTimeout(apply, 50);
      });
    });
  }

  var composeBox = panel.querySelector("[data-comment-compose]");
  var composeBtn = panel.querySelector("[data-comments-compose]");
  var composeCancel = panel.querySelector("[data-comments-compose-cancel]");

  function scrollDrawerToBottom() {
    if (drawer && drawer.scrollHeight > drawer.clientHeight) {
      drawer.scrollTop = drawer.scrollHeight;
      return;
    }
    if (composeBox) {
      composeBox.scrollIntoView({ block: "nearest", behavior: "auto" });
    }
  }

  function openCompose() {
    if (!composeBox) return;
    composeBox.hidden = false;
    composeBox.classList.add("is-open");
    if (composeBtn) composeBtn.setAttribute("aria-expanded", "true");
    scrollDrawerToBottom();
    var textarea = composeBox.querySelector("textarea");
    if (textarea) {
      window.requestAnimationFrame(function () {
        scrollDrawerToBottom();
        textarea.focus({ preventScroll: true });
      });
    }
  }

  function closeCompose() {
    if (!composeBox) return;
    composeBox.hidden = true;
    composeBox.classList.remove("is-open");
    if (composeBtn) composeBtn.setAttribute("aria-expanded", "false");
  }

  if (composeBtn) {
    composeBtn.addEventListener("click", function () {
      if (composeBox && !composeBox.hidden) {
        closeCompose();
        return;
      }
      openCompose();
    });
  }
  if (composeCancel) {
    composeCancel.addEventListener("click", closeCompose);
  }

  function handlePostedOrCompose() {
    var params = new URLSearchParams(window.location.search);
    if (params.get("compose") === "1") {
      openCompose();
    } else if (params.get("posted") === "1") {
      var last = panel.querySelector(".comment-list > .comment:last-child");
      if (last && drawer) {
        last.scrollIntoView({ block: "nearest", behavior: "auto" });
        drawer.scrollTop = drawer.scrollHeight;
      } else {
        scrollDrawerToBottom();
      }
    }
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
    if (event.key !== "Escape" || !panel.classList.contains("is-open") || isMobile()) {
      return;
    }
    // Не закрывать панель, если открыт просмотр фото
    var lightbox = document.querySelector("[data-comment-lightbox-root]");
    if (lightbox && !lightbox.hidden) return;
    closePanel();
  });

  var openedFromServer =
    panel.classList.contains("is-open") ||
    (layout && layout.classList.contains("is-comments-open"));

  if (openedFromServer) {
    restoreScroll();
    handlePostedOrCompose();
    return;
  }

  if (isMobile()) {
    openPanel();
    restoreScroll();
    handlePostedOrCompose();
    return;
  }

  if (
    panel.getAttribute("data-open-on-load") === "1" ||
    window.location.hash === "#comments"
  ) {
    openPanel();
    restoreScroll();
    handlePostedOrCompose();
  }
})();
