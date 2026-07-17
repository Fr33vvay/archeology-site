(function () {
  var panel = document.querySelector("[data-comments-panel]");
  if (!panel) return;

  var openBtn = panel.querySelector("[data-comments-open]");
  var closeBtn = panel.querySelector("[data-comments-close]");
  var drawer = panel.querySelector("[data-comments-drawer]");
  if (!openBtn || !drawer) return;

  var backdrop = document.createElement("button");
  backdrop.type = "button";
  backdrop.className = "comments-panel-backdrop";
  backdrop.setAttribute("aria-label", "Закрыть комментарии");
  document.body.appendChild(backdrop);

  function openPanel() {
    panel.classList.add("is-open");
    drawer.hidden = false;
    openBtn.setAttribute("aria-expanded", "true");
    openBtn.hidden = true;
    backdrop.classList.add("is-visible");
    document.body.style.overflow = "hidden";
  }

  function closePanel() {
    panel.classList.remove("is-open");
    drawer.hidden = true;
    openBtn.setAttribute("aria-expanded", "false");
    openBtn.hidden = false;
    backdrop.classList.remove("is-visible");
    document.body.style.overflow = "";
  }

  openBtn.addEventListener("click", openPanel);
  if (closeBtn) closeBtn.addEventListener("click", closePanel);
  backdrop.addEventListener("click", closePanel);

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
