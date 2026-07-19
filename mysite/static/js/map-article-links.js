(function () {
  function isDesktop() {
    return window.matchMedia && window.matchMedia("(min-width: 768px)").matches;
  }

  function applyTargets() {
    var desktop = isDesktop();
    document.querySelectorAll("a.map-point-link").forEach(function (link) {
      if (desktop) {
        link.setAttribute("target", "_blank");
        link.setAttribute("rel", "noopener noreferrer");
      } else {
        link.removeAttribute("target");
        link.removeAttribute("rel");
      }
    });
  }

  applyTargets();
  if (window.matchMedia) {
    window.matchMedia("(min-width: 768px)").addEventListener("change", applyTargets);
  }
})();
