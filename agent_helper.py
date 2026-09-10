"""
Cerebro de Jony: entiende mensajes en lenguaje natural y decide qué hacer,
usando la API de Claude (tool use) para llamar a las funciones que ya
tenemos armadas (clima, mail, agenda).
"""

import json
import datetime
import anthropic

import weather_helper
import gmail_helper
import outlook_helper
import google_calendar_helper
import glb_helper

# Haiku 4.5: el modelo más rápido y económico de Claude, ideal para este uso
MODEL = "claude-haiku-4-5-20251001"

client = anthropic.Anthropic()  # Lee ANTHROPIC_API_KEY del entorno automáticamente

def system_prompt():
    hoy = datetime.date.today().strftime("%Y-%m-%d")
    return (
        "Sos Jony, el secretario personal de Joaquín (Joaco), Gerente de Operaciones "
        "y Marketing en Grupo La Barranca (GLB), una empresa de energía (AXION Energy "
        "y Puma Energy) en el sur de Córdoba y norte de San Luis, Argentina. "
        f"Hoy es {hoy} (formato AAAA-MM-DD) — usá siempre esta fecha como referencia de 'hoy', "
        "'este mes', 'el año pasado', etc., y para convertir meses en texto (ej: 'agosto') al "
        "formato AAAA-MM que piden las herramientas. Nunca asumas otro año. "
        "Respondé siempre en español rioplatense, de forma cálida, directa y breve, "
        "como un asistente de confianza por Telegram. Usá las herramientas disponibles "
        "para responder con datos reales de mail, agenda, clima y de la app de Gestión "
        "de Sucursales — nunca inventes esa información. Cuando la pregunta sea sobre "
        "ventas, tareas, actividad comercial u otros datos de la app y no haya una "
        "herramienta puntual para eso, usá 'consultar_ventas_detalle' o "
        "'consultar_datos_generales' para traer los datos en crudo, y hacé vos mismo el "
        "cálculo, filtro o comparación que te pidan (sumar, comparar meses, rankear, "
        "lo que sea) — no hace falta que exista una herramienta específica para cada "
        "pregunta posible. Si te piden cargar una tarea o "
        "registrar una actividad comercial, usá la herramienta correspondiente y confirmá "
        "con un mensaje corto qué quedó cargado. Si una herramienta devuelve un error, "
        "contáselo a Joaco de forma simple, sin tecnicismos."
    )

TOOLS = [
    {
        "name": "consultar_clima",
        "description": "Consulta el clima actual o el pronóstico de mañana para una ciudad o localidad.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ciudad": {"type": "string", "description": "Nombre de la ciudad o localidad"},
                "dia": {
                    "type": "string",
                    "enum": ["hoy", "mañana"],
                    "description": "Si se pide el clima de hoy o el pronóstico de mañana. Default: hoy.",
                },
            },
            "required": ["ciudad"],
        },
    },
    {
        "name": "leer_gmail",
        "description": "Devuelve los últimos mails no leídos de la casilla de Gmail de Joaco.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cantidad": {"type": "integer", "description": "Cuántos mails traer. Default 5."}
            },
        },
    },
    {
        "name": "leer_outlook",
        "description": "Devuelve los últimos mails no leídos de la casilla de Outlook de Joaco.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cantidad": {"type": "integer", "description": "Cuántos mails traer. Default 5."}
            },
        },
    },
    {
        "name": "ver_agenda",
        "description": "Devuelve los próximos eventos de Google Calendar y de Outlook Calendar de Joaco.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "consultar_tareas_pendientes",
        "description": "Devuelve las tareas pendientes (no completadas) de la app de Gestión de Sucursales de GLB. Se puede filtrar por sucursal y/o por a quién está asignada.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sucursal": {"type": "string", "description": "Nombre de la sucursal (ej: Abasto, Seminario, Alejandro Roca, Villa Mercedes, Villa General Belgrano, Interno). Si no se especifica, trae de todas."},
                "persona": {"type": "string", "description": "Nombre (o parte del nombre) de la persona a la que está asignada la tarea."},
            },
        },
    },
    {
        "name": "crear_tarea_glb",
        "description": "Crea una tarea nueva en una sucursal de la app de Gestión de Sucursales de GLB.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sucursal": {"type": "string", "description": "Nombre de la sucursal (ej: Abasto, Seminario, Alejandro Roca, Villa Mercedes, Villa General Belgrano, Interno)."},
                "titulo": {"type": "string", "description": "Título o descripción de la tarea."},
                "asignada_a_nombre": {"type": "string", "description": "Nombre de la persona a la que se le asigna, si se conoce (opcional)."},
                "vencimiento": {"type": "string", "description": "Fecha límite en formato AAAA-MM-DD (opcional)."},
                "prioridad": {"type": "string", "enum": ["Baja", "Media", "Alta"], "description": "Prioridad de la tarea. Default: Media."},
            },
            "required": ["sucursal", "titulo"],
        },
    },
    {
        "name": "registrar_actividad_comercial",
        "description": "Registra una nueva actividad comercial (visita, lead, cliente recuperado o cliente nuevo) en la app de GLB.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": ["visita", "lead", "recuperado", "nuevo"], "description": "Tipo de actividad comercial."},
                "cliente": {"type": "string", "description": "Nombre del cliente."},
                "sucursal": {"type": "string", "description": "Nombre de la sucursal relacionada, si aplica (opcional)."},
                "nota": {"type": "string", "description": "Detalle o comentario de la actividad (opcional)."},
            },
            "required": ["tipo", "cliente"],
        },
    },
    {
        "name": "consultar_precios",
        "description": "Devuelve los últimos precios propios cargados por sucursal en la app de GLB.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sucursal": {"type": "string", "description": "Nombre de la sucursal. Si no se especifica, trae de todas."},
            },
        },
    },
    {
        "name": "consultar_ventas_detalle",
        "description": "Devuelve TODO el detalle de ventas del Panel de Estaciones de Servicio de GLB (mes, sucursal, producto, litros/m³, precio, presupuesto), registro por registro, sin agrupar. Usala para cualquier pregunta sobre ventas o volúmenes — vos mismo filtrás, sumás o comparás lo que haga falta con estos datos (por producto, por sucursal, por mes, interanual, ranking, lo que sea).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "consultar_datos_generales",
        "description": "Devuelve datos en crudo de una sección de la app de GLB, para responder cualquier pregunta sobre esa sección vos mismo (filtrando, contando, comparando lo que haga falta) sin depender de una herramienta específica. Secciones disponibles: 'tareas' (todas las tareas de cada sucursal, con estado y a quién están asignadas), 'comercial_actividad' (todo el registro de visitas/leads/clientes), 'personas' (el equipo), 'objetivos_petrolera' (objetivos bimestrales por sucursal), 'metas_comerciales' (metas por mes).",
        "input_schema": {
            "type": "object",
            "properties": {
                "seccion": {"type": "string", "enum": ["tareas", "comercial_actividad", "personas", "objetivos_petrolera", "metas_comerciales"]},
            },
            "required": ["seccion"],
        },
    },
]


def _ejecutar_tool(nombre, entrada):
    try:
        if nombre == "consultar_clima":
            resultado = weather_helper.obtener_clima(
                entrada["ciudad"], dia=entrada.get("dia", "hoy")
            )
            if not resultado:
                return {"error": f"No encontré la ciudad {entrada['ciudad']}"}
            resultado["descripcion"] = weather_helper.descripcion_clima(resultado["codigo_clima"])
            return resultado

        if nombre == "leer_gmail":
            return {"mails": gmail_helper.obtener_no_leidos(cantidad=entrada.get("cantidad", 5))}

        if nombre == "leer_outlook":
            return {"mails": outlook_helper.obtener_no_leidos(cantidad=entrada.get("cantidad", 5))}

        if nombre == "ver_agenda":
            eventos_google = google_calendar_helper.obtener_proximos_eventos(cantidad=5)
            eventos_outlook = outlook_helper.obtener_proximos_eventos(cantidad=5)
            return {"google_calendar": eventos_google, "outlook_calendar": eventos_outlook}

        if nombre == "consultar_tareas_pendientes":
            return glb_helper.consultar_tareas_pendientes(
                sucursal=entrada.get("sucursal"), persona=entrada.get("persona")
            )

        if nombre == "crear_tarea_glb":
            return glb_helper.crear_tarea(
                sucursal=entrada["sucursal"],
                titulo=entrada["titulo"],
                asignada_a_nombre=entrada.get("asignada_a_nombre"),
                vencimiento=entrada.get("vencimiento"),
                prioridad=entrada.get("prioridad", "Media"),
            )

        if nombre == "registrar_actividad_comercial":
            return glb_helper.registrar_actividad_comercial(
                tipo=entrada["tipo"],
                cliente=entrada["cliente"],
                sucursal=entrada.get("sucursal"),
                nota=entrada.get("nota"),
            )

        if nombre == "consultar_precios":
            return glb_helper.resumen_precios(sucursal=entrada.get("sucursal"))

        if nombre == "consultar_ventas_detalle":
            return glb_helper.consultar_ventas_detalle()

        if nombre == "consultar_datos_generales":
            return glb_helper.consultar_datos_generales(seccion=entrada.get("seccion"))

        return {"error": f"Herramienta desconocida: {nombre}"}
    except Exception as e:
        return {"error": str(e)}


# ---------- Memoria de conversación ----------
# Se guarda solo el texto final de cada intercambio (no los pasos intermedios de
# herramientas), por chat de Telegram. Vive en memoria del proceso: si Railway
# reinicia el servicio, se pierde y arranca de cero — es una limitación aceptada,
# no algo persistente en la base de datos.
_HISTORIALES = {}
MAX_INTERCAMBIOS_RECORDADOS = 8  # cuántos pares (Joaco / Jony) previos se le pasan de contexto


def reiniciar_conversacion(chat_id):
    _HISTORIALES.pop(chat_id, None)


def responder(chat_id, mensaje_usuario: str) -> str:
    """Manda el mensaje (con el historial reciente de ese chat) a Claude, ejecuta
    las tools que pida, y devuelve el texto final."""
    historial_previo = _HISTORIALES.get(chat_id, [])
    mensajes = historial_previo + [{"role": "user", "content": mensaje_usuario}]

    texto_final = None
    for _ in range(5):  # límite de vueltas, por las dudas, para evitar loops
        respuesta = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system_prompt(),
            tools=TOOLS,
            messages=mensajes,
        )

        if respuesta.stop_reason != "tool_use":
            texto_final = "".join(
                bloque.text for bloque in respuesta.content if bloque.type == "text"
            ) or "No tengo una respuesta para eso."
            break

        mensajes.append({"role": "assistant", "content": respuesta.content})

        resultados = []
        for bloque in respuesta.content:
            if bloque.type == "tool_use":
                resultado = _ejecutar_tool(bloque.name, bloque.input)
                resultados.append({
                    "type": "tool_result",
                    "tool_use_id": bloque.id,
                    "content": json.dumps(resultado, ensure_ascii=False, default=str),
                })

        mensajes.append({"role": "user", "content": resultados})
    else:
        texto_final = "Perdón, me hice bolas pensando la respuesta. ¿Podés reformularla?"

    # Guardamos en la memoria del chat solo el intercambio "limpio" (sin los pasos de
    # herramientas), así el contexto que se le pasa la próxima vez es liviano y siempre
    # queda bien formado para la API.
    nuevo_historial = historial_previo + [
        {"role": "user", "content": mensaje_usuario},
        {"role": "assistant", "content": texto_final},
    ]
    _HISTORIALES[chat_id] = nuevo_historial[-(MAX_INTERCAMBIOS_RECORDADOS * 2):]

    return texto_final
