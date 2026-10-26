"""Consulta el catálogo de Trendy y avisa por Telegram si hay un Calendario disponible.

El token y el chat se leen de TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID.
No se guardan en el repositorio.
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
BOT = "@RastTrendyBot"
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


def mensaje_telegram(productos):
    lineas = ["Ya hay Calendario en Trendy", ""]
    for producto in productos:
        lineas.append(producto["nombre"])
        lineas.append(
            f"Stock: {producto['stock']} · {formato_precio(producto['precio'])}"
        )
        if producto["url"]:
            lineas.append(producto["url"])
        lineas.append("")
    return "\n".join(lineas).strip()


def enviar_telegram(texto, token, chat_id):
    cuerpo = json.dumps({"chat_id": chat_id, "text": texto}).encode("utf-8")
    solicitud = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=cuerpo,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(solicitud, timeout=30) as respuesta:
            data = json.loads(respuesta.read().decode("utf-8"))
            codigo = respuesta.status
    except urllib.error.HTTPError as error:
        detalle = error.read().decode("utf-8", errors="replace")
        return False, f"HTTP {error.code}: {' '.join(detalle.split())[:240]}"

    if codigo == 200 and data.get("ok"):
        return True, "Mensaje entregado a Telegram"
    descripcion = data.get("description") or "respuesta inesperada"
    return False, f"HTTP {codigo}: {descripcion}"


def main():
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    anterior = cargar_estado()
    avisos_previos = set(anterior.get("alertasEnviadas") or [])
    aviso_previo = anterior.get("telegram") or anterior.get("whatsapp") or {}

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

    ultimo_envio = aviso_previo.get("ultimoEnvio")
    if not pendientes:
        resultado = "Sin novedades"
        enviados = avisos_previos & disponibles
    elif not token or not chat_id:
        resultado = "Hay stock, pero faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID. No se envió el aviso."
        enviados = avisos_previos & disponibles
    else:
        ok, detalle = enviar_telegram(mensaje_telegram(pendientes), token, chat_id)
        if ok:
            resultado = "Aviso enviado a " + BOT
            ultimo_envio = ahora_iso()
            enviados = (avisos_previos & disponibles) | {producto["id"] for producto in pendientes}
        else:
            resultado = "No se pudo enviar el Telegram. " + detalle
            enviados = avisos_previos & disponibles
        print(resultado)

    estado = {
        "consulta": CONSULTA,
        "tienda": TIENDA,
        "ultimaRevision": ahora_iso(),
        "productos": productos,
        "alertasEnviadas": sorted(enviados),
        "telegram": {
            "destino": BOT,
            "configurado": bool(token and chat_id),
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
