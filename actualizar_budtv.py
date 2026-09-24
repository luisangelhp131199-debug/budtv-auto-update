
import json
import os
import requests

API_URL = "https://rs.arcando.cloud/budtv/budtvpro.php?cmd=live"
GIST_ID = "7e9f4cfd00e89e9faa6cea4b649cdde5"
GIST_FILE = "canales.json"


def buscar_canales(data, resultado):
    if isinstance(data, dict):
        if data.get("poster") and data.get("url_video"):
            resultado.append(data)

        for value in data.values():
            if isinstance(value, (dict, list)):
                buscar_canales(value, resultado)

    elif isinstance(data, list):
        for item in data:
            buscar_canales(item, resultado)


def main():
    token = os.environ.get("GIST_TOKEN")
    if not token:
        raise Exception("Falta configurar GIST_TOKEN")

    session = requests.Session()

    # 1. Consultar la API actual de BUD TV
    response = session.get(API_URL, timeout=40)
    response.raise_for_status()
    api_data = response.json()

    canales_api = []
    buscar_canales(api_data, canales_api)

    if not canales_api:
        raise Exception("La API no devolvió canales reconocibles")

    # 2. Crear un índice por poster/logo.
    # Solo se actualizarán coincidencias únicas.
    por_poster = {}

    for canal in canales_api:
        poster = str(canal.get("poster", "")).strip()
        url_video = str(canal.get("url_video", "")).strip()

        if poster and url_video:
            por_poster.setdefault(poster, []).append(url_video)

    # 3. Descargar el Gist actual
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    gist_url = f"https://api.github.com/gists/{GIST_ID}"

    response = session.get(
        gist_url, headers=headers, timeout=40
    )
    response.raise_for_status()
    gist = response.json()

    if GIST_FILE not in gist.get("files", {}):
        raise Exception("No se encontró canales.json en el Gist")

    archivo = gist["files"][GIST_FILE]
    contenido = archivo.get("content")

    if contenido is None:
        raw_url = archivo.get("raw_url")
        if not raw_url:
            raise Exception("No se pudo obtener el JSON del Gist")

        response = session.get(raw_url, timeout=40)
        response.raise_for_status()
        contenido = response.text

    datos = json.loads(contenido)

    if not isinstance(datos, list):
        raise Exception("El JSON del Gist no es una lista")

    # 4. Buscar por logo, NO por el dominio de la URL actual.
    actualizados = 0
    sin_coincidencia = 0
    ambiguos = 0
    revisados = 0

    for item in datos:
        if not isinstance(item, dict):
            continue

        logo = str(item.get("logo", "")).strip()
        coincidencias = por_poster.get(logo, [])

        # No tocar entradas que no correspondan a un canal
        # de la API de BUD TV.
        if not coincidencias:
            continue

        revisados += 1

        if len(coincidencias) != 1:
            ambiguos += 1
            continue

        nueva_url = coincidencias[0]

        if item.get("url") != nueva_url:
            item["url"] = nueva_url
            actualizados += 1

    # 5. Guardar solo si hubo cambios reales
    if actualizados == 0:
        print(
            "No hubo URLs diferentes. "
            f"Canales BUD reconocidos: {revisados}; "
            f"sin coincidencia: {sin_coincidencia}; "
            f"ambiguos: {ambiguos}."
        )
        return

    nuevo_contenido = json.dumps(
        datos, ensure_ascii=False, indent=2
    ) + "\n"

    payload = {
        "files": {
            GIST_FILE: {
                "content": nuevo_contenido
            }
        }
    }

    response = session.patch(
        gist_url,
        headers=headers,
        json=payload,
        timeout=40
    )
    response.raise_for_status()

    print(
        f"Gist actualizado: {actualizados} URL(s). "
        f"Canales BUD reconocidos: {revisados}; "
        f"ambiguos: {ambiguos}."
    )


if __name__ == "__main__":
    main()
