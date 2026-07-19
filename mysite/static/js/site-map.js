(function () {
  var root = document.querySelector("[data-map-root]");
  if (!root || typeof ymaps === "undefined") return;

  var points = [];
  try {
    points = JSON.parse(document.getElementById("map-points-data").textContent || "[]");
  } catch (e) {
    points = [];
  }

  var focusId = Number(root.getAttribute("data-focus-point") || "") || null;
  var SPB_CENTER = [59.9386, 30.3141];
  var DEFAULT_ZOOM = 11;
  var FOCUS_ZOOM = 15;

  ymaps.ready(function () {
    var map = new ymaps.Map(root, {
      center: SPB_CENTER,
      zoom: DEFAULT_ZOOM,
      controls: ["zoomControl", "geolocationControl", "typeSelector"],
    });

    var focusCoords = null;
    points.forEach(function (point) {
      var coords = [point.lat, point.lon];
      var placemark = new ymaps.Placemark(
        coords,
        {
          balloonContentHeader: point.title,
          balloonContentBody: point.article_title
            ? '<a href="' + point.article_url + '">' + point.article_title + "</a>"
            : "",
          hintContent: point.title,
        },
        { preset: "islands#brownDotIcon" }
      );
      if (point.article_url) {
        placemark.events.add("click", function () {
          window.location.href = point.article_url;
        });
      }
      map.geoObjects.add(placemark);
      if (focusId && point.id === focusId) {
        focusCoords = coords;
      }
    });

    if (focusCoords) {
      map.setCenter(focusCoords, FOCUS_ZOOM);
    } else if (points.length === 1) {
      map.setCenter([points[0].lat, points[0].lon], FOCUS_ZOOM);
    } else if (points.length > 1) {
      map.setBounds(map.geoObjects.getBounds(), { checkZoomRange: true, zoomMargin: 40 });
    }
  });
})();
