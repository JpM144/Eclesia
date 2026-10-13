/*
 * Gráfico de "Sacramentos por Mes" del dashboard.
 *
 * Los datos llegan desde la plantilla con {{ datos_grafico|json_script }} y
 * nunca se concatenan aquí. Chart.js se carga antes, desde cdnjs.
 *
 * El selector de periodo ("Último año", "Últimos 6 meses", "Este año") filtra
 * en el navegador los 12 meses que ya entrega el servidor; la leyenda permite
 * ocultar o mostrar series (comportamiento propio de Chart.js).
 */
(function () {
  "use strict";

  var lienzo = document.getElementById("grafico-sacramentos");
  var origen = document.getElementById("datos-grafico");
  if (!lienzo || !origen || typeof Chart === "undefined") {
    return;
  }

  var datos = JSON.parse(origen.textContent);

  function quitarEsqueleto() {
    var esqueleto = document.querySelector(".esqueleto-grafico");
    if (esqueleto && esqueleto.parentNode) {
      esqueleto.parentNode.removeChild(esqueleto);
    }
  }

  var COLORES = {
    BAUTISMO: { borde: "#4A78B5", fondo: "rgba(74, 120, 181, 0.7)" },
    PRIMERA_COMUNION: { borde: "#4E8A6E", fondo: "rgba(78, 138, 110, 0.7)" },
    CONFIRMACION: { borde: "#7650B0", fondo: "rgba(118, 80, 176, 0.7)" },
    MATRIMONIO: { borde: "#D04A5C", fondo: "rgba(208, 74, 92, 0.7)" }
  };

  var ETIQUETAS = {
    BAUTISMO: "Bautismos",
    PRIMERA_COMUNION: "Primera Comunión",
    CONFIRMACION: "Confirmación",
    MATRIMONIO: "Matrimonios"
  };

  var conjuntos = Object.keys(datos.series).map(function (tipo) {
    var color = COLORES[tipo] || { borde: "#64748B", fondo: "rgba(100, 116, 139, 0.6)" };
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

  var todoEnCero = conjuntos.every(function (conjunto) {
    return conjunto.data.every(function (valor) {
      return !valor;
    });
  });

  var grafico = new Chart(lienzo, {
    type: "bar",
    data: { labels: datos.etiquetas.slice(), datasets: conjuntos },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { onComplete: quitarEsqueleto },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
        tooltip: { mode: "index", intersect: false }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { autoSkip: true, maxRotation: 0, minRotation: 0 }
        },
        y: {
          beginAtZero: true,
          ticks: { precision: 0 },
          suggestedMax: todoEnCero ? 10 : undefined,
          grid: { color: "rgba(15, 23, 42, 0.06)" }
        }
      }
    }
  });

  function todosLosIndices() {
    return datos.etiquetas.map(function (_, indice) {
      return indice;
    });
  }

  function indicesPeriodo(periodo) {
    var total = datos.etiquetas.length;
    if (periodo === "seis") {
      return todosLosIndices().slice(Math.max(0, total - 6));
    }
    if (periodo === "este") {
      var ultima = datos.etiquetas[total - 1] || "";
      var coincidencia = ultima.match(/(\d{4})\s*$/);
      if (!coincidencia) {
        return todosLosIndices();
      }
      var anio = coincidencia[1];
      return todosLosIndices().filter(function (indice) {
        return datos.etiquetas[indice].indexOf(anio) !== -1;
      });
    }
    return todosLosIndices();
  }

  function aplicarPeriodo(periodo) {
    var indices = indicesPeriodo(periodo);
    grafico.data.labels = indices.map(function (indice) {
      return datos.etiquetas[indice];
    });
    conjuntos.forEach(function (conjunto, posicion) {
      grafico.data.datasets[posicion].data = indices.map(function (indice) {
        return conjunto.data[indice];
      });
    });
    grafico.update();
  }

  var selector = document.getElementById("periodo-grafico");
  if (selector) {
    selector.addEventListener("change", function () {
      aplicarPeriodo(selector.value);
    });
  }
})();
