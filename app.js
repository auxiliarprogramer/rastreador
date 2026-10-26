const lista = document.querySelector("#lista");
const resumen = document.querySelector("#resumen");
const ultima = document.querySelector("#ultima");
const siguiente = document.querySelector("#siguiente");

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
  if (!iso) return "Todavía no hay una búsqueda";
  const valor = new Date(iso);
  if (Number.isNaN(valor.getTime())) return "Todavía no hay una búsqueda";
  return fecha.format(valor);
}

const INICIO = new Date("2026-11-15T00:00:00-05:00");
const FIN = new Date("2026-12-16T00:00:00-05:00");

function proximaBusqueda(desde) {
  if (desde < INICIO) return INICIO;
  if (desde >= FIN) return null;
  const siguienteMomento = new Date(desde.getTime());
  siguienteMomento.setUTCSeconds(0, 0);
  const minutos = siguienteMomento.getUTCMinutes();
  const resto = minutos % 15;
  siguienteMomento.setUTCMinutes(minutos + (resto === 0 ? 15 : 15 - resto));
  return siguienteMomento;
}

function pintarHorario(iso) {
  if (iso) ultima.dataset.iso = iso;
  ultima.textContent = textoFecha(iso || ultima.dataset.iso);
  const proxima = proximaBusqueda(new Date());
  siguiente.textContent = proxima
    ? textoFecha(proxima.toISOString())
    : "La temporada de búsqueda ya terminó";
}

function pintar(estado) {
  const productos = Array.isArray(estado.productos) ? estado.productos : [];
  const disponibles = productos.filter((producto) => producto.disponible).length;

  resumen.textContent = productos.length
    ? `${disponibles} de ${productos.length} con stock.`
    : "Ningún producto publicado contiene «Calendario» en el nombre.";
  pintarHorario(estado.ultimaRevision);

  if (!productos.length) {
    lista.innerHTML = '<p class="vacio">Cuando la tienda publique un producto cuyo nombre contenga «Calendario», va a aparecer aquí. Si tiene stock, el aviso sale por Telegram.</p>';
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
setInterval(() => pintarHorario(ultima.dataset.iso || null), 30000);
