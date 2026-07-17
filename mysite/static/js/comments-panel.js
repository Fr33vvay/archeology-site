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
  }

  openBtn.addEventListener("click", openPanel);
  if (closeBtn) closeBtn.addEventListener("click", closePanel);

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && panel.classList.contains("is-open")) {
      closePanel();
    }
  });

  if (
    panel.getAttribute("data-open-on-load") === "1" ||
    window.location.hash === "#comments"
  ) {
    openPanel();
  }
})();
