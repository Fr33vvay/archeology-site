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
        img.alt = "Превью выбранного фото";
        img.src = URL.createObjectURL(file);
        img.onload = function () {
          URL.revokeObjectURL(img.src);
        };
        preview.appendChild(img);
      });
    });
  }

  document.querySelectorAll("[data-comment-images]").forEach(bindPreview);

  var lightbox = document.querySelector("[data-comment-lightbox-root]");
  var lightboxImg = document.querySelector("[data-comment-lightbox-img]");
  var closeBtn = document.querySelector("[data-comment-lightbox-close]");
  if (!lightbox || !lightboxImg) return;

  function openLightbox(src) {
    if (!src) return;
    lightboxImg.src = src;
    lightbox.hidden = false;
    lightbox.setAttribute("aria-hidden", "false");
    document.documentElement.classList.add("is-lightbox-open");
  }

  function closeLightbox() {
    lightbox.hidden = true;
    lightbox.setAttribute("aria-hidden", "true");
    lightboxImg.removeAttribute("src");
    document.documentElement.classList.remove("is-lightbox-open");
  }

  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-comment-lightbox]");
    if (!trigger) return;
    event.preventDefault();
    var src =
      trigger.getAttribute("data-full-src") || trigger.getAttribute("href");
    openLightbox(src);
  });

  if (closeBtn) closeBtn.addEventListener("click", closeLightbox);
  lightbox.addEventListener("click", function (event) {
    if (event.target === lightbox) closeLightbox();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !lightbox.hidden) {
      closeLightbox();
    }
  });
})();
