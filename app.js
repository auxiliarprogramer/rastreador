const lista = document.querySelector("#lista");
const resumen = document.querySelector("#resumen");
const aviso = document.querySelector("#aviso");

const moneda = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

const fecha = new Intl.DateTimeFormat("es-CO", {
  dateStyle: "medium",
  timeStyle: "short",
  hour12: false,
  timeZone: "America/Bogota",
});

function textoFecha(iso) {
  if (!iso) return "todavía no hay una revisión";
  const valor = new Date(iso);
  if (Number.isNaN(valor.getTime())) return "todavía no hay una revisión";
  return fecha.format(valor);
}

function pintar(estado) {
  const productos = Array.isArray(estado.productos) ? estado.productos : [];
  const disponibles = productos.filter((producto) => producto.disponible).length;
  const whatsapp = estado.whatsapp || {};

  const revision = `Última revisión: ${textoFecha(estado.ultimaRevision)}`;
  resumen.textContent = productos.length
    ? `${disponibles} de ${productos.length} con stock. ${revision}`
    : `Ningún producto publicado contiene «Calendario» en el nombre. ${revision}`;

  if (whatsapp.configurado) {
    aviso.hidden = true;
  } else {
    aviso.hidden = false;
    aviso.textContent = "El WhatsApp a +57 314 687 6883 todavía no está activado. Falta la clave en el repositorio. Los pasos están más abajo.";
  }

  if (!productos.length) {
    lista.innerHTML = '<p class="vacio">Cuando la tienda publique un producto cuyo nombre contenga «Calendario», va a aparecer aquí. Si tiene stock, el aviso sale al WhatsApp.</p>';
    return;
  }

  lista.replaceChildren(...productos.map(tarjeta));
}

function tarjeta(producto) {
  const articulo = document.createElement("article");
  articulo.className = "tarjeta";

  if (producto.imagen) {
    const imagen = document.createElement("img");
    imagen.src = producto.imagen;
    imagen.alt = "";
    articulo.append(imagen);
  } else {
    const vacio = document.createElement("div");
    vacio.className = "sin-foto";
    vacio.textContent = "Sin foto";
    articulo.append(vacio);
  }

  const cuerpo = document.createElement("div");
  const titulo = document.createElement("h2");
  titulo.textContent = producto.nombre || "Producto";

  const meta = document.createElement("p");
  meta.className = "meta";
  const partes = [];
  if (producto.referencia) partes.push(producto.referencia);
  if (producto.precio != null) partes.push(moneda.format(producto.precio));
  meta.textContent = partes.join(" · ");

  const estado = document.createElement("p");
  estado.className = producto.disponible ? "estado" : "estado agotado";
  estado.textContent = producto.disponible
    ? `Disponible · ${producto.stock} unidades`
    : "Agotado";

  cuerpo.append(titulo, meta, estado);

  if (producto.url) {
    const enlace = document.createElement("p");
    enlace.className = "meta";
    const a = document.createElement("a");
    a.href = producto.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = "Ver en la tienda";
    enlace.append(a);
    cuerpo.append(enlace);
  }

  articulo.append(cuerpo);
  return articulo;
}

async function cargar() {
  try {
    const respuesta = await fetch("estado.json?t=" + Date.now(), { cache: "no-store" });
    if (!respuesta.ok) throw new Error("HTTP " + respuesta.status);
    pintar(await respuesta.json());
  } catch (error) {
    resumen.textContent = "No se pudo leer el estado guardado.";
    lista.innerHTML = '<p class="vacio">Recarga la página en unos segundos. Si acabas de crear el repositorio, la primera revisión todavía no corre.</p>';
  }
}

cargar();
setInterval(cargar, 60000);
