(function () {
  function csrfToken() {
    var input = document.querySelector("[name=csrfmiddlewaretoken]");
    if (input && input.value) return input.value;
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function ruViewsWord(count) {
    var n = Math.abs(parseInt(count, 10) || 0) % 100;
    if (n >= 11 && n <= 14) return "просмотров";
    n = n % 10;
    if (n === 1) return "просмотр";
    if (n >= 2 && n <= 4) return "просмотра";
    return "просмотров";
  }

  function updateCount(root, count) {
    var countEl = root.querySelector("[data-view-count]");
    if (countEl) countEl.textContent = String(count);
    var labelEl = root.querySelector("[data-view-label]");
    if (labelEl) labelEl.textContent = ruViewsWord(count);
  }

  function sendView(el) {
    var url = el.getAttribute("data-view-url");
    if (!url) return;
    fetch(url, {
      method: "POST",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfToken(),
      },
      credentials: "same-origin",
    })
      .then(function (response) {
        if (!response.ok) throw new Error("view failed");
        return response.json();
      })
      .then(function (data) {
        if (typeof data.count === "number") {
          updateCount(el, data.count);
        }
      })
      .catch(function () {});
  }

  var targets = document.querySelectorAll("[data-view-track][data-view-url]");
  if (!targets.length) return;

  if (!("IntersectionObserver" in window)) {
    Array.prototype.forEach.call(targets, sendView);
    return;
  }

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        observer.unobserve(entry.target);
        sendView(entry.target);
      });
    },
    { threshold: 0.4 }
  );

  Array.prototype.forEach.call(targets, function (el) {
    observer.observe(el);
  });
})();
