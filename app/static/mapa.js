/* Mapa de la ronda con Leaflet (HU-007 c2).
   Lee los datos que el servidor dejó en <script id="datos-mapa"> (ya convertidos
   de Gauss-Krüger a latitud y longitud con pyproj) y dibuja la base, los activos
   coloreados por criticidad, su número de orden y el recorrido. */
(function () {
  var contenedor = document.getElementById("mapa");
  var fuente = document.getElementById("datos-mapa");
  if (!contenedor || !fuente || typeof L === "undefined") return;

  var datos = JSON.parse(fuente.textContent);
  var colores = { alta: "#C0442E", media: "#C8890E", baja: "#5A7D5A", sin: "#8A8984" };

  var mapa = L.map(contenedor, { scrollWheelZoom: false });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: '&copy; colaboradores de <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(mapa);

  var limites = [];

  // Base de origen
  var base = [datos.origen.lat, datos.origen.lon];
  L.circleMarker(base, { radius: 8, color: "#2F4E6F", fillColor: "#2F4E6F", fillOpacity: 1 })
    .addTo(mapa).bindTooltip(datos.origen.nombre, { permanent: true, direction: "right" });
  limites.push(base);

  // Recorrido (línea punteada desde la base)
  if (datos.ruta.length > 0) {
    L.polyline([base].concat(datos.ruta), { color: "#2F4E6F", weight: 2, dashArray: "7 5" }).addTo(mapa);
  }

  // Activos
  datos.puntos.forEach(function (punto) {
    var posicion = [punto.lat, punto.lon];
    var color = colores[punto.categoria] || colores.sin;
    var etiqueta = punto.orden ? String(punto.orden) : "—";
    var icono = L.divIcon({
      className: "marcador-activo",
      html: '<span style="background:' + (punto.orden ? color : "#FFFFFF") +
            ';border-color:' + color + ';color:' + (punto.orden ? "#FFFFFF" : color) + '">' +
            etiqueta + "</span>",
      iconSize: [26, 26],
      iconAnchor: [13, 13]
    });
    L.marker(posicion, { icon: icono }).addTo(mapa)
      .bindTooltip(punto.codigo + (punto.excluido ? " (fuera por tiempo)" : ""), { direction: "top" });
    limites.push(posicion);
  });

  mapa.fitBounds(limites, { padding: [30, 30] });
})();
