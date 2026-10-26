"""Consulta el catálogo de Trendy y avisa por WhatsApp si hay un Calendario disponible.

La clave se lee de la variable de entorno WHATSAPP_APIKEY (secreto de GitHub).
El número de destino es el que pidió el aviso. CallMeBot solo entrega el mensaje
al mismo WhatsApp que activó la clave.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TIENDA = "https://www.maquillajetrendyshop.com"
BUSQUEDA = TIENDA + "/api/catalog_system/pub/products/search"
CONSULTA = "Calendario"
DESTINO = (os.environ.get("WHATSAPP_PHONE") or "+573146876883").strip()
ESTADO_PATH = Path(__file__).with_name("estado.json")
PAGINA = 50
MAXIMO = 200
USER_AGENT = "RastreadorCalendario/1.0 (+https://github.com/)"


def ahora_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cargar_estado():
    if not ESTADO_PATH.exists():
        return {}
    try:
        return json.loads(ESTADO_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def guardar_estado(estado):
    ESTADO_PATH.write_text(
        json.dumps(estado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def obtener_json(url):
    solicitud = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(solicitud, timeout=30) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def buscar_productos():
    encontrados = []
    inicio = 0
    while inicio < MAXIMO:
        consulta = urllib.parse.urlencode(
            {"ft": CONSULTA, "_from": inicio, "_to": inicio + PAGINA - 1}
        )
        lote = obtener_json(BUSQUEDA + "?" + consulta)
        if not isinstance(lote, list) or not lote:
            break
        encontrados.extend(lote)
        if len(lote) < PAGINA:
            break
        inicio += PAGINA
    return encontrados


def resumir(producto):
    nombre = (producto.get("productName") or "").strip()
    if CONSULTA.casefold() not in nombre.casefold():
        return None

    stock = 0
    disponible = False
    precio = None
    imagen = None
    for item in producto.get("items") or []:
        if imagen is None:
            imagenes = item.get("images") or []
            if imagenes:
                imagen = imagenes[0].get("imageUrl")
        for vendedor in item.get("sellers") or []:
            oferta = vendedor.get("commertialOffer") or {}
            cantidad = int(oferta.get("AvailableQuantity") or 0)
            stock += cantidad
            if oferta.get("IsAvailable") or cantidad > 0:
                disponible = True
            if precio is None and oferta.get("Price") is not None:
                precio = oferta.get("Price")

    return {
        "id": str(producto.get("productId") or producto.get("linkText") or nombre),
        "nombre": nombre,
        "referencia": producto.get("productReference") or "",
        "url": producto.get("link") or "",
        "disponible": disponible,
        "stock": stock,
        "precio": precio,
        "imagen": imagen,
    }


def formato_precio(precio):
    if precio is None:
        return "precio no publicado"
    return "$" + f"{int(round(precio)):,}".replace(",", ".")


def mensaje_whatsapp(productos):
    lineas = ["*Ya hay Calendario en Trendy*", ""]
    for producto in productos:
        lineas.append(producto["nombre"])
        lineas.append(
            f"Stock: {producto['stock']} · {formato_precio(producto['precio'])}"
        )
        if producto["url"]:
            lineas.append(producto["url"])
        lineas.append("")
    return "\n".join(lineas).strip()


def enviar_whatsapp(texto, apikey):
    consulta = urllib.parse.urlencode(
        {"phone": DESTINO, "text": texto, "apikey": apikey}
    )
    solicitud = urllib.request.Request(
        "https://api.callmebot.com/whatsapp.php?" + consulta,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(solicitud, timeout=30) as respuesta:
            cuerpo = respuesta.read().decode("utf-8", errors="replace")
            codigo = respuesta.status
    except urllib.error.HTTPError as error:
        cuerpo = error.read().decode("utf-8", errors="replace")
        codigo = error.code

    plano = " ".join(cuerpo.split())
    exito = codigo == 200 and any(
        frase in plano.lower() for frase in ("queued", "sent", "success", "enviad")
    )
    return exito, f"HTTP {codigo}: {plano[:240]}"


def main():
    apikey = (os.environ.get("WHATSAPP_APIKEY") or "").strip()
    anterior = cargar_estado()
    avisos_previos = set(anterior.get("alertasEnviadas") or [])
    whatsapp_previo = anterior.get("whatsapp") or {}

    try:
        crudos = buscar_productos()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"No se pudo consultar la tienda: {error}", file=sys.stderr)
        return 1

    productos = []
    vistos = set()
    for crudo in crudos:
        resumen = resumir(crudo)
        if resumen is None or resumen["id"] in vistos:
            continue
        vistos.add(resumen["id"])
        productos.append(resumen)

    disponibles = {producto["id"] for producto in productos if producto["disponible"]}
    pendientes = [producto for producto in productos if producto["id"] in disponibles - avisos_previos]

    ultimo_envio = whatsapp_previo.get("ultimoEnvio")
    if not pendientes:
        resultado = "Sin novedades"
        enviados = avisos_previos & disponibles
    elif not apikey:
        resultado = "Hay stock, pero falta el secreto WHATSAPP_APIKEY. No se envió el WhatsApp."
        enviados = avisos_previos & disponibles
    else:
        ok, detalle = enviar_whatsapp(mensaje_whatsapp(pendientes), apikey)
        if ok:
            resultado = "Aviso enviado a " + DESTINO
            ultimo_envio = ahora_iso()
            enviados = (avisos_previos & disponibles) | {producto["id"] for producto in pendientes}
        else:
            resultado = "No se pudo enviar el WhatsApp. " + detalle
            enviados = avisos_previos & disponibles
        print(resultado)

    estado = {
        "consulta": CONSULTA,
        "tienda": TIENDA,
        "ultimaRevision": ahora_iso(),
        "productos": productos,
        "alertasEnviadas": sorted(enviados),
        "whatsapp": {
            "destino": DESTINO,
            "configurado": bool(apikey),
            "ultimoEnvio": ultimo_envio,
            "ultimoResultado": resultado,
        },
    }
    guardar_estado(estado)
    print(
        f"Revisión lista. Productos con «{CONSULTA}»: {len(productos)}. "
        f"Disponibles: {len(disponibles)}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
