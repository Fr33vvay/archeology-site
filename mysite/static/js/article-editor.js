(function () {
  var form = document.querySelector("[data-article-editor]");
  if (!form) return;

  var blocksRoot = form.querySelector("[data-blocks]");
  var jsonInput = form.querySelector("[data-blocks-json]");
  var uploadUrl = form.getAttribute("data-upload-url");
  var csrf = (form.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";
  var initial = [];
  try {
    initial = JSON.parse(document.getElementById("article-editor-initial").textContent || "[]");
  } catch (e) {
    initial = [];
  }

  function csrfHeaders() {
    return { "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest" };
  }

  function uploadImage(file) {
    var body = new FormData();
    body.append("image", file);
    body.append("title", file.name || "image");
    return fetch(uploadUrl, { method: "POST", headers: csrfHeaders(), body: body, credentials: "same-origin" }).then(
      function (r) {
        if (!r.ok) throw new Error("upload failed");
        return r.json();
      }
    );
  }

  function blockShell(type, title) {
    var el = document.createElement("div");
    el.className = "article-editor__block";
    el.dataset.type = type;
    el.innerHTML =
      '<div class="article-editor__block-head">' +
      "<strong>" +
      title +
      "</strong>" +
      '<div class="article-editor__block-tools">' +
      '<button type="button" data-move="-1" title="Выше">↑</button>' +
      '<button type="button" data-move="1" title="Ниже">↓</button>' +
      '<button type="button" data-remove title="Удалить">×</button>' +
      "</div></div>" +
      '<div class="article-editor__block-body"></div>';
    return el;
  }

  function addParagraph(value) {
    var el = blockShell("paragraph", "Абзац");
    var body = el.querySelector(".article-editor__block-body");
    body.innerHTML =
      '<label class="auth-label"><span>Текст (можно HTML)</span>' +
      '<textarea rows="6" data-field="value"></textarea></label>';
    body.querySelector("[data-field=value]").value = value || "";
    blocksRoot.appendChild(el);
  }

  function addHeading(value) {
    var el = blockShell("heading", "Заголовок");
    var body = el.querySelector(".article-editor__block-body");
    body.innerHTML =
      '<label class="auth-label"><span>Заголовок</span>' +
      '<input type="text" data-field="value" maxlength="255"></label>';
    body.querySelector("[data-field=value]").value = value || "";
    blocksRoot.appendChild(el);
  }

  function addQuote(value) {
    var el = blockShell("quote", "Цитата");
    var body = el.querySelector(".article-editor__block-body");
    body.innerHTML =
      '<label class="auth-label"><span>Цитата</span>' +
      '<textarea rows="3" data-field="value"></textarea></label>';
    body.querySelector("[data-field=value]").value = value || "";
    blocksRoot.appendChild(el);
  }

  function addImage(value) {
    value = value || {};
    var el = blockShell("image", "Иллюстрация");
    var body = el.querySelector(".article-editor__block-body");
    body.innerHTML =
      '<input type="hidden" data-field="image" value="">' +
      '<img class="article-editor__preview" data-preview alt="" hidden>' +
      '<label class="auth-label"><span>Файл</span><input type="file" accept="image/*" data-file></label>' +
      '<label class="auth-label"><span>Подпись</span><input type="text" data-field="caption" maxlength="255"></label>';
    var idInput = body.querySelector("[data-field=image]");
    var preview = body.querySelector("[data-preview]");
    var caption = body.querySelector("[data-field=caption]");
    caption.value = value.caption || "";
    if (value.image) {
      idInput.value = value.image;
      if (value.preview_url) {
        preview.src = value.preview_url;
        preview.hidden = false;
      }
    }
    body.querySelector("[data-file]").addEventListener("change", function (ev) {
      var file = ev.target.files && ev.target.files[0];
      if (!file) return;
      uploadImage(file)
        .then(function (data) {
          idInput.value = data.id;
          preview.src = data.url;
          preview.hidden = false;
        })
        .catch(function () {
          alert("Не удалось загрузить изображение.");
        });
    });
    blocksRoot.appendChild(el);
  }

  function addGallery(value) {
    value = value || { title: "", images: [] };
    var el = blockShell("gallery", "Галерея-врезка");
    var body = el.querySelector(".article-editor__block-body");
    body.innerHTML =
      '<label class="auth-label"><span>Заголовок врезки</span>' +
      '<input type="text" data-field="title" maxlength="120"></label>' +
      '<div data-gallery-images></div>' +
      '<button type="button" class="button" data-gallery-add>+ Фото во врезку</button>';
    body.querySelector("[data-field=title]").value = value.title || "";
    var list = body.querySelector("[data-gallery-images]");

    function addGalleryImage(img) {
      img = img || {};
      var row = document.createElement("div");
      row.className = "article-editor__gallery-item";
      row.innerHTML =
        '<input type="hidden" data-field="image" value="">' +
        '<img class="article-editor__preview" data-preview alt="" hidden>' +
        '<input type="file" accept="image/*" data-file>' +
        '<input type="text" data-field="caption" placeholder="Подпись" maxlength="255">' +
        '<button type="button" data-gallery-remove>×</button>';
      var idInput = row.querySelector("[data-field=image]");
      var preview = row.querySelector("[data-preview]");
      row.querySelector("[data-field=caption]").value = img.caption || "";
      if (img.image) {
        idInput.value = img.image;
        if (img.preview_url) {
          preview.src = img.preview_url;
          preview.hidden = false;
        }
      }
      row.querySelector("[data-file]").addEventListener("change", function (ev) {
        var file = ev.target.files && ev.target.files[0];
        if (!file) return;
        uploadImage(file)
          .then(function (data) {
            idInput.value = data.id;
            preview.src = data.url;
            preview.hidden = false;
          })
          .catch(function () {
            alert("Не удалось загрузить изображение.");
          });
      });
      row.querySelector("[data-gallery-remove]").addEventListener("click", function () {
        row.remove();
      });
      list.appendChild(row);
    }

    (value.images || []).forEach(addGalleryImage);
    body.querySelector("[data-gallery-add]").addEventListener("click", function () {
      addGalleryImage({});
    });
    blocksRoot.appendChild(el);
  }

  function addBlock(type, value) {
    if (type === "paragraph") addParagraph(value);
    else if (type === "heading") addHeading(value);
    else if (type === "quote") addQuote(value);
    else if (type === "image") addImage(value);
    else if (type === "gallery") addGallery(value);
  }

  initial.forEach(function (b) {
    addBlock(b.type, b.value);
  });
  if (!initial.length) addParagraph("");

  form.querySelectorAll("[data-add]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      addBlock(btn.getAttribute("data-add"));
    });
  });

  blocksRoot.addEventListener("click", function (ev) {
    var remove = ev.target.closest("[data-remove]");
    if (remove) {
      var block = remove.closest(".article-editor__block");
      if (block) block.remove();
      return;
    }
    var move = ev.target.closest("[data-move]");
    if (!move) return;
    var el = move.closest(".article-editor__block");
    if (!el) return;
    var dir = Number(move.getAttribute("data-move"));
    if (dir < 0 && el.previousElementSibling) {
      el.parentNode.insertBefore(el, el.previousElementSibling);
    } else if (dir > 0 && el.nextElementSibling) {
      el.parentNode.insertBefore(el.nextElementSibling, el);
    }
  });

  var coverFile = form.querySelector("[data-cover-file]");
  var coverId = form.querySelector("[data-cover-id]");
  var coverPreview = form.querySelector("[data-cover-preview]");
  if (coverFile) {
    coverFile.addEventListener("change", function (ev) {
      var file = ev.target.files && ev.target.files[0];
      if (!file) return;
      uploadImage(file)
        .then(function (data) {
          coverId.value = data.id;
          coverPreview.src = data.url;
          coverPreview.hidden = false;
        })
        .catch(function () {
          alert("Не удалось загрузить обложку.");
        });
    });
  }

  function collectBlocks() {
    var blocks = [];
    blocksRoot.querySelectorAll(".article-editor__block").forEach(function (el) {
      var type = el.dataset.type;
      if (type === "paragraph" || type === "heading" || type === "quote") {
        var val = (el.querySelector("[data-field=value]") || {}).value || "";
        if (String(val).trim()) blocks.push({ type: type, value: val });
        return;
      }
      if (type === "image") {
        var image = (el.querySelector("[data-field=image]") || {}).value;
        if (!image) return;
        blocks.push({
          type: "image",
          value: {
            image: Number(image),
            caption: (el.querySelector("[data-field=caption]") || {}).value || "",
          },
        });
        return;
      }
      if (type === "gallery") {
        var images = [];
        el.querySelectorAll(".article-editor__gallery-item").forEach(function (row) {
          var id = (row.querySelector("[data-field=image]") || {}).value;
          if (!id) return;
          images.push({
            image: Number(id),
            caption: (row.querySelector("[data-field=caption]") || {}).value || "",
          });
        });
        if (!images.length) return;
        blocks.push({
          type: "gallery",
          value: {
            title: (el.querySelector("[data-field=title]") || {}).value || "",
            images: images,
          },
        });
      }
    });
    return blocks;
  }

  form.addEventListener("submit", function () {
    jsonInput.value = JSON.stringify(collectBlocks());
  });
})();
