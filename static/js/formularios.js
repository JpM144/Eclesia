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

/*
 * Restringe lo que se escribe en los campos de personas:
 *
 *   data-solo-letras    no admite dígitos.
 *   data-solo-numeros   no admite letras (inputmode="numeric").
 *
 * Los campos con data-documento-numero dejan letras solo cuando el tipo de
 * documento elegido es CE o PA. Si se descarta un carácter se muestra un aviso
 * breve bajo el campo (siempre con textContent, nunca con innerHTML).
 */
(function () {
  "use strict";

  var TIPOS_CON_LETRAS = ["CE", "PA"];
  var AVISO_LETRAS = "Este campo solo admite letras";
  var AVISO_NUMEROS = "Este campo solo admite números";

  function avisoDe(campo) {
    var contenedor = campo.closest(".form-group") || campo.parentNode;
    var aviso = null;
    if (contenedor) {
      aviso = contenedor.querySelector("[data-aviso-caracter]");
      if (!aviso) {
        aviso = document.createElement("div");
        aviso.className = "text-danger small";
        aviso.setAttribute("data-aviso-caracter", "");
        contenedor.appendChild(aviso);
      }
    }
    return aviso;
  }

  function mostrarAviso(campo, texto) {
    var aviso = avisoDe(campo);
    if (aviso) {
      aviso.textContent = texto;
    }
  }

  function limpiarAviso(campo) {
    var contenedor = campo.closest(".form-group") || campo.parentNode;
    if (!contenedor) {
      return;
    }
    var aviso = contenedor.querySelector("[data-aviso-caracter]");
    if (aviso) {
      aviso.textContent = "";
    }
  }

  function tipoDocumento(campo) {
    var contenedor =
      campo.closest(".bloque-persona") || campo.closest("form") || campo.parentNode;
    if (!contenedor) {
      return "";
    }
    var select = contenedor.querySelector("[data-documento-tipo]");
    return select ? select.value : "";
  }

  function filtroDe(campo) {
    if (campo.hasAttribute("data-solo-letras")) {
      return { patron: /[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ'.\- ]/g, aviso: AVISO_LETRAS };
    }
    if (campo.hasAttribute("data-solo-numeros")) {
      if (campo.hasAttribute("data-documento-numero")) {
        var tipo = tipoDocumento(campo);
        if (TIPOS_CON_LETRAS.indexOf(tipo) !== -1) {
          return { patron: /[^A-Za-z0-9]/g, aviso: "El documento solo admite letras y números" };
        }
      }
      return { patron: /[^0-9]/g, aviso: AVISO_NUMEROS };
    }
    return null;
  }

  function limpiarCampo(campo) {
    var filtro = filtroDe(campo);
    if (!filtro) {
      limpiarAviso(campo);
      return;
    }
    var original = campo.value;
    var limpio = original.replace(filtro.patron, "");
    if (limpio !== original) {
      var posicion = campo.selectionStart;
      campo.value = limpio;
      if (typeof posicion === "number") {
        var nueva = Math.max(0, posicion - (original.length - limpio.length));
        try {
          campo.setSelectionRange(nueva, nueva);
        } catch (error) {
          /* campos sin selección (p. ej. type number) */
        }
      }
      mostrarAviso(campo, filtro.aviso);
    } else {
      limpiarAviso(campo);
    }
  }

  function iniciar() {
    var campos = document.querySelectorAll(
      "[data-solo-letras], [data-solo-numeros]"
    );
    Array.prototype.forEach.call(campos, function (campo) {
      campo.addEventListener("input", function () {
        limpiarCampo(campo);
      });
      campo.addEventListener("paste", function () {
        window.setTimeout(function () {
          limpiarCampo(campo);
        }, 0);
      });
      var contenedor = campo.closest(".bloque-persona") || campo.closest("form");
      var select = contenedor ? contenedor.querySelector("[data-documento-tipo]") : null;
      if (select) {
        select.addEventListener("change", function () {
          limpiarCampo(campo);
        });
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
