"""
Conexión de Jony con la app de Gestión de Sucursales de GLB.

Jony se loguea con su propio usuario (creado en Configuración → Usuarios
y Permisos de la app) y a partir de ahí puede consultar y cargar datos,
usando la misma API que usa la app web.
"""

import os
import uuid
import datetime
import requests

GLB_BASE_URL = os.getenv("GLB_APP_URL", "https://sucursales.grupolabarranca.com").rstrip("/")
GLB_PASSWORD = os.getenv("GLB_JONY_PASSWORD")

_session = requests.Session()
_logueado = False


def _login():
    global _logueado
    if not GLB_PASSWORD:
        raise RuntimeError(
            "No encontré GLB_JONY_PASSWORD. Hay que configurar esa variable de entorno "
            "con la contraseña del usuario de Jony en la app de Sucursales."
        )
    resp = _session.post(f"{GLB_BASE_URL}/api/login", json={"password": GLB_PASSWORD}, timeout=15)
    data = resp.json() if resp.content else {}
    if not resp.ok or not data.get("ok"):
        raise RuntimeError("No pude iniciar sesión en la app de Sucursales. Revisá GLB_JONY_PASSWORD.")
    _logueado = True


def obtener_datos():
    """Trae el estado completo de la app (ya logueado)."""
    global _logueado
    if not _logueado:
        _login()
    resp = _session.get(f"{GLB_BASE_URL}/api/data", timeout=20)
    if resp.status_code == 401:
        _login()
        resp = _session.get(f"{GLB_BASE_URL}/api/data", timeout=20)
    resp.raise_for_status()
    return resp.json()


def guardar_datos(data):
    """Guarda el estado completo de vuelta (después de modificarlo en memoria)."""
    global _logueado
    if not _logueado:
        _login()
    resp = _session.post(f"{GLB_BASE_URL}/api/data", json=data, timeout=30)
    if resp.status_code == 401:
        _login()
        resp = _session.post(f"{GLB_BASE_URL}/api/data", json=data, timeout=30)
    resp.raise_for_status()
    resultado = resp.json()
    if not resultado.get("ok"):
        raise RuntimeError(resultado.get("reason", "Error desconocido al guardar en la app."))
    return resultado


NOMBRES_SUCURSALES = {
    "abasto": "Abasto",
    "seminario": "Seminario",
    "alejandro_roca": "Alejandro Roca",
    "villa_mercedes": "Villa Mercedes",
    "villa_general_belgrano": "Villa General Belgrano",
    "interno": "Interno (Mkt y Operativas)",
    "comercial_tareas": "Tareas Comerciales",
}


def _resolver_sucursal(texto):
    """Busca el slug de sucursal a partir de un texto libre (ej: 'abasto', 'Villa Gral Belgrano')."""
    if not texto:
        return None
    t = texto.strip().lower().replace("gral", "general")
    for slug, nombre in NOMBRES_SUCURSALES.items():
        if t == slug or t in nombre.lower() or nombre.lower() in t:
            return slug
    return None


def _resolver_persona(data, texto):
    """Busca el id de una persona a partir de su nombre (o parte del nombre)."""
    if not texto:
        return None, None
    t = texto.strip().lower()
    for p in data.get("personas", []):
        if t in (p.get("nombre") or "").lower():
            return p["id"], p["nombre"]
    return None, None


def consultar_tareas_pendientes(sucursal=None, persona=None):
    data = obtener_datos()
    personas_por_id = {p["id"]: p["nombre"] for p in data.get("personas", [])}
    slug_filtro = _resolver_sucursal(sucursal) if sucursal else None
    if sucursal and not slug_filtro:
        return {"error": f"No encontré la sucursal '{sucursal}'."}

    resultado = []
    for suc_key, suc in data.get("sucursales", {}).items():
        if slug_filtro and suc_key != slug_filtro:
            continue
        for t in suc.get("tareas", []):
            if (t.get("estado") or "").lower() == "hecha":
                continue
            nombre_persona = personas_por_id.get(t.get("asignadaA"), "")
            if persona and persona.strip().lower() not in nombre_persona.lower():
                continue
            resultado.append({
                "sucursal": NOMBRES_SUCURSALES.get(suc_key, suc_key),
                "titulo": t.get("titulo"),
                "asignada_a": nombre_persona or "(sin asignar)",
                "vencimiento": t.get("vencimiento") or "(sin fecha)",
                "prioridad": t.get("prioridad") or "",
                "estado": t.get("estado") or "",
            })
    return {"tareas_pendientes": resultado, "total": len(resultado)}


def crear_tarea(sucursal, titulo, asignada_a_nombre=None, vencimiento=None, prioridad="Media"):
    slug = _resolver_sucursal(sucursal)
    if not slug:
        return {"error": f"No encontré la sucursal '{sucursal}'. Las válidas son: {', '.join(NOMBRES_SUCURSALES.values())}."}

    data = obtener_datos()
    suc = data["sucursales"].get(slug)
    if suc is None:
        return {"error": f"La sucursal '{sucursal}' no está disponible para vos en este momento."}

    persona_id, persona_nombre = _resolver_persona(data, asignada_a_nombre) if asignada_a_nombre else (None, None)

    nueva = {
        "id": "id_" + uuid.uuid4().hex[:12],
        "titulo": titulo,
        "asignadaA": persona_id or "",
        "vencimiento": vencimiento or "",
        "prioridad": prioridad or "Media",
        "estado": "Pendiente",
        "notas": "",
    }
    suc.setdefault("tareas", []).append(nueva)
    guardar_datos(data)

    aviso_persona = ""
    if asignada_a_nombre and not persona_id:
        aviso_persona = f" (no encontré a '{asignada_a_nombre}' en la lista de personas, quedó sin asignar)"

    return {
        "ok": True,
        "sucursal": NOMBRES_SUCURSALES.get(slug, slug),
        "titulo": titulo,
        "asignada_a": persona_nombre or "(sin asignar)" ,
        "aviso": aviso_persona or None,
    }


def registrar_actividad_comercial(tipo, cliente, sucursal=None, nota=None):
    tipos_validos = ("visita", "lead", "recuperado", "nuevo")
    tipo_norm = (tipo or "").strip().lower()
    if tipo_norm not in tipos_validos:
        return {"error": f"El tipo de actividad tiene que ser uno de: {', '.join(tipos_validos)}."}

    slug = _resolver_sucursal(sucursal) if sucursal else ""
    if sucursal and not slug:
        slug = ""  # si no la reconoce, la deja vacía en vez de fallar

    data = obtener_datos()
    nueva = {
        "id": "id_" + uuid.uuid4().hex[:12],
        "tipo": tipo_norm,
        "cliente": cliente,
        "fecha": datetime.date.today().isoformat(),
        "sucursal": slug,
        "sucursalOtroTexto": "" if slug else (sucursal or ""),
        "clienteActual": False,
        "tipoCliente": None,
        "nota": nota or "",
        "productos": [],
        "futura": {},
        "cargadoPor": "Jony",
    }
    data.setdefault("comercialActividad", []).append(nueva)
    guardar_datos(data)
    return {"ok": True, "tipo": tipo_norm, "cliente": cliente, "sucursal": NOMBRES_SUCURSALES.get(slug, sucursal or "(sin sucursal)")}


def resumen_precios(sucursal=None):
    slug = _resolver_sucursal(sucursal) if sucursal else None
    if sucursal and not slug:
        return {"error": f"No encontré la sucursal '{sucursal}'."}

    data = obtener_datos()
    resultado = {}
    for suc_key, suc in data.get("sucursales", {}).items():
        if slug and suc_key != slug:
            continue
        comercial = suc.get("comercial") or []
        if not comercial:
            continue
        ultimo = sorted(comercial, key=lambda c: c.get("fecha") or "")[-1]
        resultado[NOMBRES_SUCURSALES.get(suc_key, suc_key)] = {
            "fecha": ultimo.get("fecha"),
            "precios_propios": ultimo.get("propio"),
        }
    return resultado or {"info": "No hay precios cargados todavía."}


SECCIONES_GENERALES = {
    "tareas": "Todas las tareas (pendientes y hechas) de cada sucursal, con quién las tiene asignadas.",
    "comercial_actividad": "El registro completo de actividad comercial (visitas, leads, clientes nuevos/recuperados).",
    "personas": "La lista de personas del equipo (nombre, rol).",
    "objetivos_petrolera": "Los objetivos bimestrales de la petrolera, por sucursal.",
    "metas_comerciales": "Las metas comerciales cargadas por mes.",
}


def consultar_datos_generales(seccion):
    """Devuelve datos en crudo de una sección de la app para que puedas responder
    cualquier pregunta sobre ellos vos mismo, sin depender de una función específica.
    Secciones válidas: ver SECCIONES_GENERALES."""
    s = (seccion or "").strip().lower().replace(" ", "_")
    if s not in SECCIONES_GENERALES:
        return {"error": f"Sección '{seccion}' desconocida. Válidas: {', '.join(SECCIONES_GENERALES.keys())}."}

    data = obtener_datos()
    personas_por_id = {p["id"]: p["nombre"] for p in data.get("personas", [])}

    if s == "tareas":
        resultado = {}
        for suc_key, suc in data.get("sucursales", {}).items():
            tareas = suc.get("tareas") or []
            if not tareas:
                continue
            resultado[NOMBRES_SUCURSALES.get(suc_key, suc_key)] = [
                {
                    "titulo": t.get("titulo"),
                    "estado": t.get("estado"),
                    "asignada_a": personas_por_id.get(t.get("asignadaA"), "(sin asignar)"),
                    "vencimiento": t.get("vencimiento") or None,
                    "prioridad": t.get("prioridad"),
                }
                for t in tareas
            ]
        return resultado

    if s == "comercial_actividad":
        actividad = data.get("comercialActividad") or []
        return [
            {
                "tipo": a.get("tipo"),
                "cliente": a.get("cliente"),
                "fecha": a.get("fecha"),
                "sucursal": NOMBRES_SUCURSALES.get(a.get("sucursal"), a.get("sucursal") or a.get("sucursalOtroTexto")),
                "nota": a.get("nota") or None,
            }
            for a in actividad
        ]

    if s == "personas":
        return [{"nombre": p.get("nombre"), "rol": p.get("rol")} for p in data.get("personas", [])]

    if s == "objetivos_petrolera":
        objetivos = data.get("objetivosPetrolera") or {}
        return {NOMBRES_SUCURSALES.get(k, k): v for k, v in objetivos.items()}

    if s == "metas_comerciales":
        return data.get("metasComerciales") or {}

    return {}


# ---------- Panel de ventas / volúmenes (usa la misma sesión que la app principal) ----------
PANEL_SUCURSALES = {
    "abasto": "Abasto",
    "seminario": "Seminario",
    "alejandro_roca": "Alejandro Roca",
    "villa_mercedes": "Villa Mercedes",
    "villa_gral_belgrano": "Villa General Belgrano",
}

PANEL_PRODUCTOS = {
    "diesel": "Diesel (grado 2)",
    "euro": "Euro (grado 3)",
    "nafta_super": "Nafta Super (grado 2)",
    "nafta_premium": "Nafta Premium (grado 3)",
    "gnc": "GNC",
}


def _resolver_sucursal_panel(texto):
    if not texto:
        return None
    t = texto.strip().lower().replace("gral.", "general").replace("gral", "general")
    for slug, nombre in PANEL_SUCURSALES.items():
        nombre_norm = nombre.lower().replace("general", "general")
        if t == slug or t in nombre_norm or nombre_norm in t:
            return slug
    return None


def obtener_datos_panel():
    global _logueado
    if not _logueado:
        _login()
    resp = _session.get(f"{GLB_BASE_URL}/api/panel-data", timeout=20)
    if resp.status_code == 401:
        _login()
        resp = _session.get(f"{GLB_BASE_URL}/api/panel-data", timeout=20)
    resp.raise_for_status()
    return resp.json()


def consultar_ventas_detalle():
    """Devuelve TODO el detalle de ventas del panel (mes, sucursal, producto, litros,
    precio, presupuesto), sin agrupar ni filtrar — para que puedas calcular vos mismo
    cualquier comparación, ranking o suma que te pidan (por producto, por sucursal,
    por mes, interanual, lo que sea), sin depender de un filtro predefinido."""
    data = obtener_datos_panel()
    ventas = list((data.get("ventas") or {}).values())
    detalle = []
    for v in ventas:
        producto = v.get("producto")
        detalle.append({
            "mes": v.get("mes"),
            "sucursal": PANEL_SUCURSALES.get(v.get("sucursal"), v.get("sucursal")),
            "producto": "Total líquidos (sin discriminar)" if producto == "total_liquidos" else PANEL_PRODUCTOS.get(producto, producto),
            "unidad": v.get("unidad"),
            "litros_o_m3_vendidos": v.get("litros"),
            "precio": v.get("precio") or None,
            "presupuesto_litros_o_m3": v.get("presLitros") or None,
        })
    detalle.sort(key=lambda x: (x["mes"] or "", x["sucursal"] or ""))
    return {"registros": detalle, "total_registros": len(detalle)}
