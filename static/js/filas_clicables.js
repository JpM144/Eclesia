/*
 * Filas clicables de las tablas de partidas: al pulsar cualquier celda (que
 * no sea un enlace o control) se abre la ficha de la fila. El enlace del ojo
 * sigue siendo el respaldo accesible con teclado y lector de pantalla.
 */
document.addEventListener("click", function (evento) {
  var fila = evento.target.closest("tr[data-href]");
  if (!fila) {
    return;
  }
  if (evento.target.closest("a, button, input, select, label, textarea")) {
    return;
  }
  window.location.href = fila.getAttribute("data-href");
});
