/* Encadenamiento de selects de ubicación (país -> departamento -> municipio).
 *
 * Uso: marca los selects con los atributos data-cascada-* dentro de un mismo
 * formulario (o de un contenedor con data-cascada-contenedor):
 *
 *   <select data-cascada-pais>...</select>
 *   <select data-cascada-departamento
 *           data-url="/ubicacion/api/departamentos/">...</select>
 *   <select data-cascada-municipio            (opcional)
 *           data-url="/ubicacion/api/municipios/">...</select>
 *
 * El script cargará las opciones por fetch al cambiar el select padre y, al
 * cargar la página, conservará el valor ya seleccionado (precarga al editar).
 */
(function () {
  "use strict";

  var TEXTO_VACIO = "---------";

  function llenarSelect(select, datos) {
    var valorPrevio = select.value;
    select.innerHTML = "";
    var vacio = document.createElement("option");
    vacio.value = "";
    vacio.textContent = TEXTO_VACIO;
    select.appendChild(vacio);
    datos.forEach(function (item) {
      var opcion = document.createElement("option");
      opcion.value = item.id;
      opcion.textContent = item.nombre;
      select.appendChild(opcion);
    });
    if (valorPrevio) {
      select.value = valorPrevio;
    }
  }

  function cargarOpciones(select, url, parametro, valor) {
    return fetch(url + "?" + parametro + "=" + encodeURIComponent(valor))
      .then(function (respuesta) {
        if (!respuesta.ok) {
          throw new Error("Respuesta " + respuesta.status);
        }
        return respuesta.json();
      })
      .then(function (datos) {
        llenarSelect(select, datos);
      })
      .catch(function () {
        llenarSelect(select, []);
      });
  }

  function inicializar(contenedor) {
    var pais = contenedor.querySelector("[data-cascada-pais]");
    var departamento = contenedor.querySelector("[data-cascada-departamento]");
    var municipio = contenedor.querySelector("[data-cascada-municipio]");
    if (!pais || !departamento) {
      return;
    }

    var urlDepartamentos =
      departamento.getAttribute("data-url") || "/ubicacion/api/departamentos/";
    var urlMunicipios = municipio
      ? municipio.getAttribute("data-url") || "/ubicacion/api/municipios/"
      : null;

    function cargarMunicipios() {
      if (!municipio) {
        return;
      }
      if (!departamento.value) {
        llenarSelect(municipio, []);
        return;
      }
      cargarOpciones(municipio, urlMunicipios, "departamento", departamento.value);
    }

    function cargarDepartamentos() {
      if (!pais.value) {
        llenarSelect(departamento, []);
        cargarMunicipios();
        return;
      }
      cargarOpciones(departamento, urlDepartamentos, "pais", pais.value).then(
        cargarMunicipios
      );
    }

    pais.addEventListener("change", cargarDepartamentos);
    departamento.addEventListener("change", cargarMunicipios);

    // Precarga inicial al editar: el país ya trae su valor seleccionado.
    if (pais.value) {
      cargarDepartamentos();
    }
  }

  function iniciar() {
    var paises = document.querySelectorAll("[data-cascada-pais]");
    Array.prototype.forEach.call(paises, function (pais) {
      var contenedor =
        pais.closest("[data-cascada-contenedor]") || pais.closest("form") || document;
      inicializar(contenedor);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
