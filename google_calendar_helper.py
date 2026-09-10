"""
Módulo de conexión a Google Calendar para Jony.
Usa las credenciales compartidas de google_auth.py.
"""

import datetime
from googleapiclient.discovery import build
import google_auth


def obtener_proximos_eventos(cantidad: int = 5):
    """Devuelve los próximos eventos del calendario principal de Google."""
    creds = google_auth.get_credentials()
    service = build("calendar", "v3", credentials=creds)

    ahora = datetime.datetime.utcnow().isoformat() + "Z"

    resultados = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=ahora,
            maxResults=cantidad,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    eventos = resultados.get("items", [])

    lista = []
    for evento in eventos:
        inicio = evento["start"].get("dateTime", evento["start"].get("date"))
        lista.append({
            "titulo": evento.get("summary", "(sin título)"),
            "inicio": inicio,
            "lugar": evento.get("location", ""),
        })

    return lista
