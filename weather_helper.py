"""
Módulo de clima para Jony, usando Open-Meteo (gratis, sin API key).
"""

import requests

WEATHER_CODES = {
    0: "Despejado ☀️",
    1: "Mayormente despejado 🌤️",
    2: "Parcialmente nublado ⛅",
    3: "Nublado ☁️",
    45: "Niebla 🌫️",
    48: "Niebla con escarcha 🌫️",
    51: "Llovizna leve 🌦️",
    53: "Llovizna moderada 🌦️",
    55: "Llovizna intensa 🌧️",
    61: "Lluvia leve 🌦️",
    63: "Lluvia moderada 🌧️",
    65: "Lluvia intensa 🌧️",
    71: "Nevada leve 🌨️",
    73: "Nevada moderada 🌨️",
    75: "Nevada intensa 🌨️",
    80: "Chubascos leves 🌦️",
    81: "Chubascos moderados 🌧️",
    82: "Chubascos violentos ⛈️",
    95: "Tormenta ⛈️",
    96: "Tormenta con granizo leve ⛈️",
    99: "Tormenta con granizo fuerte ⛈️",
}


def descripcion_clima(codigo):
    return WEATHER_CODES.get(codigo, "Condición desconocida")


def _geocodificar(ciudad: str):
    geo_resp = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": ciudad, "count": 1, "language": "es"},
    )
    geo_resp.raise_for_status()
    resultados = geo_resp.json().get("results")
    if not resultados:
        return None
    return resultados[0]


def obtener_clima(ciudad: str, dia: str = "hoy"):
    """
    Busca una ciudad y devuelve su clima.
    dia: "hoy" (clima actual) o "mañana" (pronóstico del día siguiente).
    Devuelve None si no encuentra la ciudad.
    """
    lugar = _geocodificar(ciudad)
    if not lugar:
        return None

    lat, lon = lugar["latitude"], lugar["longitude"]
    nombre = lugar.get("name")
    provincia = lugar.get("admin1", "")

    if dia == "mañana":
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,weather_code",
                "timezone": "America/Argentina/Cordoba",
                "forecast_days": 2,
            },
        )
        resp.raise_for_status()
        daily = resp.json().get("daily", {})

        return {
            "tipo": "pronostico",
            "ciudad": nombre,
            "provincia": provincia,
            "fecha": daily.get("time", [None, None])[1],
            "temp_max": daily.get("temperature_2m_max", [None, None])[1],
            "temp_min": daily.get("temperature_2m_min", [None, None])[1],
            "codigo_clima": daily.get("weather_code", [None, None])[1],
        }

    # dia == "hoy" -> clima actual
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "timezone": "America/Argentina/Cordoba",
        },
    )
    resp.raise_for_status()
    actual = resp.json().get("current", {})

    return {
        "tipo": "actual",
        "ciudad": nombre,
        "provincia": provincia,
        "temperatura": actual.get("temperature_2m"),
        "humedad": actual.get("relative_humidity_2m"),
        "viento": actual.get("wind_speed_10m"),
        "codigo_clima": actual.get("weather_code"),
    }
