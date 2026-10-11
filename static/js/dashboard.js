/*
 * Gráfico de "Sacramentos por Mes" del dashboard.
 *
 * Los datos llegan desde la plantilla con {{ datos_grafico|json_script }} y
 * nunca se concatenan aquí. Chart.js se carga antes, desde cdnjs.
 */
(function () {
  "use strict";

  var lienzo = document.getElementById("grafico-sacramentos");
  var origen = document.getElementById("datos-grafico");
  if (!lienzo || !origen || typeof Chart === "undefined") {
    return;
  }

  var datos = JSON.parse(origen.textContent);

  var COLORES = {
    BAUTISMO: { borde: "#1d4ed8", fondo: "rgba(37, 99, 235, 0.65)" },
    PRIMERA_COMUNION: { borde: "#15803d", fondo: "rgba(22, 163, 74, 0.65)" },
    CONFIRMACION: { borde: "#6d28d9", fondo: "rgba(124, 58, 237, 0.65)" },
    MATRIMONIO: { borde: "#be123c", fondo: "rgba(225, 29, 72, 0.65)" }
  };

  var ETIQUETAS = {
    BAUTISMO: "Bautismos",
    PRIMERA_COMUNION: "Primera Comunión",
    CONFIRMACION: "Confirmación",
    MATRIMONIO: "Matrimonios"
  };

  var conjuntos = Object.keys(datos.series).map(function (tipo) {
    var color = COLORES[tipo] || { borde: "#6b7280", fondo: "rgba(107, 114, 128, 0.6)" };
    return {
      label: ETIQUETAS[tipo] || tipo,
      tipo: tipo,
      data: datos.series[tipo],
      backgroundColor: color.fondo,
      borderColor: color.borde,
      borderWidth: 1.5,
      borderRadius: 4,
      maxBarThickness: 26
    };
  });

  var grafico = new Chart(lienzo, {
    type: "bar",
    data: { labels: datos.etiquetas, datasets: conjuntos },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
        tooltip: { mode: "index", intersect: false }
      },
      scales: {
        x: { grid: { display: false } },
        y: {
          beginAtZero: true,
          ticks: { precision: 0 },
          grid: { color: "rgba(0, 0, 0, 0.05)" }
        }
      }
    }
  });

  var filtro = document.getElementById("filtro-series");
  if (filtro) {
    filtro.addEventListener("change", function () {
      var seleccion = filtro.value;
      grafico.data.datasets.forEach(function (conjunto, indice) {
        var visible = seleccion === "TODOS" || seleccion === conjunto.tipo;
        grafico.setDatasetVisibility(indice, visible);
      });
      grafico.update();
    });
  }
})();
