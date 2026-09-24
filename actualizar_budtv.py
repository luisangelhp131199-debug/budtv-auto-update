import json
import os
import requests

API_URL = "https://rs.arcando.cloud/budtv/budtvpro.php?cmd=live"
GIST_ID = "7e9f4cfd00e89e9faa6cea4b649cdde5"
GIST_FILE = "canales.json"


def find_channels(data, result):
    if isinstance(data, dict):
        if data.get("poster") and data.get("url_video"):
            result.append(data)
        for value in data.values():
            if isinstance(value, (dict, list)):
                find_channels(value, result)

    elif isinstance(data, list):
        for item in data:
            find_channels(item, result)


def main():
    token = os.environ.get("GIST_TOKEN")
    if not token:
        raise Exception("Falta configurar GIST_TOKEN")

    session = requests.Session()

    # Consultar API de BUD TV
    response = session.get(API_URL, timeout=40)
    response.raise_for_status()
    api_data = response.json()

    channels = []
    find_channels(api_data, channels)

    if not channels:
        raise Exception("La API no devolvió canales reconocibles")

    # Relacionar poster con URL nueva
    by_poster = {}

    for channel in channels:
        poster = str(channel.get("poster", "")).strip()
        url = str(channel.get("url_video", "")).strip()

        if poster and url:
            by_poster.setdefault(poster, []).append(url)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Obtener el Gist actual
    gist_url = f"https://api.github.com/gists/{GIST_ID}"
    response = session.get(gist_url, headers=headers, timeout=40)
    response.raise_for_status()
    gist = response.json()

    if GIST_FILE not in gist.get("files", {}):
        raise Exception("No se encontró canales.json en el Gist")

    content = gist["files"][GIST_FILE].get("content")

    if content is None:
        raw_url = gist["files"][GIST_FILE].get("raw_url")
        if not raw_url:
            raise Exception("No se pudo obtener el JSON del Gist")

        response = session.get(raw_url, timeout=40)
        response.raise_for_status()
        content = response.text

    data = json.loads(content)

    if not isinstance(data, list):
        raise Exception("El JSON del Gist no es una lista")

    updated = 0

    for item in data:
        if not isinstance(item, dict):
            continue

        old_url = str(item.get("url", "")).lower()

        # Solo canales BUD TV que ya existen
        if "rs.arcando.cloud/budtv/" not in old_url:
            continue

        logo = str(item.get("logo", "")).strip()
        matches = by_poster.get(logo, [])

        # Actualizar solo si el logo coincide con un único canal
        if len(matches) == 1 and item.get("url") != matches[0]:
            item["url"] = matches[0]
            updated += 1

    if updated == 0:
        print("No hay cambios. El Gist queda igual.")
        return

    new_content = json.dumps(
        data, ensure_ascii=False, indent=2
    ) + "\n"

    patch = {
        "files": {
            GIST_FILE: {
                "content": new_content
            }
        }
    }

    response = session.patch(
        gist_url,
        headers=headers,
        json=patch,
        timeout=40
    )
    response.raise_for_status()

    print(f"Gist actualizado: {updated} URL(s)")


if __name__ == "__main__":
    main()
