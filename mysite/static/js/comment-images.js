(function () {
  var MAX_IMAGES = 3;

  function bindPreview(input) {
    var field = input.closest(".comment-images-field");
    if (!field) return;
    var preview = field.querySelector("[data-comment-images-preview]");
    if (!preview) return;

    input.addEventListener("change", function () {
      var files = Array.prototype.slice.call(input.files || [], 0, MAX_IMAGES);
      preview.innerHTML = "";
      if (files.length < (input.files || []).length) {
        try {
          var dt = new DataTransfer();
          files.forEach(function (f) {
            dt.items.add(f);
          });
          input.files = dt.files;
        } catch (e) {
          /* старые браузеры: сервер всё равно отклонит лишнее */
        }
      }
      files.forEach(function (file) {
        if (!file.type || file.type.indexOf("image/") !== 0) return;
        var img = document.createElement("img");
        img.className = "comment-images-preview__item";
        img.alt = "";
        img.src = URL.createObjectURL(file);
        img.onload = function () {
          URL.revokeObjectURL(img.src);
        };
        preview.appendChild(img);
      });
    });
  }

  document.querySelectorAll("[data-comment-images]").forEach(bindPreview);

  var dialog = document.querySelector("[data-comment-lightbox-dialog]");
  var dialogImg = document.querySelector("[data-comment-lightbox-img]");
  var closeBtn = document.querySelector("[data-comment-lightbox-close]");
  if (!dialog || !dialogImg) return;

  function openLightbox(src) {
    if (!src) return;
    var scrollY = window.scrollY;
    dialogImg.src = src;
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
      // showModal часто сбрасывает прокрутку страницы — возвращаем
      window.scrollTo(0, scrollY);
      requestAnimationFrame(function () {
        window.scrollTo(0, scrollY);
      });
    } else {
      window.open(src, "_blank");
    }
  }

  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-comment-lightbox]");
    if (!trigger) return;
    event.preventDefault();
    event.stopPropagation();
    var src =
      trigger.getAttribute("data-full-src") || trigger.getAttribute("href");
    openLightbox(src);
  });

  function closeLightbox() {
    var scrollY = window.scrollY;
    if (typeof dialog.close === "function" && dialog.open) dialog.close();
    dialogImg.src = "";
    window.scrollTo(0, scrollY);
  }

  if (closeBtn) closeBtn.addEventListener("click", closeLightbox);
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) closeLightbox();
  });
  dialog.addEventListener("close", function () {
    dialogImg.src = "";
  });
})();
