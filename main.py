"""
Jony - Secretario Personal
Fase 2: Bot de Telegram + lectura de Gmail

Cómo correrlo:
    1. pip install -r requirements.txt
    2. python main.py
    3. Andá a Telegram, buscá tu bot y mandale /start
"""

import logging
import os
import tempfile
from dotenv import load_dotenv

load_dotenv()  # Lee el archivo .env - tiene que ir ANTES de importar los módulos de mail

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import gmail_helper
import outlook_helper
import weather_helper
import google_calendar_helper
import agent_helper
import voice_helper

# --- Configuración básica ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("jony")


# --- Comandos ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    nombre = update.effective_user.first_name or "jefe"
    await update.message.reply_text(
        f"¡Hola {nombre}! Soy Jony, tu secretario personal. 👋\n\n"
        "Ya puedo revisar tu Gmail, tu Outlook, darte el clima, contarte tu agenda, "
        "y consultar o cargar datos de la app de Gestión de Sucursales. "
        "Y ahora también me podés hablar en lenguaje natural (por texto o por audio), sin comandos.\n\n"
        "Pronto voy a poder avisarte solo cuando necesites recordar algo. 🔔\n\n"
        "Usá /help para ver qué puedo hacer por ahora."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Por ahora puedo:\n"
        "/start - Saludarte\n"
        "/help - Ver esta ayuda\n"
        "/correos - Ver tus últimos mails no leídos de Gmail\n"
        "/outlook - Ver tus últimos mails no leídos de Outlook\n"
        "/clima <ciudad> - Ver el clima actual de una localidad (ej: /clima Río Cuarto)\n"
        "/clima <ciudad> mañana - Ver el pronóstico de mañana (ej: /clima Río Cuarto mañana)\n"
        "/agenda - Ver tus próximos compromisos (Google + Outlook)\n\n"
        "También me podés escribir directamente, sin comandos, o mandarme un audio — por ejemplo:\n"
        "\"¿qué clima hace mañana en Río Cuarto?\", \"tengo mails sin leer?\", "
        "\"¿qué tareas tiene pendientes Nacho en Abasto?\", "
        "\"cargame una tarea en Seminario: revisar el cartel de precios\", "
        "\"registrá una visita al cliente Transporte Rodriguez\", "
        "\"¿cuánto vendimos en Abasto en agosto?\""
    )


async def correos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Un segundo, reviso tu Gmail... 📬")

    try:
        lista = gmail_helper.obtener_no_leidos(cantidad=5)
    except RuntimeError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return
    except Exception as e:
        logger.exception("Error al leer Gmail")
        await update.message.reply_text(
            "⚠️ Tuve un problema conectando con Gmail. Revisá la terminal para más detalle."
        )
        return

    if not lista:
        await update.message.reply_text("No tenés mails sin leer. Bandeja limpia 👌")
        return

    texto = f"Tenés {len(lista)} mail(s) sin leer:\n\n"
    for i, correo in enumerate(lista, start=1):
        texto += (
            f"{i}. *De:* {correo['de']}\n"
            f"   *Asunto:* {correo['asunto']}\n"
            f"   _{correo['resumen']}_\n\n"
        )

    await update.message.reply_text(texto, parse_mode="Markdown")


async def outlook(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Un segundo, reviso tu Outlook... 📬\n"
        "(Si es la primera vez, revisá la terminal — puede pedirte un código para autorizar)"
    )

    try:
        lista = outlook_helper.obtener_no_leidos(cantidad=5)
    except RuntimeError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return
    except Exception:
        logger.exception("Error al leer Outlook")
        await update.message.reply_text(
            "⚠️ Tuve un problema conectando con Outlook. Revisá la terminal para más detalle."
        )
        return

    if not lista:
        await update.message.reply_text("No tenés mails sin leer en Outlook. Bandeja limpia 👌")
        return

    texto = f"Tenés {len(lista)} mail(s) sin leer en Outlook:\n\n"
    for i, correo in enumerate(lista, start=1):
        texto += (
            f"{i}. *De:* {correo['de']}\n"
            f"   *Asunto:* {correo['asunto']}\n"
            f"   _{correo['resumen']}_\n\n"
        )

    await update.message.reply_text(texto, parse_mode="Markdown")


async def clima(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Decime la ciudad así: /clima Río Cuarto (o /clima Río Cuarto mañana)"
        )
        return

    args = list(context.args)
    dia = "hoy"
    if args[-1].lower() in ("mañana", "manana"):
        dia = "mañana"
        args = args[:-1]

    ciudad = " ".join(args)
    if not ciudad:
        await update.message.reply_text(
            "Decime la ciudad así: /clima Río Cuarto mañana"
        )
        return

    await update.message.reply_text(f"Buscando el clima en {ciudad} para {dia}... 🌤️")

    try:
        resultado = weather_helper.obtener_clima(ciudad, dia=dia)
    except Exception:
        logger.exception("Error al obtener clima")
        await update.message.reply_text(
            "⚠️ Tuve un problema consultando el clima. Revisá la terminal para más detalle."
        )
        return

    if not resultado:
        await update.message.reply_text(f"No encontré la ciudad '{ciudad}'. Probá con otro nombre.")
        return

    descripcion = weather_helper.descripcion_clima(resultado["codigo_clima"])

    if resultado["tipo"] == "pronostico":
        texto = (
            f"📍 *{resultado['ciudad']}, {resultado['provincia']}* — mañana ({resultado['fecha']})\n"
            f"{descripcion}\n"
            f"🌡️ Máxima: {resultado['temp_max']}°C / Mínima: {resultado['temp_min']}°C"
        )
    else:
        texto = (
            f"📍 *{resultado['ciudad']}, {resultado['provincia']}*\n"
            f"{descripcion}\n"
            f"🌡️ Temperatura: {resultado['temperatura']}°C\n"
            f"💧 Humedad: {resultado['humedad']}%\n"
            f"💨 Viento: {resultado['viento']} km/h"
        )

    await update.message.reply_text(texto, parse_mode="Markdown")


def _formatear_fecha(fecha_iso):
    if not fecha_iso:
        return "(sin fecha)"
    return fecha_iso.replace("T", " ")[:16]


async def agenda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Un segundo, reviso tu agenda... 📅\n"
        "(Si es la primera vez, revisá la terminal — puede pedirte volver a autorizar)"
    )

    texto = ""

    try:
        eventos_google = google_calendar_helper.obtener_proximos_eventos(cantidad=5)
        texto += "*Google Calendar:*\n"
        if eventos_google:
            for e in eventos_google:
                texto += f"• {_formatear_fecha(e['inicio'])} — {e['titulo']}\n"
        else:
            texto += "Sin eventos próximos.\n"
    except RuntimeError as e:
        texto += f"⚠️ Google Calendar: {e}\n"
    except Exception:
        logger.exception("Error al leer Google Calendar")
        texto += "⚠️ Tuve un problema con Google Calendar.\n"

    texto += "\n"

    try:
        eventos_outlook = outlook_helper.obtener_proximos_eventos(cantidad=5)
        texto += "*Outlook Calendar:*\n"
        if eventos_outlook:
            for e in eventos_outlook:
                texto += f"• {_formatear_fecha(e['inicio'])} — {e['titulo']}\n"
        else:
            texto += "Sin eventos próximos.\n"
    except RuntimeError as e:
        texto += f"⚠️ Outlook Calendar: {e}\n"
    except Exception:
        logger.exception("Error al leer Outlook Calendar")
        texto += "⚠️ Tuve un problema con Outlook Calendar.\n"

    await update.message.reply_text(texto, parse_mode="Markdown")


async def mensaje_voz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notas de voz: se transcriben con Whisper y después se procesan igual que un mensaje de texto."""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    voz = update.message.voice or update.message.audio
    if not voz:
        return

    archivo = await context.bot.get_file(voz.file_id)
    tmp = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
    ruta_tmp = tmp.name
    tmp.close()
    await archivo.download_to_drive(ruta_tmp)

    try:
        texto = voice_helper.transcribir(ruta_tmp)
    except Exception:
        logger.exception("Error transcribiendo audio")
        await update.message.reply_text(
            "⚠️ No pude transcribir el audio. Probá de nuevo o escribime el mensaje."
        )
        return
    finally:
        try:
            os.remove(ruta_tmp)
        except OSError:
            pass

    if not texto:
        await update.message.reply_text("No entendí nada en el audio 🤔 ¿Podés repetirlo?")
        return

    await update.message.reply_text(f"🎙️ Escuché: \"{texto}\"")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        respuesta = agent_helper.responder(texto)
    except Exception:
        logger.exception("Error en el agente conversacional")
        respuesta = (
            "⚠️ Tuve un problema pensando la respuesta. Revisá los logs de Railway para más detalle."
        )

    await update.message.reply_text(respuesta)


async def mensaje_libre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cualquier mensaje que no sea un comando se lo pasamos a Jony para que decida qué hacer."""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        respuesta = agent_helper.responder(update.message.text)
    except Exception:
        logger.exception("Error en el agente conversacional")
        respuesta = (
            "⚠️ Tuve un problema pensando la respuesta. Revisá la terminal para más detalle "
            "(puede ser que falte la ANTHROPIC_API_KEY en el .env)."
        )

    await update.message.reply_text(respuesta)


def main() -> None:
    if not TOKEN:
        raise RuntimeError(
            "No encontré TELEGRAM_BOT_TOKEN. Revisá que el archivo .env esté en esta carpeta."
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("correos", correos))
    app.add_handler(CommandHandler("outlook", outlook))
    app.add_handler(CommandHandler("clima", clima))
    app.add_handler(CommandHandler("agenda", agenda))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje_libre))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, mensaje_voz))

    logger.info("Jony está arrancando...")
    app.run_polling()


if __name__ == "__main__":
    main()
