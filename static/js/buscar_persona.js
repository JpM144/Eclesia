/* Búsqueda de personas por documento dentro de un formulario de sacramento.
 *
 * Cada bloque de persona se marca así:
 *
 *   <div class="bloque-persona" data-rol="fiel">
 *     <select data-documento-tipo>...</select>
 *     <input data-documento-numero>
 *     <button type="button" data-buscar-persona>...</button>
 *     <input data-campo-persona="nombres">
 *     ...
 *     <div data-nota-persona></div>
 *   </div>
 *
 * Al pulsar el botón se consulta /personas/api/persona/ y, si la persona ya
 * existe, se rellenan sus datos. Nunca se usa innerHTML con datos de personas:
 * todo se inserta con textContent o con la propiedad value.
 */
(function () {
  "use strict";

  var URL = "/personas/api/persona/";

  function botonConSpinner(boton, activo) {
    if (activo) {
      if (!boton.querySelector(".fa-spinner")) {
        var spinner = document.createElement("i");
        spinner.className = "fas fa-spinner fa-spin";
        spinner.setAttribute("aria-hidden", "true");
        boton.appendChild(document.createTextNode(" "));
        boton.appendChild(spinner);
      }
      boton.disabled = true;
      return;
    }
    boton.disabled = false;
    var icono = boton.querySelector(".fa-spinner");
    if (icono) {
      icono.remove();
    }
  }

  function setCampo(bloque, nombre, valor) {
    var campo = bloque.querySelector('[data-campo-persona="' + nombre + '"]');
    if (!campo) {
      return;
    }
    campo.value = valor === null || valor === undefined ? "" : valor;
    if (campo.tagName === "SELECT") {
      var evento = document.createEvent("HTMLEvents");
      evento.initEvent("change", true, false);
      campo.dispatchEvent(evento);
    }
  }

  function limpiarNota(bloque) {
    var nota = bloque.querySelector("[data-nota-persona]");
    if (nota) {
      nota.textContent = "";
    }
  }

  function mostrarNota(bloque, texto, alCambiar) {
    var nota = bloque.querySelector("[data-nota-persona]");
    if (!nota) {
      return;
    }
    nota.textContent = texto + " ";
    var enlace = document.createElement("a");
    enlace.href = "#";
    enlace.className = "enlace-cambiar-persona";
    enlace.textContent = "cambiar";
    enlace.addEventListener("click", function (evento) {
      evento.preventDefault();
      limpiarNota(bloque);
      var numero = bloque.querySelector("[data-documento-numero]");
      if (numero) {
        numero.value = "";
        numero.focus();
      }
      if (typeof alCambiar === "function") {
        alCambiar();
      }
    });
    nota.appendChild(enlace);
  }

  function buscar(bloque) {
    var tipo = bloque.querySelector("[data-documento-tipo]");
    var numero = bloque.querySelector("[data-documento-numero]");
    var boton = bloque.querySelector("[data-buscar-persona]");
    if (!numero || !boton) {
      return;
    }
    var valor = numero.value.trim();
    if (!valor) {
      return;
    }
    var rol = bloque.getAttribute("data-rol") || "";
    var url =
      URL +
      "?rol=" +
      encodeURIComponent(rol) +
      "&tipo=" +
      encodeURIComponent(tipo ? tipo.value : "") +
      "&numero=" +
      encodeURIComponent(valor);

    botonConSpinner(boton, true);
    fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (respuesta) {
        if (respuesta.status === 404) {
          return null;
        }
        if (!respuesta.ok) {
          throw new Error("Respuesta " + respuesta.status);
        }
        return respuesta.json();
      })
      .then(function (datos) {
        botonConSpinner(boton, false);
        if (!datos || !datos.encontrado) {
          limpiarNota(bloque);
          return;
        }
        setCampo(bloque, "nombres", datos.nombres);
        setCampo(bloque, "apellidos", datos.apellidos);
        setCampo(bloque, "fecha_nacimiento", datos.fecha_nacimiento);
        setCampo(bloque, "municipio", datos.municipio);
        setCampo(bloque, "sexo", datos.sexo);
        mostrarNota(bloque, "Ya registrado: se usarán sus datos.", function () {
          limpiarNota(bloque);
        });
      })
      .catch(function () {
        botonConSpinner(boton, false);
      });
  }

  function iniciar() {
    var botones = document.querySelectorAll("[data-buscar-persona]");
    Array.prototype.forEach.call(botones, function (boton) {
      var bloque = boton.closest(".bloque-persona");
      if (!bloque) {
        return;
      }
      boton.addEventListener("click", function () {
        buscar(bloque);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
