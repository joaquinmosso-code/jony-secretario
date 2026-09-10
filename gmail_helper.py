"""
Módulo de conexión a Gmail para Jony.
Usa las credenciales compartidas de google_auth.py.
"""

from googleapiclient.discovery import build
import google_auth


def _get_header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return "(sin datos)"


def obtener_no_leidos(cantidad: int = 5):
    """Devuelve una lista de dicts con remitente, asunto y un snippet de cada mail no leído."""
    creds = google_auth.get_credentials()
    service = build("gmail", "v1", credentials=creds)

    resultados = (
        service.users()
        .messages()
        .list(userId="me", labelIds=["INBOX", "UNREAD"], maxResults=cantidad)
        .execute()
    )
    mensajes = resultados.get("messages", [])

    correos = []
    for msg in mensajes:
        detalle = (
            service.users()
            .messages()
            .get(userId="me", id=msg["id"], format="metadata",
                 metadataHeaders=["From", "Subject"])
            .execute()
        )
        headers = detalle["payload"]["headers"]
        correos.append({
            "de": _get_header(headers, "From"),
            "asunto": _get_header(headers, "Subject"),
            "resumen": detalle.get("snippet", ""),
        })

    return correos
