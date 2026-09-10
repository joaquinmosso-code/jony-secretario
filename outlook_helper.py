"""
Módulo de conexión a Outlook (Microsoft Graph) para Jony.

Usa el flujo de "device code": la primera vez, en la TERMINAL va a aparecer
un mensaje con una URL (microsoft.com/devicelogin) y un código corto.
Entrá a esa URL, escribí el código, iniciá sesión con tu cuenta de Outlook
y aceptá los permisos. Después queda guardado un archivo de caché y no
lo vuelve a pedir (hasta que expire).
"""

import os
import datetime
import requests
import msal

CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID")
TENANT_ID = os.getenv("OUTLOOK_TENANT_ID", "common")
SCOPES = ["Mail.Read", "Calendars.Read"]
CACHE_FILE = "outlook_token_cache.bin"

GRAPH_URL = "https://graph.microsoft.com/v1.0"


def _load_cache():
    cache = msal.SerializableTokenCache()
    if not os.path.exists(CACHE_FILE):
        contenido_env = os.getenv("OUTLOOK_TOKEN_CACHE")
        if contenido_env:
            with open(CACHE_FILE, "w") as f:
                f.write(contenido_env)
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache.deserialize(f.read())
    return cache


def _save_cache(cache):
    if cache.has_state_changed:
        with open(CACHE_FILE, "w") as f:
            f.write(cache.serialize())


def _get_app():
    cache = _load_cache()
    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    app = msal.PublicClientApplication(CLIENT_ID, authority=authority, token_cache=cache)
    return app, cache


def get_access_token():
    if not CLIENT_ID:
        raise RuntimeError(
            "No encontré OUTLOOK_CLIENT_ID. Revisá que esté en el archivo .env."
        )

    app, cache = _get_app()
    accounts = app.get_accounts()

    result = None
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result:
        raise RuntimeError(
            "El acceso a Outlook venció y no lo pude renovar solo (no hay una sesión "
            "guardada válida). Hay que volver a autorizar desde una PC: correr el login "
            "de Outlook ahí, y después actualizar la variable de entorno "
            "OUTLOOK_TOKEN_CACHE con el contenido nuevo de outlook_token_cache.bin."
        )

    _save_cache(cache)

    if "access_token" not in result:
        raise RuntimeError(
            f"No pude autenticar con Outlook: {result.get('error_description', 'error desconocido')}"
        )

    return result["access_token"]


def obtener_no_leidos(cantidad: int = 5):
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "$filter": "isRead eq false",
        "$top": cantidad,
        "$select": "from,subject,bodyPreview",
        "$orderby": "receivedDateTime desc",
    }
    resp = requests.get(
        f"{GRAPH_URL}/me/mailFolders/inbox/messages", headers=headers, params=params
    )
    resp.raise_for_status()
    data = resp.json()

    correos = []
    for msg in data.get("value", []):
        remitente = msg.get("from", {}).get("emailAddress", {}).get("address", "(desconocido)")
        correos.append({
            "de": remitente,
            "asunto": msg.get("subject", "(sin asunto)"),
            "resumen": msg.get("bodyPreview", ""),
        })
    return correos


def obtener_proximos_eventos(cantidad: int = 5):
    """Devuelve los próximos eventos del calendario de Outlook (próximos 7 días)."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Prefer": 'outlook.timezone="Argentina Standard Time"',
    }

    ahora = datetime.datetime.utcnow()
    en_una_semana = ahora + datetime.timedelta(days=7)

    params = {
        "startDateTime": ahora.isoformat() + "Z",
        "endDateTime": en_una_semana.isoformat() + "Z",
        "$orderby": "start/dateTime",
        "$top": cantidad,
        "$select": "subject,start,end,location",
    }
    resp = requests.get(f"{GRAPH_URL}/me/calendarView", headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json()

    eventos = []
    for e in data.get("value", []):
        eventos.append({
            "titulo": e.get("subject", "(sin título)"),
            "inicio": e.get("start", {}).get("dateTime"),
            "lugar": e.get("location", {}).get("displayName", ""),
        })
    return eventos
