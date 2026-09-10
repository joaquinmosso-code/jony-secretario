"""
Autenticación compartida con Google para Jony (Gmail + Calendar).

En el servidor (Railway) no hay navegador para hacer el login interactivo,
así que el token que ya autorizaste desde tu PC se carga desde la variable
de entorno GOOGLE_TOKEN_JSON. Mientras el refresh token siga siendo válido,
Jony renueva el acceso solo, sin volver a pedirte nada.

Si en algún momento Google pide reautorizar de cero (pasa raramente, o si
cambian los permisos), hay que volver a correr el login interactivo desde
una PC con navegador y actualizar la variable GOOGLE_TOKEN_JSON con el
contenido nuevo de token.json.
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

TOKEN_FILE = "token.json"


def _asegurar_archivo_desde_env(nombre_archivo, nombre_env):
    """Si el archivo no existe en disco pero sí la variable de entorno, lo crea."""
    if os.path.exists(nombre_archivo):
        return
    contenido = os.getenv(nombre_env)
    if contenido:
        with open(nombre_archivo, "w") as f:
            f.write(contenido)


def get_credentials():
    _asegurar_archivo_desde_env(TOKEN_FILE, "GOOGLE_TOKEN_JSON")

    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError(
            "No encontré credenciales de Google (falta GOOGLE_TOKEN_JSON). "
            "Hay que autorizar Gmail/Calendar una vez desde una PC con navegador "
            "y cargar el token.json resultante como variable de entorno."
        )

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())
        else:
            raise RuntimeError(
                "El token de Google venció y no se pudo renovar solo. "
                "Hay que volver a autorizar desde una PC con navegador y actualizar "
                "la variable de entorno GOOGLE_TOKEN_JSON."
            )

    return creds
