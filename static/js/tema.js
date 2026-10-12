/*
 * Comportamiento del menú lateral en móvil y tablet vertical:
 * se cierra al pulsar Escape o al elegir un ítem. El fondo oscuro que aparece
 * al abrirlo lo gestiona AdminLTE con su propio #sidebar-overlay.
 */
(function () {
  "use strict";

  var cuerpo = document.body;

  function esMovil() {
    return window.innerWidth < 992;
  }

  function cerrarMenu() {
    cuerpo.classList.remove("sidebar-open");
    cuerpo.classList.add("sidebar-collapse");
  }

  document.addEventListener("keydown", function (evento) {
    if (evento.key === "Escape" && esMovil()) {
      cerrarMenu();
    }
  });

  var enlaces = document.querySelectorAll(".main-sidebar .nav-sidebar a.nav-link[href]");
  enlaces.forEach(function (enlace) {
    enlace.addEventListener("click", function () {
      if (esMovil()) {
        cerrarMenu();
      }
    });
  });
})();
