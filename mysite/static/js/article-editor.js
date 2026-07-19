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

  function isEmptyHtml(html) {
    var tmp = document.createElement("div");
    tmp.innerHTML = html || "";
    return !(tmp.textContent || "").trim();
  }

  function normalizeEditorHtml(html) {
    if (!html || isEmptyHtml(html)) return "";
    var tmp = document.createElement("div");
    tmp.innerHTML = html;
    tmp.querySelectorAll("script,style").forEach(function (node) {
      node.remove();
    });
    return tmp.innerHTML.trim();
  }

  function runCommand(cmd, value) {
    try {
      document.execCommand(cmd, false, value);
    } catch (e) {
      /* старые браузеры */
    }
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function nextFootnoteNumber() {
    var max = 0;
    var re = /#fn(?:ref)?-(\d+)/g;
    blocksRoot.querySelectorAll(".article-rte__editor").forEach(function (editor) {
      var html = editor.innerHTML || "";
      var match;
      while ((match = re.exec(html))) {
        max = Math.max(max, Number(match[1]));
      }
    });
    return max + 1;
  }

  function insertHtmlAtCursor(editor, html) {
    editor.focus();
    var sel = window.getSelection();
    if (!sel || !sel.rangeCount || !editor.contains(sel.anchorNode)) {
      editor.appendChild(document.createTextNode(""));
      var range = document.createRange();
      range.selectNodeContents(editor);
      range.collapse(false);
      sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    }
    var ok = false;
    try {
      ok = document.execCommand("insertHTML", false, html);
    } catch (e) {
      ok = false;
    }
    if (!ok) {
      var range2 = window.getSelection().getRangeAt(0);
      range2.deleteContents();
      var tmp = document.createElement("div");
      tmp.innerHTML = html;
      var frag = document.createDocumentFragment();
      var node;
      while ((node = tmp.firstChild)) frag.appendChild(node);
      range2.insertNode(frag);
    }
  }

  function findFootnotesOl() {
    var editors = blocksRoot.querySelectorAll(".article-rte__editor");
    for (var i = 0; i < editors.length; i++) {
      var ols = editors[i].querySelectorAll("ol");
      for (var j = 0; j < ols.length; j++) {
        if ((ols[j].innerHTML || "").indexOf("#fnref-") !== -1) {
          return { editor: editors[i], ol: ols[j] };
        }
      }
    }
    return null;
  }

  function appendFootnoteItem(n, noteText) {
    var liHtml =
      "<li>" + escapeHtml(noteText) + ' <a href="#fnref-' + n + '">↩</a></li>';
    var found = findFootnotesOl();
    if (found) {
      found.ol.insertAdjacentHTML("beforeend", liHtml);
      return;
    }
    addParagraph("<ol>" + liHtml + "</ol>");
  }

  function insertFootnote(editor) {
    var saved = null;
    var sel = window.getSelection();
    if (sel && sel.rangeCount && editor.contains(sel.anchorNode)) {
      saved = sel.getRangeAt(0).cloneRange();
    }
    var note = window.prompt("Текст сноски:", "");
    if (note === null || !String(note).trim()) return;
    note = String(note).trim();
    var n = nextFootnoteNumber();
    editor.focus();
    if (saved) {
      sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(saved);
    }
    insertHtmlAtCursor(
      editor,
      '<a href="#fn-' + n + '"><sup>' + n + "</sup></a>"
    );
    appendFootnoteItem(n, note);
  }

  function makeRichText(initialHtml) {
    var wrap = document.createElement("div");
    wrap.className = "article-rte";
    wrap.innerHTML =
      '<div class="article-rte__toolbar" role="toolbar" aria-label="Форматирование текста">' +
      '<button type="button" data-cmd="bold" title="Жирный"><b>Ж</b></button>' +
      '<button type="button" data-cmd="italic" title="Курсив"><i>К</i></button>' +
      '<button type="button" data-cmd="underline" title="Подчёркивание"><u>Ч</u></button>' +
      '<span class="article-rte__sep" aria-hidden="true"></span>' +
      '<button type="button" data-cmd="insertUnorderedList" title="Маркированный список">• Список</button>' +
      '<button type="button" data-cmd="insertOrderedList" title="Нумерованный список">1. Список</button>' +
      '<span class="article-rte__sep" aria-hidden="true"></span>' +
      '<button type="button" data-cmd="createLink" title="Ссылка">Ссылка</button>' +
      '<button type="button" data-cmd="insertFootnote" title="Сноска">Сноска</button>' +
      '<button type="button" data-cmd="superscript" title="Верхний индекс">x²</button>' +
      '<button type="button" data-cmd="subscript" title="Нижний индекс">x₂</button>' +
      '<span class="article-rte__sep" aria-hidden="true"></span>' +
      '<button type="button" data-cmd="undo" title="Отменить">↩</button>' +
      '<button type="button" data-cmd="redo" title="Повторить">↪</button>' +
      "</div>" +
      '<div class="article-rte__editor" contenteditable="true" data-field="value" role="textbox" aria-multiline="true"></div>';

    var editor = wrap.querySelector(".article-rte__editor");
    editor.innerHTML = initialHtml || "<p><br></p>";

    wrap.querySelector(".article-rte__toolbar").addEventListener("mousedown", function (ev) {
      // Не снимаем выделение в тексте при клике по кнопке
      if (ev.target.closest("button")) ev.preventDefault();
    });

    wrap.querySelector(".article-rte__toolbar").addEventListener("click", function (ev) {
      var btn = ev.target.closest("[data-cmd]");
      if (!btn) return;
      editor.focus();
      var cmd = btn.getAttribute("data-cmd");
      if (cmd === "createLink") {
        var url = window.prompt("Адрес ссылки (https://…)", "https://");
        if (!url) return;
        runCommand("createLink", url);
        return;
      }
      if (cmd === "insertFootnote") {
        insertFootnote(editor);
        return;
      }
      runCommand(cmd);
    });

    return wrap;
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
    body.appendChild(makeRichText(value || ""));
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
        if (!window.confirm("Удалить это фото из галереи?")) return;
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
      if (!block) return;
      if (!window.confirm("Точно удалить этот блок?")) return;
      block.remove();
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

  function fieldValue(el) {
    var field = el.querySelector("[data-field=value]");
    if (!field) return "";
    if (field.isContentEditable || field.getAttribute("contenteditable") === "true") {
      return normalizeEditorHtml(field.innerHTML);
    }
    return field.value || "";
  }

  function collectBlocks() {
    var blocks = [];
    blocksRoot.querySelectorAll(".article-editor__block").forEach(function (el) {
      var type = el.dataset.type;
      if (type === "paragraph" || type === "heading" || type === "quote") {
        var val = fieldValue(el);
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

  // ——— Точка на карте ———
  var mapPointUrl = form.getAttribute("data-map-point-url") || "/maps/points/";
  var articleId = form.getAttribute("data-article-id") || "";
  var mapAvailable = form.getAttribute("data-map-available") === "1";
  var mapModal = document.querySelector("[data-map-point-modal]");
  var mapBtn = form.querySelector("[data-map-point]");
  var miniMapEl = mapModal ? mapModal.querySelector("[data-map-point-mini-map]") : null;
  var titleInput = mapModal ? mapModal.querySelector("[data-map-point-title]") : null;
  var coordsEl = mapModal ? mapModal.querySelector("[data-map-point-coords]") : null;
  var hintEl = mapModal ? mapModal.querySelector("[data-map-point-hint]") : null;
  var pickedCoords = null;
  var miniMap = null;
  var miniPlacemark = null;
  // Модалка снимает фокус с RTE — помним блок и range до открытия.
  var mapInsertTarget = null;
  var lastRteSelection = null;

  function editorFromSelectionNode(node) {
    if (!node) return null;
    var el = node.nodeType === 1 ? node : node.parentElement;
    if (!el) return null;
    var found = el.closest(".article-rte__editor");
    if (!found || !blocksRoot.contains(found)) return null;
    return found;
  }

  function captureRteSelection() {
    var sel = window.getSelection();
    if (!sel || !sel.rangeCount) return null;
    var editor = editorFromSelectionNode(sel.anchorNode);
    if (!editor || !editor.contains(sel.anchorNode)) return null;
    return { editor: editor, range: sel.getRangeAt(0).cloneRange() };
  }

  document.addEventListener("selectionchange", function () {
    var captured = captureRteSelection();
    if (captured) lastRteSelection = captured;
  });

  function activeEditor() {
    var captured = captureRteSelection();
    if (captured) return captured.editor;
    if (mapInsertTarget && mapInsertTarget.editor && document.contains(mapInsertTarget.editor)) {
      return mapInsertTarget.editor;
    }
    if (lastRteSelection && lastRteSelection.editor && document.contains(lastRteSelection.editor)) {
      return lastRteSelection.editor;
    }
    return blocksRoot.querySelector(".article-rte__editor");
  }

  function closeMapModal() {
    if (!mapModal) return;
    mapModal.hidden = true;
    pickedCoords = null;
    if (titleInput) titleInput.value = "";
    if (coordsEl) coordsEl.textContent = "";
  }

  function openMapModal() {
    if (!mapModal) return;
    mapInsertTarget = captureRteSelection() || lastRteSelection;
    if (!articleId) {
      alert("Сначала сохраните статью как черновик, затем добавьте точку на карте.");
      return;
    }
    if (!mapAvailable || typeof ymaps === "undefined") {
      if (hintEl) {
        hintEl.textContent = "Карта временно недоступна: ключ Яндекс.Карт не настроен.";
      }
      if (miniMapEl) miniMapEl.hidden = true;
      mapModal.hidden = false;
      return;
    }
    if (hintEl) {
      hintEl.textContent = "Кликните по карте, чтобы выбрать координаты, затем укажите подпись.";
    }
    if (miniMapEl) miniMapEl.hidden = false;
    mapModal.hidden = false;
    ymaps.ready(function () {
      if (!miniMap) {
        miniMap = new ymaps.Map(miniMapEl, {
          center: [59.9386, 30.3141],
          zoom: 11,
          controls: ["zoomControl"],
        });
        miniMap.events.add("click", function (e) {
          var coords = e.get("coords");
          pickedCoords = { lat: coords[0], lon: coords[1] };
          if (coordsEl) {
            coordsEl.textContent =
              "Координаты: " + coords[0].toFixed(6) + ", " + coords[1].toFixed(6);
          }
          if (miniPlacemark) {
            miniPlacemark.geometry.setCoordinates(coords);
          } else {
            miniPlacemark = new ymaps.Placemark(coords, {}, { preset: "islands#brownDotIcon" });
            miniMap.geoObjects.add(miniPlacemark);
          }
        });
      } else {
        miniMap.container.fitToViewport();
      }
    });
  }

  function insertMapPointLink(data) {
    var target = mapInsertTarget;
    var editor = target && target.editor && document.contains(target.editor) ? target.editor : null;
    var savedRange = target && target.range ? target.range : null;
    if (!editor) {
      editor = activeEditor();
    }
    if (!editor) {
      addParagraph("");
      editor = activeEditor();
    }
    if (!editor) return;
    var label = escapeHtml(data.title || "На карте");
    var html =
      '<a id="' +
      escapeHtml(data.anchor_id) +
      '" class="map-point-link" href="' +
      escapeHtml(data.map_url) +
      '">На карте: ' +
      label +
      "</a>";
    editor.focus();
    if (savedRange && editor.contains(savedRange.startContainer)) {
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(savedRange);
    }
    insertHtmlAtCursor(editor, " " + html + " ");
    mapInsertTarget = null;
  }

  function saveMapPoint() {
    if (!articleId) {
      alert("Сначала сохраните статью как черновик.");
      return;
    }
    if (!mapAvailable || typeof ymaps === "undefined") {
      alert("Карта временно недоступна: ключ Яндекс.Карт не настроен.");
      return;
    }
    if (!pickedCoords) {
      alert("Кликните по карте, чтобы выбрать точку.");
      return;
    }
    var title = (titleInput && titleInput.value ? titleInput.value : "").trim();
    if (!title) {
      alert("Укажите подпись точки.");
      return;
    }
    fetch(mapPointUrl, {
      method: "POST",
      headers: Object.assign({ "Content-Type": "application/json" }, csrfHeaders()),
      credentials: "same-origin",
      body: JSON.stringify({
        article_id: Number(articleId),
        lat: String(pickedCoords.lat),
        lon: String(pickedCoords.lon),
        title: title,
      }),
    })
      .then(function (r) {
        if (!r.ok) throw new Error("create failed");
        return r.json();
      })
      .then(function (data) {
        insertMapPointLink(data);
        closeMapModal();
      })
      .catch(function () {
        alert("Не удалось создать точку на карте.");
      });
  }

  if (mapBtn) {
    // mousedown раньше blur RTE: запоминаем курсор и не отдаём фокус кнопке.
    mapBtn.addEventListener("mousedown", function (e) {
      var captured = captureRteSelection() || lastRteSelection;
      if (captured) mapInsertTarget = captured;
      e.preventDefault();
    });
    mapBtn.addEventListener("click", openMapModal);
  }
  if (mapModal) {
    mapModal.querySelectorAll("[data-map-point-close]").forEach(function (btn) {
      btn.addEventListener("click", closeMapModal);
    });
    var saveBtn = mapModal.querySelector("[data-map-point-save]");
    if (saveBtn) saveBtn.addEventListener("click", saveMapPoint);
    mapModal.addEventListener("click", function (ev) {
      if (ev.target === mapModal) closeMapModal();
    });
  }
})();
