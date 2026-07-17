(function () {
  document.querySelectorAll("[data-comments-toggle]").forEach(function (btn) {
    var targetId = btn.getAttribute("data-comments-toggle");
    var rest = document.getElementById(targetId);
    if (!rest) return;
    btn.addEventListener("click", function () {
      rest.hidden = !rest.hidden;
      btn.textContent = rest.hidden ? btn.dataset.showLabel : btn.dataset.hideLabel;
    });
  });
})();
