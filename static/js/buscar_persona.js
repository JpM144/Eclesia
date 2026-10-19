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
 * Comportamiento:
 * - Al pulsar Buscar (o Intro en el número) se consulta
 *   /personas/api/persona/. Si la persona ya existe en cualquier rol se
 *   rellenan sus datos, los campos de identidad (nombres y apellidos) quedan
 *   de solo lectura y aparece un enlace a su ficha en Consultar personas.
 * - Si el documento no existe se avisa y los campos quedan editables: los
 *   datos nuevos se guardan junto con la partida.
 * - Si el usuario cambia el número después de buscar, se desbloquean los
 *   campos y se limpian los datos rellenados.
 * - Si el bautizado ya tiene bautismo, o el sexo de un rol no corresponde
 *   (padre varón, madre mujer…), el aviso aparece al buscar, no solo al
 *   guardar. Si el bloque lleva data-mostrar-bautismo (el formulario de
 *   Primera Comunión), el bautismo enlazado se muestra como enlace verde a la
 *   partida y su pk se guarda en la casilla oculta data-bautismo-id.
 * - El comportamiento se configura solo con atributos data-: data-rol del
 *   bloque, data-documento-tipo/numero del par de documento y
 *   data-campo-persona de cada campo rellenable (nombres, apellidos,
 *   fecha_nacimiento, municipio, sexo, telefono, padre, madrina).
 * - Nunca se usa innerHTML con datos de personas: todo se inserta con
 *   textContent o con la propiedad value.
 */
(function () {
  "use strict";

  var URL = "/personas/api/persona/";
  var CAMPOS_RELLENABLES = [
    "nombres",
    "apellidos",
    "fecha_nacimiento",
    "municipio",
    "sexo",
    "telefono",
    "padre",
    "madre",
  ];
  var SOLO_DIGITOS = { CC: true, TI: true, RC: true };
  var ALFANUMERICO = { CE: true, PA: true };
  var RE_DIGITOS = /^\d{5,15}$/;
  var RE_ALFANUMERICO = /^[A-Za-z0-9]{5,20}$/;
  var RE_SEPARADORES = /[.\s-]/g;

  var MENSAJES = {
    numeroVacio: "Escribe el número del documento.",
    numeroInvalido: "Revisa el número del documento.",
    noEncontrada:
      "No está registrada. Llena sus datos y se guardará con la partida.",
    varios: "Hay varias personas con ese número; elige el tipo de documento.",
    error: "No se pudo buscar la persona. Intenta de nuevo.",
    registrada: "Persona registrada.",
    corregir: "Para corregir sus datos usa Consultar personas",
    bautismo: "Este fiel ya tiene un bautismo registrado",
    padreMujer: "El padre debe ser varón.",
    madreVaron: "La madre debe ser mujer.",
    padrinoMujer: "El padrino debe ser varón.",
    madrinaVaron: "La madrina debe ser mujer.",
  };
  var AVISOS_SEXO = {
    padre: { sexo: "M", mensaje: MENSAJES.padreMujer },
    madre: { sexo: "H", mensaje: MENSAJES.madreVaron },
    padrino: { sexo: "M", mensaje: MENSAJES.padrinoMujer },
    madrina: { sexo: "H", mensaje: MENSAJES.madrinaVaron },
  };

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

  function campoDe(bloque, nombre) {
    return bloque.querySelector('[data-campo-persona="' + nombre + '"]');
  }

  function setCampo(bloque, nombre, valor) {
    var campo = campoDe(bloque, nombre);
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

  function setSoloLectura(bloque, soloLectura) {
    ["nombres", "apellidos"].forEach(function (nombre) {
      var campo = campoDe(bloque, nombre);
      if (!campo) {
        return;
      }
      if (soloLectura) {
        campo.setAttribute("readonly", "readonly");
      } else {
        campo.removeAttribute("readonly");
      }
    });
  }

  function limpiarRelleno(bloque) {
    (bloque.personaRellenada || []).forEach(function (nombre) {
      setCampo(bloque, nombre, "");
    });
    bloque.personaRellenada = [];
  }

  function limpiarNota(bloque) {
    var nota = bloque.querySelector("[data-nota-persona]");
    if (nota) {
      nota.textContent = "";
    }
  }

  function limpiarBautismo(bloque) {
    var oculto = bloque.querySelector("[data-bautismo-id]");
    if (oculto) {
      oculto.value = "";
    }
  }

  function fechaCorta(iso) {
    var partes = (iso || "").split("-");
    if (partes.length !== 3) {
      return iso || "";
    }
    return partes[2] + "/" + partes[1] + "/" + partes[0];
  }

  function agregarTexto(nota, texto, clase) {
    if (!texto) {
      return;
    }
    var span = document.createElement("span");
    span.textContent = texto;
    if (clase) {
      span.className = clase;
    }
    nota.appendChild(span);
  }

  function mostrarNota(bloque, avisos, urlEdicion) {
    var nota = bloque.querySelector("[data-nota-persona]");
    if (!nota) {
      return;
    }
    nota.textContent = "";
    avisos.forEach(function (aviso) {
      agregarTexto(nota, aviso.texto, aviso.clase);
      if (aviso.url) {
        nota.appendChild(document.createTextNode(" "));
        var enlaceAviso = document.createElement("a");
        enlaceAviso.href = aviso.url;
        enlaceAviso.target = "_blank";
        enlaceAviso.rel = "noopener";
        enlaceAviso.textContent = aviso.enlaceTexto || "Ver bautismo";
        nota.appendChild(enlaceAviso);
      }
    });
    if (urlEdicion) {
      nota.appendChild(document.createTextNode(" "));
      var enlace = document.createElement("a");
      enlace.href = urlEdicion;
      enlace.target = "_blank";
      enlace.rel = "noopener";
      enlace.textContent = MENSAJES.corregir;
      nota.appendChild(enlace);
    }
  }

  function validarNumero(tipo, valor) {
    var limpio = valor.replace(RE_SEPARADORES, "");
    if (!limpio) {
      return MENSAJES.numeroVacio;
    }
    if (tipo && SOLO_DIGITOS[tipo]) {
      return RE_DIGITOS.test(limpio) ? "" : MENSAJES.numeroInvalido;
    }
    if (tipo && ALFANUMERICO[tipo]) {
      return RE_ALFANUMERICO.test(limpio) ? "" : MENSAJES.numeroInvalido;
    }
    if (RE_DIGITOS.test(limpio) || RE_ALFANUMERICO.test(limpio)) {
      return "";
    }
    return MENSAJES.numeroInvalido;
  }

  function rellenar(bloque, datos) {
    bloque.personaRellenada = [];
    CAMPOS_RELLENABLES.forEach(function (nombre) {
      var valor = datos[nombre];
      if (valor === null || valor === undefined || valor === "") {
        // padre y madre llegan como bautismo_padre/bautismo_madre
        valor = datos["bautismo_" + nombre];
      }
      if (valor === null || valor === undefined || valor === "") {
        return;
      }
      setCampo(bloque, nombre, valor);
      bloque.personaRellenada.push(nombre);
    });
  }

  function avisosDeEncontrado(bloque, datos) {
    var rol = bloque.getAttribute("data-rol") || "";
    var avisos = [
      { texto: MENSAJES.registrada + " " },
    ];
    if (datos.bautismo_activo) {
      var oculto = bloque.querySelector("[data-bautismo-id]");
      if (oculto) {
        oculto.value = datos.bautismo_id || "";
      }
      if (bloque.hasAttribute("data-mostrar-bautismo")) {
        avisos.push({
          texto:
            "Bautizado en " +
            (datos.bautismo_parroquia ? datos.bautismo_parroquia + " · " : "") +
            (datos.bautismo_referencia || "") +
            (datos.bautismo_fecha ? " · " + fechaCorta(datos.bautismo_fecha) : "") +
            ". ",
          clase: "text-success",
          url: datos.bautismo_url,
          enlaceTexto: "Ver partida de bautismo",
        });
      } else {
        avisos.push({
          texto:
            " " +
            MENSAJES.bautismo +
            (datos.bautismo_referencia ? ": " + datos.bautismo_referencia : "") +
            ".",
          clase: "text-danger",
        });
      }
    }
    var avisoSexo = AVISOS_SEXO[rol];
    if (avisoSexo && datos.sexo_fiel === avisoSexo.sexo) {
      avisos.push({ texto: " " + avisoSexo.mensaje, clase: "text-danger" });
    }
    return avisos;
  }

  function manejarRespuesta(bloque, estado, datos) {
    if (datos && datos.varios) {
      mostrarNota(bloque, [{ texto: datos.mensaje || MENSAJES.varios }]);
      return;
    }
    if (estado === 404 || (datos && datos.encontrado === false)) {
      bloque.personaEncontrada = false;
      setSoloLectura(bloque, false);
      limpiarBautismo(bloque);
      mostrarNota(bloque, [{ texto: MENSAJES.noEncontrada }]);
      return;
    }
    if (!datos || !datos.encontrado) {
      mostrarNota(bloque, [
        { texto: (datos && datos.error) || MENSAJES.error, clase: "text-danger" },
      ]);
      return;
    }
    var tipo = bloque.querySelector("[data-documento-tipo]");
    if (tipo && !tipo.value && datos.tipo_documento) {
      tipo.value = datos.tipo_documento;
    }
    rellenar(bloque, datos);
    bloque.personaEncontrada = true;
    setSoloLectura(bloque, true);
    mostrarNota(bloque, avisosDeEncontrado(bloque, datos), datos.editar_url);
  }

  function buscar(bloque) {
    var tipo = bloque.querySelector("[data-documento-tipo]");
    var numero = bloque.querySelector("[data-documento-numero]");
    var boton = bloque.querySelector("[data-buscar-persona]");
    if (!numero || !boton) {
      return;
    }
    var valor = numero.value.trim();
    var errorCliente = validarNumero(tipo ? tipo.value : "", valor);
    if (errorCliente) {
      mostrarNota(bloque, [{ texto: errorCliente, clase: "text-danger" }]);
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
        return respuesta.json().then(function (datos) {
          return { estado: respuesta.status, datos: datos };
        });
      })
      .then(function (resultado) {
        botonConSpinner(boton, false);
        manejarRespuesta(bloque, resultado.estado, resultado.datos);
      })
      .catch(function () {
        botonConSpinner(boton, false);
        mostrarNota(bloque, [{ texto: MENSAJES.error, clase: "text-danger" }]);
      });
  }

  function numeroCambio(bloque) {
    if (!bloque.personaEncontrada) {
      return;
    }
    bloque.personaEncontrada = false;
    limpiarRelleno(bloque);
    limpiarBautismo(bloque);
    setSoloLectura(bloque, false);
    limpiarNota(bloque);
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
      var numero = bloque.querySelector("[data-documento-numero]");
      if (numero) {
        numero.addEventListener("keydown", function (evento) {
          if (evento.key === "Enter") {
            evento.preventDefault();
            buscar(bloque);
          }
        });
        numero.addEventListener("input", function () {
          numeroCambio(bloque);
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
