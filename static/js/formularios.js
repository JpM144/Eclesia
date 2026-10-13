/*
 * Evita el doble envío de formularios.
 *
 * Los formularios que quieren protegerse llevan el atributo
 * data-evitar-doble-envio (crud/formulario.html y crud/confirmar_eliminar.html
 * lo aplican por defecto; el registro de usuarios lo añade explícitamente).
 *
 * Al enviar un formulario válido, deshabilita sus botones de envío y muestra un
 * spinner con el texto "Guardando…". Si el navegador marca errores de
 * validación, no se toca nada (la validación del navegador tiene prioridad). Si
 * el usuario vuelve con el botón atrás (pageshow con persisted), se restaura el
 * estado original de los botones.
 */
(function () {
  "use strict";

  function esDeEnvio(elemento) {
    if (elemento.tagName === "BUTTON") {
      var tipo = elemento.getAttribute("type");
      return tipo === null || tipo === "submit";
    }
    return elemento.tagName === "INPUT" && elemento.getAttribute("type") === "submit";
  }

  function deshabilitar(boton) {
    var fragmento = document.createDocumentFragment();
    var spinner = document.createElement("i");
    spinner.className = "fas fa-spinner fa-spin";
    spinner.setAttribute("aria-hidden", "true");
    fragmento.appendChild(spinner);
    fragmento.appendChild(document.createTextNode(" Guardando…"));

    var originales = [];
    while (boton.firstChild) {
      originales.push(boton.removeChild(boton.firstChild));
    }
    boton.__nodosOriginales = originales;
    boton.appendChild(fragmento);
    boton.disabled = true;
    boton.setAttribute("aria-busy", "true");
  }

  function reactivar(boton) {
    if (!boton.__nodosOriginales) {
      return;
    }
    while (boton.firstChild) {
      boton.removeChild(boton.firstChild);
    }
    boton.__nodosOriginales.forEach(function (nodo) {
      boton.appendChild(nodo);
    });
    boton.__nodosOriginales = null;
    boton.disabled = false;
    boton.removeAttribute("aria-busy");
  }

  function botonesDeEnvio(form) {
    return Array.prototype.filter.call(
      form.querySelectorAll("button, input"),
      esDeEnvio
    );
  }

  function preparar(form) {
    form.addEventListener("submit", function (evento) {
      if (evento.defaultPrevented) {
        return;
      }
      if (typeof form.checkValidity === "function" && !form.checkValidity()) {
        return;
      }
      botonesDeEnvio(form).forEach(function (boton) {
        if (!boton.disabled) {
          deshabilitar(boton);
        }
      });
    });
  }

  function reactivarTodo(raiz) {
    var formularios = (raiz || document).querySelectorAll("[data-evitar-doble-envio]");
    Array.prototype.forEach.call(formularios, function (form) {
      botonesDeEnvio(form).forEach(reactivar);
    });
  }

  document.querySelectorAll("[data-evitar-doble-envio]").forEach(preparar);

  window.addEventListener("pageshow", function (evento) {
    if (evento.persisted) {
      reactivarTodo(document);
    }
  });
})();
