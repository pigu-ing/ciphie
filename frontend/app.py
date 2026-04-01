"""
frontend/app.py — Interfaz de escritorio de Ciphie con Tkinter (stdlib).
"""

import json
import re
import subprocess
import sys
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import auth, crypto
from app.database import (
    agregar_secreto, editar_secreto, eliminar_secreto, inicializar_bd,
    listar_auditoria, listar_secretos, listar_usuarios_basico, listar_versiones,
    obtener_secreto, registrar_auditoria, restaurar_version,
    secretos_por_vencer, secretos_vencidos,
)

inicializar_bd()

# QR code support (opcional — instalar con: pip install qrcode[pil])
try:
    import qrcode
    from io import BytesIO
    from PIL import Image, ImageTk
    _QR_OK = True
except ImportError:
    _QR_OK = False

# Logo de la aplicacion
_LOGO_PATH = Path(__file__).resolve().parent / "public" / "▌.png"

# Tiempo de inactividad antes de cerrar sesion automaticamente (ms)
INACTIVITY_TIMEOUT_MS = 10 * 60 * 1000  # 10 minutos

# ---------------------------------------------------------------------------
# Paleta de colores
# ---------------------------------------------------------------------------
BG         = "#0d1117"
BG_PANEL   = "#161b22"
BG_ENTRY   = "#1c2128"
BORDER     = "#30363d"
FG         = "#e6edf3"
FG_DIM     = "#7d8590"
ACCENT     = "#3fb950"
DANGER     = "#f85149"
AMARILLO   = "#d29922"
CURSOR_COL = "#58a6ff"
BTN_COLOR  = "#8b949e"
BTN_OSCURO = "#21262d"

FONT       = ("Courier New", 14)
FONT_GRANDE= ("Courier New", 24, "bold")
FONT_MONO  = ("Courier New", 13)
FONT_SMALL = ("Courier New", 12)
FONT_TINY  = ("Courier New", 11)
PAD        = 20

CATEGORIAS = ["contrasena", "tarjeta", "api key", "token", "nota", "env", "otro"]

# Colores de categoria
CAT_COLORS = {
    "contrasena": "#3fb950",
    "tarjeta":    "#f78166",
    "api key":    "#58a6ff",
    "token":      "#d29922",
    "nota":       "#bc8cff",
    "env":        "#79c0ff",
    "otro":       "#7d8590",
}

# Campos por tipo de secreto
PLANTILLAS_CAMPOS = {
    "contrasena": [
        {"nombre": "usuario",    "tipo": "text",     "requerido": False},
        {"nombre": "contrasena", "tipo": "password",  "requerido": True},
        {"nombre": "url",        "tipo": "text",     "requerido": False},
        {"nombre": "notas",      "tipo": "text",     "requerido": False},
    ],
    "tarjeta": [
        {"nombre": "numero",      "tipo": "text",    "requerido": True},
        {"nombre": "titular",     "tipo": "text",    "requerido": True},
        {"nombre": "expiracion",  "tipo": "text",    "requerido": True},
        {"nombre": "cvv",         "tipo": "password","requerido": True},
        {"nombre": "banco",       "tipo": "text",    "requerido": False},
    ],
    "api key": [
        {"nombre": "clave",     "tipo": "password", "requerido": True},
        {"nombre": "endpoint",  "tipo": "text",    "requerido": False},
        {"nombre": "notas",     "tipo": "text",    "requerido": False},
    ],
    "token": [
        {"nombre": "token",    "tipo": "password", "requerido": True},
        {"nombre": "servicio", "tipo": "text",    "requerido": False},
        {"nombre": "notas",    "tipo": "text",    "requerido": False},
    ],
    "nota": [
        {"nombre": "contenido", "tipo": "textarea", "requerido": True},
    ],
    "env": [
        {"nombre": "contenido", "tipo": "textarea", "requerido": True},
    ],
    "otro": [
        {"nombre": "valor", "tipo": "password", "requerido": True},
        {"nombre": "notas", "tipo": "text",    "requerido": False},
    ],
}


def _parsear_valor(valor_descifrado: str) -> dict:
    """
    Interpreta el valor descifrado.
    - Si es JSON con __type='multi': devuelve {'tipo':'multi','campos':{...}}
    - Si no: devuelve {'tipo':'simple','valor':'...'}
    """
    try:
        data = json.loads(valor_descifrado)
        if isinstance(data, dict) and data.get("__type") == "multi":
            return {"tipo": "multi", "campos": data.get("campos", {})}
    except (json.JSONDecodeError, TypeError):
        pass
    return {"tipo": "simple", "valor": valor_descifrado}


def _serializar_campos(campos: dict) -> str:
    """Serializa un dict de campos a JSON para cifrar."""
    return json.dumps({"__type": "multi", "campos": campos}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Widgets reutilizables
# ---------------------------------------------------------------------------

def _separador(parent) -> tk.Frame:
    return tk.Frame(parent, height=1, bg=BORDER)


def _configurar_ttk() -> None:
    s = ttk.Style()
    s.theme_use("default")
    s.configure("Vertical.TScrollbar",
        background=BG_PANEL, troughcolor=BG, arrowcolor=FG_DIM,
        relief="flat", borderwidth=0,
    )
    s.map("Vertical.TScrollbar", background=[("active", BORDER)])


def _entry(parent, **kwargs) -> tk.Entry:
    return tk.Entry(
        parent, font=FONT, bg=BG_ENTRY, fg=FG,
        insertbackground=ACCENT, selectbackground=CURSOR_COL, selectforeground=FG,
        relief="flat", highlightthickness=1,
        highlightbackground=BORDER, highlightcolor=ACCENT,
        **kwargs,
    )


def _boton(parent, texto, comando, color=BTN_COLOR, fg_text="#0d1117", **kwargs) -> tk.Label:
    """Botón principal (Label, para respetar bg en macOS)."""
    btn = tk.Label(parent, text=texto, font=FONT_SMALL, bg=color, fg=fg_text,
                   cursor="hand2", **kwargs)
    btn.bind("<Button-1>", lambda e: comando())
    btn.bind("<Enter>",    lambda e: btn.configure(bg=FG))
    btn.bind("<Leave>",    lambda e: btn.configure(bg=color))
    return btn


def _boton_oscuro(parent, texto, comando, fg=FG_DIM, **kwargs) -> tk.Label:
    """Botón gris oscuro para uso en paneles/diálogos."""
    btn = tk.Label(parent, text=texto, font=FONT_SMALL, bg=BTN_OSCURO, fg=fg,
                   cursor="hand2", padx=8, pady=3, **kwargs)
    btn.bind("<Button-1>", lambda e: comando())
    btn.bind("<Enter>",    lambda e: btn.configure(bg=BORDER))
    btn.bind("<Leave>",    lambda e: btn.configure(bg=BTN_OSCURO))
    return btn


def _entry_password(parent) -> "tuple[tk.Frame, tk.Entry]":
    """Campo contrasena con candado 🔒/🔓."""
    frame = tk.Frame(parent, bg=BG_ENTRY,
                     highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
    entry = tk.Entry(frame, font=FONT, bg=BG_ENTRY, fg=FG,
                     insertbackground=ACCENT, selectbackground=CURSOR_COL, selectforeground=FG,
                     relief="flat", bd=0, show="●")
    entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(6, 0))

    _visible = [False]

    def _toggle():
        if _visible[0]:
            entry.configure(show="●")
            btn.configure(text="🔒", fg=FG_DIM)
        else:
            entry.configure(show="")
            btn.configure(text="🔓", fg=ACCENT)
        _visible[0] = not _visible[0]

    btn = tk.Button(frame, text="🔒", font=("Courier New", 12),
                    bg="black", fg=FG_DIM, activebackground="#111", activeforeground=FG,
                    relief="flat", cursor="hand2", bd=0, highlightbackground="black",
                    command=_toggle)
    btn.pack(side="right", padx=(0, 6))
    return frame, entry


def _label(parent, texto, font=None, fg=FG, bg=BG, **kwargs) -> tk.Label:
    return tk.Label(parent, text=texto, font=font or FONT_SMALL, fg=fg, bg=bg, **kwargs)


# ---------------------------------------------------------------------------
# Touch ID (macOS)
# ---------------------------------------------------------------------------

def _touch_id_disponible() -> bool:
    if sys.platform != "darwin":
        return False
    script = (
        "import sys\n"
        "try:\n"
        "    from LocalAuthentication import LAContext, LAPolicyDeviceOwnerAuthenticationWithBiometrics\n"
        "    ctx = LAContext()\n"
        "    ok, _ = ctx.canEvaluatePolicy_error_(LAPolicyDeviceOwnerAuthenticationWithBiometrics, None)\n"
        "    sys.exit(0 if ok else 1)\n"
        "except ImportError: sys.exit(2)\n"
        "except Exception: sys.exit(1)\n"
    )
    try:
        return subprocess.run([sys.executable, "-c", script], timeout=5, capture_output=True).returncode == 0
    except Exception:
        return False


def _verificar_touch_id() -> bool:
    script = (
        "import sys\n"
        "try:\n"
        "    from Foundation import NSRunLoop, NSDate\n"
        "    from LocalAuthentication import LAContext, LAPolicyDeviceOwnerAuthenticationWithBiometrics\n"
        "    ctx = LAContext()\n"
        "    result = [None]\n"
        "    def cb(ok, _): result[0] = bool(ok)\n"
        "    ctx.evaluatePolicy_localizedReason_reply_(\n"
        "        LAPolicyDeviceOwnerAuthenticationWithBiometrics,\n"
        "        'Verificar identidad para Ciphie', cb)\n"
        "    for _ in range(300):\n"
        "        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))\n"
        "        if result[0] is not None: break\n"
        "    sys.exit(0 if result[0] else 1)\n"
        "except ImportError: sys.exit(3)\n"
        "except Exception: sys.exit(1)\n"
    )
    try:
        return subprocess.run([sys.executable, "-c", script], timeout=35, capture_output=True).returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Internacionalización (i18n)
# ---------------------------------------------------------------------------
_LANG = ["es"]

TEXTOS: dict = {
    "es": {
        # login
        "subtitulo": "[ secrets manager ]",
        "usuario_lbl": "usuario:", "contrasena_lbl": "contraseña:",
        "entrar": "> entrar", "no_cuenta": "¿no tienes cuenta?",
        "registrarse": "[ registrarse ]",
        "campos_vacios": "campos vacíos", "completa_campos": "completa todos los campos.",
        "acceso_denegado": "acceso denegado",
        "usuario_pass_incorrectos": "usuario o contraseña incorrectos.",
        # registro
        "crear_cuenta_titulo": "crear cuenta", "nuevo_usuario_tag": "[ nuevo usuario ]",
        "ya_tengo_cuenta": "[ ya tengo cuenta ]", "crear_cuenta_btn": "> crear cuenta",
        "campos_obligatorios": "completa todos los campos obligatorios.",
        "contrasenas_error": "las contraseñas no coinciden.",
        "contrasenas_no_coinciden": "✗ las contraseñas no coinciden",
        "contrasenas_coinciden": "✓ las contraseñas coinciden",
        "cuenta_creada": "cuenta creada",
        "cuenta_creada_msg": "Cuenta creada.\n(SMTP no configurado — activada sin verificación.)\nInicia sesión.",
        # verificación
        "verificar_cuenta": "verificar cuenta", "cod_activacion": "[ código de activación ]",
        "enviado_email": "Te enviamos un código a tu email\n(y celular si lo ingresaste).",
        "codigo_lbl": "código:", "verificar_activar": "> verificar y activar cuenta",
        "reenviar_codigo": "[ reenviar código ]", "volver": "[ volver ]",
        "vacio": "vacío", "ingresa_codigo": "ingresa el código.",
        "codigo_invalido": "código inválido", "codigo_expirado": "el código es incorrecto o ya expiró.",
        "cuenta_activada": "¡Cuenta activa! Inicia sesión.",
        "enviado": "enviado", "nuevo_codigo_enviado": "nuevo código enviado.",
        # 2FA screens
        "verificacion": "verificación",
        "elige_verificacion": "[ elegí cómo verificar tu identidad ]",
        "touch_id_configurado": "[Touch ID]  huella digital (método configurado)",
        "correo_2fa": "correo  — código por email",
        "celular_2fa": "celular  — código por SMS",
        "app_totp": "app autenticadora  — TOTP",
        "touch_id_btn": "[Touch ID]  huella digital",
        "sin_metodos": "No hay métodos configurados.\nConfigura SMTP en .env para email.",
        "volver_login": "[ volver al login ]",
        "touch_id_fallo": "verificación biométrica fallida o cancelada.",
        "codigo_enviado_email": "código enviado a tu email:",
        "revisa_bandeja": "revisa tu bandeja (expira en 5 min)",
        "codigo_enviado_celular": "código enviado a tu celular:",
        "revisa_mensajes": "revisa tus mensajes (expira en 5 min)",
        "codigo_totp": "código de tu app autenticadora:",
        "app_hint": "(Google Authenticator, Authy, etc.)",
        "verificar_codigo": "> verificar código",
        "elegir_otro": "[ elegir otro método ]",
        "codigo_invalido2": "incorrecto o expirado.",
        "error_enviar_codigo": "error al enviar código",
        # sidebar / nav
        "nav_inicio": "🏠  inicio", "nav_nuevo": "➕  nuevo",
        "nav_secretos": "🔒  secretos", "nav_actividad": "📋  actividad",
        "nav_usuario": "👤  usuario", "nav_salir": "[ salir ]",
        "cambiar_idioma": "EN",
        # bienvenida
        "bienvenido": "¡Hola, bienvenido", "bienvenido_sub": "Seleccioná a dónde querés ir desde el menú de la izquierda.",
        # nuevo secreto
        "nuevo_secreto": "nuevo secreto", "agrega_secreto": "agrega un secreto a tu bóveda",
        "nombre_lbl": "nombre:", "categoria_lbl": "categoría:", "expira_lbl": "expira en:",
        "guardar_secreto": "> guardar secreto",
        "campo_vacio": "campo vacío", "ingresa_nombre": "ingresa un nombre.",
        "nunca": "nunca", "dias_30": "30 días", "dias_60": "60 días", "dias_90": "90 días",
        "personalizada": "personalizada", "sin_cambio": "sin cambio",
        "fecha_invalida": "fecha inválida", "formato_fecha": "usa el formato AAAA-MM-DD.",
        # secretos lista
        "secretos_guardados": "secretos guardados", "no_secretos": "no hay secretos guardados.",
        "renovar": "renovar",
        # perfil
        "perfil": "perfil", "seguridad": "seguridad", "cuentas": "cuentas",
        "editar_perfil": "editar perfil", "config_2fa": "> configurar 2FA",
        "nueva_cuenta_btn": "> nueva cuenta", "cambiar_cuenta": "cambiar cuenta",
        "editar_perfil_titulo": "editar perfil",
        "nuevo_usuario_hint": "nuevo usuario (vacío = no cambiar):",
        "nuevo_email_hint": "nuevo email (vacío = no cambiar):",
        "perfil_actualizado": "Perfil actualizado.",
        "nueva_cuenta_titulo": "nueva cuenta",
        "cuenta_ok": "@{username} creado correctamente.",
        "cambiar_cuenta_titulo": "cambiar cuenta",
        "no_otras_cuentas": "no hay otras cuentas.",
        "seleccionar_cuenta": "seleccionar cuenta:",
        "ingresa_contrasena": "ingresa la contraseña.",
        "contrasena_incorrecta": "contraseña incorrecta.",
        "frase_recuperacion": "frase de recuperación:",
        # actividad
        "actividad": "actividad", "historial_acciones": "historial de acciones",
        "sin_actividad": "sin actividad registrada.",
        # modales comunes
        "ok_btn": "> ok", "cancelar": "cancelar", "si_btn": "> sí",
        "cerrar": "cerrar", "guardar_cambios": "> guardar cambios", "confirmar": "confirmar",
        "error": "error",
        # secretos acciones
        "copiar_campo_titulo": "copiar campo — {name}",
        "copiar_todo_env": "> copiar todo (.env)",
        "copiado": "copiado", "copiado_msg": '"{name}" en portapapeles.\nse borrará en 30 s.',
        "eliminar_confirmar": '¿eliminar "{name}"?\nno se puede deshacer.',
        "editar_secreto": "editar secreto", "valores_lbl": "valores:",
        "editar_error": "no se pudo editar el secreto.",
        "historial_secreto": "historial: {name}",
        "versiones": "{n} versión(es) anterior(es)",
        "sin_historial": "sin historial — este secreto no ha sido editado.",
        "restaurar_btn": "restaurar",
        "restaurar_confirmar": "¿restaurar esta versión?\nEl valor actual quedará guardado en el historial.",
        "restaurar_error": "no se pudo restaurar.",
        "ver_valor": "valor:",
        # 2FA config
        "2fa_titulo": "autenticación de 2 pasos",
        "2fa_activado_estado": "activado ({method})",
        "2fa_desactivado_estado": "desactivado",
        "desactivar_2fa": "> desactivar 2FA",
        "2fa_desactivado_ok": "2FA desactivado.",
        "elegir_metodo": "elegir método:",
        "app_autenticadora_btn": "> app autenticadora",
        "email_2fa_btn": "> email  ({email})",
        "email_no_disponible": "email no disponible (SMTP no configurado)",
        "touch_id_ok": "Huella digital configurada como 2FA.",
        "verificacion_fallo": "verificación biométrica fallida.",
        "2fa_email_ok": "Códigos a:\n{email}",
        # TOTP
        "config_totp": "configurar app autenticadora",
        "escanear_qr": "Escaneá con tu app autenticadora",
        "totp_pasos": ["1. Abre tu app (Google Auth, Authy, etc.)",
                       "2. Pulsa '+' → 'ingresar clave manual'",
                       "3. Copia el secreto de abajo y pegalo",
                       "4. Ingresa el código que te muestra"],
        "secreto_lbl": "secreto:", "cod_verificacion_lbl": "código de verificación:",
        "confirmar_activar": "> confirmar y activar",
        "cod_no_coincide": "el código no coincide.", "incorrecto": "incorrecto",
        "totp_activado": "app autenticadora configurada.",
        # sesión
        "sesion_expirada": "sesión expirada",
        "sesion_expiro": "Tu sesión expiró por inactividad (10 min).",
        # fortaleza
        "muy_debil": "muy débil", "debil": "débil", "media": "media", "fuerte": "fuerte",
        # verificar 2fa antes de
        "verificar_identidad": "verificar identidad",
        "ingresa_cod_app": "ingresa el código de tu app autenticadora:",
        "verificar_btn": "> verificar",
        "ingresa_cod_email": "ingresa el código enviado a tu email:",
        "cod_incorrecto": "código incorrecto.",
        # errores
        "error_cifrado": "error de cifrado", "error_al_guardar": "error al guardar",
        # login screen labels
        "email_lbl": "email:", "celular_lbl": "celular (opcional):",
        "confirmar_contrasena_lbl": "confirmar contraseña:",
        # popup secreto
        "copiar_btn": "copiar", "editar_btn": "editar",
        "historial_btn": "historial", "eliminar_btn": "eliminar",
        # lista secretos
        "copiar_titulo": "copiar — {name}",
        "vencidos_banner": "🔴  {n} secreto(s) vencido(s)",
        # perfil
        "estado_lbl": "estado", "usuario_tag": "usuario", "email_tag": "email",
        # fecha placeholder
        "fecha_placeholder": "AAAA-MM-DD",
        # criterios barra contraseña
        "criterio_len": "12+ chars", "criterio_case": "may/min",
        "criterio_num": "números", "criterio_special": "símbolos",
        "simbolo_invalido": "(Este símbolo no está permitido)",
        # nombres de categorías
        "cat_contrasena": "contraseña", "cat_tarjeta": "tarjeta", "cat_api_key": "api key",
        "cat_token": "token", "cat_nota": "nota", "cat_env": "env", "cat_otro": "otro",
        # nombres de campos
        "campo_usuario": "usuario", "campo_contrasena": "contraseña", "campo_url": "url",
        "campo_notas": "notas", "campo_numero": "número", "campo_titular": "titular",
        "campo_expiracion": "expiración", "campo_cvv": "cvv", "campo_banco": "banco",
        "campo_clave": "clave", "campo_endpoint": "endpoint", "campo_token": "token",
        "campo_servicio": "servicio", "campo_contenido": "contenido", "campo_valor": "valor",
    },
    "en": {
        "subtitulo": "[ secrets manager ]",
        "usuario_lbl": "username:", "contrasena_lbl": "password:",
        "entrar": "> sign in", "no_cuenta": "don't have an account?",
        "registrarse": "[ register ]",
        "campos_vacios": "empty fields", "completa_campos": "please fill in all fields.",
        "acceso_denegado": "access denied",
        "usuario_pass_incorrectos": "incorrect username or password.",
        "crear_cuenta_titulo": "create account", "nuevo_usuario_tag": "[ new user ]",
        "ya_tengo_cuenta": "[ already have an account ]", "crear_cuenta_btn": "> create account",
        "campos_obligatorios": "please fill in all required fields.",
        "contrasenas_error": "passwords do not match.",
        "contrasenas_no_coinciden": "✗ passwords do not match",
        "contrasenas_coinciden": "✓ passwords match",
        "cuenta_creada": "account created",
        "cuenta_creada_msg": "Account created.\n(SMTP not configured — activated without email verification.)\nSign in now.",
        "verificar_cuenta": "verify account", "cod_activacion": "[ activation code ]",
        "enviado_email": "We sent a code to your email\n(and phone if you entered one).",
        "codigo_lbl": "code:", "verificar_activar": "> verify and activate account",
        "reenviar_codigo": "[ resend code ]", "volver": "[ back ]",
        "vacio": "empty", "ingresa_codigo": "enter the code.",
        "codigo_invalido": "invalid code", "codigo_expirado": "the code is incorrect or has expired.",
        "cuenta_activada": "Account active! Sign in now.",
        "enviado": "sent", "nuevo_codigo_enviado": "new code sent.",
        "verificacion": "verification",
        "elige_verificacion": "[ choose how to verify your identity ]",
        "touch_id_configurado": "[Touch ID]  fingerprint (configured method)",
        "correo_2fa": "email  — code by email", "celular_2fa": "phone  — code by SMS",
        "app_totp": "authenticator app  — TOTP", "touch_id_btn": "[Touch ID]  fingerprint",
        "sin_metodos": "No methods configured.\nConfigure SMTP in .env for email.",
        "volver_login": "[ back to login ]",
        "touch_id_fallo": "biometric verification failed or cancelled.",
        "codigo_enviado_email": "code sent to your email:",
        "revisa_bandeja": "check your inbox (expires in 5 min)",
        "codigo_enviado_celular": "code sent to your phone:",
        "revisa_mensajes": "check your messages (expires in 5 min)",
        "codigo_totp": "code from your authenticator app:",
        "app_hint": "(Google Authenticator, Authy, etc.)",
        "verificar_codigo": "> verify code", "elegir_otro": "[ choose another method ]",
        "codigo_invalido2": "incorrect or expired.", "error_enviar_codigo": "error sending code",
        "nav_inicio": "🏠  home", "nav_nuevo": "➕  new",
        "nav_secretos": "🔒  secrets", "nav_actividad": "📋  activity",
        "nav_usuario": "👤  profile", "nav_salir": "[ sign out ]",
        "cambiar_idioma": "ES",
        "bienvenido": "Hello, welcome", "bienvenido_sub": "Select where you want to go from the left menu.",
        "nuevo_secreto": "new secret", "agrega_secreto": "add a secret to your vault",
        "nombre_lbl": "name:", "categoria_lbl": "category:", "expira_lbl": "expires in:",
        "guardar_secreto": "> save secret",
        "campo_vacio": "empty field", "ingresa_nombre": "enter a name.",
        "nunca": "never", "dias_30": "30 days", "dias_60": "60 days", "dias_90": "90 days",
        "personalizada": "custom", "sin_cambio": "no change",
        "fecha_invalida": "invalid date", "formato_fecha": "use format YYYY-MM-DD.",
        "secretos_guardados": "saved secrets", "no_secretos": "no secrets saved.",
        "renovar": "renew",
        "perfil": "profile", "seguridad": "security", "cuentas": "accounts",
        "editar_perfil": "edit profile", "config_2fa": "> configure 2FA",
        "nueva_cuenta_btn": "> new account", "cambiar_cuenta": "switch account",
        "editar_perfil_titulo": "edit profile",
        "nuevo_usuario_hint": "new username (empty = no change):",
        "nuevo_email_hint": "new email (empty = no change):",
        "perfil_actualizado": "Profile updated.",
        "nueva_cuenta_titulo": "new account",
        "cuenta_ok": "@{username} created successfully.",
        "cambiar_cuenta_titulo": "switch account",
        "no_otras_cuentas": "no other accounts.",
        "seleccionar_cuenta": "select account:",
        "ingresa_contrasena": "enter password.",
        "contrasena_incorrecta": "incorrect password.",
        "frase_recuperacion": "recovery phrase:",
        "actividad": "activity", "historial_acciones": "action history",
        "sin_actividad": "no activity recorded.",
        "ok_btn": "> ok", "cancelar": "cancel", "si_btn": "> yes",
        "cerrar": "close", "guardar_cambios": "> save changes", "confirmar": "confirm",
        "error": "error",
        "copiar_campo_titulo": "copy field — {name}",
        "copiar_todo_env": "> copy all (.env)",
        "copiado": "copied", "copiado_msg": '"{name}" in clipboard.\nwill be cleared in 30s.',
        "eliminar_confirmar": 'delete "{name}"?\nthis cannot be undone.',
        "editar_secreto": "edit secret", "valores_lbl": "values:",
        "editar_error": "could not edit secret.",
        "historial_secreto": "history: {name}",
        "versiones": "{n} previous version(s)",
        "sin_historial": "no history — this secret has never been edited.",
        "restaurar_btn": "restore",
        "restaurar_confirmar": "Restore this version?\nThe current value will be saved to history.",
        "restaurar_error": "could not restore.",
        "ver_valor": "value:",
        "2fa_titulo": "two-step authentication",
        "2fa_activado_estado": "enabled ({method})",
        "2fa_desactivado_estado": "disabled",
        "desactivar_2fa": "> disable 2FA",
        "2fa_desactivado_ok": "2FA disabled.",
        "elegir_metodo": "choose method:",
        "app_autenticadora_btn": "> authenticator app",
        "email_2fa_btn": "> email  ({email})",
        "email_no_disponible": "email unavailable (SMTP not configured)",
        "touch_id_ok": "Fingerprint configured as 2FA.",
        "verificacion_fallo": "biometric verification failed.",
        "2fa_email_ok": "Codes to:\n{email}",
        "config_totp": "configure authenticator app",
        "escanear_qr": "Scan with your authenticator app",
        "totp_pasos": ["1. Open your app (Google Auth, Authy, etc.)",
                       "2. Tap '+' → 'enter key manually'",
                       "3. Copy the secret below and paste it",
                       "4. Enter the code shown by the app"],
        "secreto_lbl": "secret:", "cod_verificacion_lbl": "verification code:",
        "confirmar_activar": "> confirm and activate",
        "cod_no_coincide": "code does not match.", "incorrecto": "incorrect",
        "totp_activado": "authenticator app configured.",
        "sesion_expirada": "session expired",
        "sesion_expiro": "Your session expired due to inactivity (10 min).",
        "muy_debil": "very weak", "debil": "weak", "media": "medium", "fuerte": "strong",
        "verificar_identidad": "verify identity",
        "ingresa_cod_app": "enter the code from your authenticator app:",
        "verificar_btn": "> verify",
        "ingresa_cod_email": "enter the code sent to your email:",
        "cod_incorrecto": "incorrect code.",
        "error_cifrado": "encryption error", "error_al_guardar": "save error",
        # login screen labels
        "email_lbl": "email:", "celular_lbl": "phone (optional):",
        "confirmar_contrasena_lbl": "confirm password:",
        # popup secreto
        "copiar_btn": "copy", "editar_btn": "edit",
        "historial_btn": "history", "eliminar_btn": "delete",
        # lista secretos
        "copiar_titulo": "copy — {name}",
        "vencidos_banner": "🔴  {n} expired secret(s)",
        # perfil
        "estado_lbl": "status", "usuario_tag": "username", "email_tag": "email",
        # fecha placeholder
        "fecha_placeholder": "YYYY-MM-DD",
        # criterios barra contraseña
        "criterio_len": "12+ chars", "criterio_case": "upper/lower",
        "criterio_num": "numbers", "criterio_special": "symbols",
        "simbolo_invalido": "(This symbol is not allowed)",
        # category names
        "cat_contrasena": "password", "cat_tarjeta": "card", "cat_api_key": "api key",
        "cat_token": "token", "cat_nota": "note", "cat_env": "env", "cat_otro": "other",
        # field names
        "campo_usuario": "username", "campo_contrasena": "password", "campo_url": "url",
        "campo_notas": "notes", "campo_numero": "number", "campo_titular": "cardholder",
        "campo_expiracion": "expiration", "campo_cvv": "cvv", "campo_banco": "bank",
        "campo_clave": "key", "campo_endpoint": "endpoint", "campo_token": "token",
        "campo_servicio": "service", "campo_contenido": "content", "campo_valor": "value",
    },
}


def T(key: str, **kwargs) -> str:
    texto = TEXTOS.get(_LANG[0], TEXTOS["es"]).get(key, TEXTOS["es"].get(key, key))
    if kwargs:
        try:
            texto = texto.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return texto


def TC(cat: str) -> str:
    """Traduce el nombre interno de una categoría para mostrar en la UI."""
    return T("cat_" + cat.replace(" ", "_"))


def TF(field: str) -> str:
    """Traduce el nombre interno de un campo para mostrar como etiqueta."""
    return T("campo_" + field)


def _cat_key(display: str) -> str:
    """Convierte el nombre de categoría mostrado (traducido) al key interno en español."""
    for cat in CATEGORIAS:
        if TC(cat) == display:
            return cat
    return display  # fallback: si no matchea, devuelve tal cual


# ---------------------------------------------------------------------------
# Helpers de modal (reemplazan messagebox)
# ---------------------------------------------------------------------------

def _modal_msg(parent_frame: tk.Widget, titulo: str, mensaje: str, tipo: str = "info", on_cerrar=None):
    """Muestra un mensaje como modal sobre parent_frame."""
    colores = {"info": ACCENT, "warning": AMARILLO, "error": DANGER}
    color = colores.get(tipo, ACCENT)
    overlay = tk.Frame(parent_frame, bg="#0a0e14")
    overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
    box = tk.Frame(overlay, bg=BG_PANEL, padx=28, pady=22,
                   highlightthickness=1, highlightbackground=BORDER)
    box.place(relx=0.5, rely=0.5, anchor="center")
    tk.Label(box, text=titulo, font=("Courier New", 13, "bold"), fg=color, bg=BG_PANEL).pack(anchor="w")
    tk.Frame(box, height=1, bg=BORDER).pack(fill="x", pady=8)
    tk.Label(box, text=mensaje, font=FONT_SMALL, fg=FG, bg=BG_PANEL,
             wraplength=320, justify="left").pack(anchor="w", pady=(0, 12))
    def _cerrar():
        overlay.destroy()
        if on_cerrar:
            on_cerrar()
    _boton(box, T("ok_btn"), _cerrar).pack(fill="x", ipady=5)
    overlay.lift()


def _modal_confirmar(parent_frame: tk.Widget, titulo: str, mensaje: str, on_si, on_no=None):
    """Muestra una confirmación Sí/No como modal sobre parent_frame."""
    overlay = tk.Frame(parent_frame, bg="#0a0e14")
    overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
    box = tk.Frame(overlay, bg=BG_PANEL, padx=28, pady=22,
                   highlightthickness=1, highlightbackground=BORDER)
    box.place(relx=0.5, rely=0.5, anchor="center")
    tk.Label(box, text=titulo, font=("Courier New", 13, "bold"), fg=AMARILLO, bg=BG_PANEL).pack(anchor="w")
    tk.Frame(box, height=1, bg=BORDER).pack(fill="x", pady=8)
    tk.Label(box, text=mensaje, font=FONT_SMALL, fg=FG, bg=BG_PANEL,
             wraplength=320, justify="left").pack(anchor="w", pady=(0, 12))
    def _si():
        overlay.destroy()
        on_si()
    def _no():
        overlay.destroy()
        if on_no:
            on_no()
    fila = tk.Frame(box, bg=BG_PANEL)
    fila.pack(fill="x")
    _boton(fila, T("si_btn"), _si, color=DANGER).pack(side="left", fill="x", expand=True, ipady=5)
    _boton_oscuro(fila, T("cancelar"), _no).pack(side="left", padx=(8, 0), fill="x", expand=True, ipady=5)
    overlay.lift()


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------

class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        _configurar_ttk()
        self.title("ciphie — secrets manager")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.eval("tk::PlaceWindow . center")
        if _QR_OK and _LOGO_PATH.exists():
            _icon = ImageTk.PhotoImage(Image.open(_LOGO_PATH).resize((64, 64), Image.LANCZOS))
            self.iconphoto(True, _icon)
            self._logo_icon = _icon  # mantener referencia
        self.ir_a_login()

    def _limpiar(self):
        for w in self.winfo_children():
            w.destroy()

    def ir_a_login(self):
        self.geometry("540x620")
        self._limpiar()
        PantallaLogin(self).pack(fill="both", expand=True)

    def ir_a_registro(self):
        self.geometry("540x720")
        self._limpiar()
        PantallaRegistro(self).pack(fill="both", expand=True)

    def ir_a_verificacion_registro(self, username: str):
        self.geometry("540x520")
        self._limpiar()
        PantallaVerificacionRegistro(self, username).pack(fill="both", expand=True)

    def ir_a_elegir_2fa(self, username: str):
        self.geometry("540x520")
        self._limpiar()
        PantallaElegir2FA(self, username).pack(fill="both", expand=True)

    def ir_a_2fa_codigo(self, username: str, method: str):
        self.geometry("540x480")
        self._limpiar()
        PantallaCodigo2FA(self, username, method).pack(fill="both", expand=True)

    def ir_a_dashboard(self, usuario: auth.Usuario):
        self.geometry("1060x640")
        self._limpiar()
        PantallaDashboard(self, usuario).pack(fill="both", expand=True)


# ---------------------------------------------------------------------------
# Pantalla de login
# ---------------------------------------------------------------------------

class PantallaLogin(tk.Frame):
    def __init__(self, app: Aplicacion):
        super().__init__(app, bg=BG, padx=PAD, pady=PAD)
        self.app = app
        self._construir()

    def _construir(self):
        tk.Label(self, text="ciphie", font=FONT_GRANDE, fg=ACCENT, bg=BG).pack(pady=(20, 0))
        tk.Label(self, text=T("subtitulo"), font=FONT_SMALL, fg=FG_DIM, bg=BG).pack(pady=(0, 4))
        _separador(self).pack(fill="x", pady=14)

        _label(self, T("usuario_lbl"), font=FONT_MONO, fg=FG_DIM, anchor="w").pack(fill="x")
        self._usuario = _entry(self)
        self._usuario.pack(fill="x", ipady=5, pady=(2, 10))
        self._usuario.focus_set()

        _label(self, T("contrasena_lbl"), font=FONT_MONO, fg=FG_DIM, anchor="w").pack(fill="x")
        _frm, self._password = _entry_password(self)
        _frm.pack(fill="x", pady=(2, 18))
        self._password.bind("<Return>", lambda _: self._login())

        _boton(self, T("entrar"), self._login).pack(fill="x", ipady=6)
        _separador(self).pack(fill="x", pady=14)
        tk.Label(self, text=T("no_cuenta"), font=FONT_SMALL, fg=FG_DIM, bg=BG).pack()
        btn = _boton(self, T("registrarse"), self.app.ir_a_registro, color=BG_ENTRY)
        btn.configure(fg=ACCENT)
        btn.pack(fill="x", ipady=4, pady=(4, 0))

    def _login(self):
        username = self._usuario.get().strip()
        password = self._password.get()
        if not username or not password:
            _modal_msg(self, T("campos_vacios"), T("completa_campos"), "warning")
            return
        try:
            estado, usuario = auth.autenticar_paso1(username, password)
        except Exception as e:
            _modal_msg(self, T("error"), str(e), "error")
            return
        if estado == "fallo":
            _modal_msg(self, T("acceso_denegado"), T("usuario_pass_incorrectos"), "error")
        elif estado == "ok":
            self.app.ir_a_dashboard(usuario)
        elif estado == "2fa_requerido":
            self.app.ir_a_elegir_2fa(username)


# ---------------------------------------------------------------------------
# Utilidad: seguridad de contrasena
# ---------------------------------------------------------------------------

def _calcular_seguridad(password: str) -> "tuple[int, str, str]":
    score = sum([
        len(password) >= 12,
        bool(re.search(r'[A-Z]', password) and re.search(r'[a-z]', password)),
        bool(re.search(r'\d', password)),
        bool(re.search(r'[!@#$%^&*()\-_=+\[\]{};:\'",.<>?/\\|`~]', password)),
    ])
    niveles = {0: ("", BORDER), 1: (T("muy_debil"), DANGER), 2: (T("debil"), AMARILLO),
               3: (T("media"), AMARILLO), 4: (T("fuerte"), ACCENT)}
    texto, color = niveles[score]
    return score, texto, color


# ---------------------------------------------------------------------------
# Pantalla de registro
# ---------------------------------------------------------------------------

class PantallaRegistro(tk.Frame):
    def __init__(self, app: Aplicacion):
        super().__init__(app, bg=BG, padx=PAD, pady=PAD)
        self.app = app
        self._construir()

    def _construir(self):
        tk.Label(self, text=T("crear_cuenta_titulo"), font=FONT_GRANDE, fg=ACCENT, bg=BG).pack(pady=(10, 0))
        tk.Label(self, text=T("nuevo_usuario_tag"), font=FONT_SMALL, fg=FG_DIM, bg=BG).pack()
        _separador(self).pack(fill="x", pady=12)

        campos = [
            (T("usuario_lbl"),               "Usuario",              False),
            (T("email_lbl"),                 "Email",                False),
            (T("celular_lbl"),               "Celular",              False),
            (T("contrasena_lbl"),            "Contrasena",           True),
            (T("confirmar_contrasena_lbl"),  "Confirmar contrasena", True),
            (T("frase_recuperacion"),        "Frase",                False),
        ]
        self._entradas: dict[str, tk.Entry] = {}
        for prompt, clave, es_pass in campos:
            _label(self, prompt, font=FONT_MONO, fg=FG_DIM, anchor="w").pack(fill="x")
            if es_pass:
                frm, e = _entry_password(self)
                frm.pack(fill="x", pady=(2, 4 if clave == "Contrasena" else 4))
            else:
                e = _entry(self)
                e.pack(fill="x", ipady=4, pady=(2, 4 if clave == "Contrasena" else 4))
            self._entradas[clave] = e
            if clave == "Contrasena":
                self._construir_barra()
                e.bind("<KeyRelease>", lambda _: self._actualizar_barra_y_match())
            if clave == "Confirmar contrasena":
                self._lbl_match = tk.Label(self, text="", font=FONT_TINY, bg=BG, anchor="w")
                self._lbl_match.pack(fill="x", pady=(0, 4))
                e.bind("<KeyRelease>", lambda _: self._actualizar_match())

        self._entradas["Usuario"].focus_set()
        _boton(self, T("crear_cuenta_btn"), self._registrar).pack(fill="x", ipady=6)
        btn = _boton(self, T("ya_tengo_cuenta"), self.app.ir_a_login, color=BG_ENTRY)
        btn.configure(fg=ACCENT)
        btn.pack(fill="x", ipady=4, pady=(8, 0))

    def _construir_barra(self):
        cont = tk.Frame(self, bg=BG)
        cont.pack(fill="x", pady=(0, 6))
        cf = tk.Frame(cont, bg=BG)
        cf.pack(fill="x", pady=(0, 3))
        self._criterio_labels = {}
        for i, (key, txt) in enumerate([("len",T("criterio_len")),("case",T("criterio_case")),("num",T("criterio_num")),("special",T("criterio_special"))]):
            lbl = tk.Label(cf, text=f"✗ {txt}", font=FONT_TINY, fg=FG_DIM, bg=BG)
            lbl.grid(row=i//2, column=i%2, sticky="w", padx=(0,12))
            self._criterio_labels[key] = lbl
        bc = tk.Frame(cont, bg=BG)
        bc.pack(fill="x")
        self._segmentos = []
        for _ in range(4):
            seg = tk.Frame(bc, height=6, bg=BORDER)
            seg.pack(side="left", fill="x", expand=True, padx=(0,2))
            self._segmentos.append(seg)
        self._nivel_label = tk.Label(cont, text="", font=FONT_SMALL, fg=FG_DIM, bg=BG, anchor="e")
        self._nivel_label.pack(fill="x", pady=(3,0))
        self._lbl_simbolo_invalido = tk.Label(cont, text="", font=FONT_TINY, fg=DANGER, bg=BG, anchor="w")
        self._lbl_simbolo_invalido.pack(fill="x")

    def _actualizar_barra_y_match(self):
        self._actualizar_barra()
        self._actualizar_match()

    def _actualizar_barra(self):
        pw = self._entradas["Contrasena"].get()
        score, texto, color = _calcular_seguridad(pw)
        for i, seg in enumerate(self._segmentos):
            seg.configure(bg=color if i < score else BORDER)
        self._nivel_label.configure(text=texto, fg=color if score > 0 else FG_DIM)
        checks = {"len": len(pw)>=12, "case": bool(re.search(r'[A-Z]',pw) and re.search(r'[a-z]',pw)),
                  "num": bool(re.search(r'\d',pw)), "special": bool(re.search(r'[!@#$%^&*()\-_=+\[\]{};:\'",.<>?/\\|`~]',pw))}
        nombres = {"len":T("criterio_len"),"case":T("criterio_case"),"num":T("criterio_num"),"special":T("criterio_special")}
        for key, cumple in checks.items():
            self._criterio_labels[key].configure(
                text=f"{'✓' if cumple else '✗'} {nombres[key]}",
                fg=ACCENT if cumple else FG_DIM)
        hay_invalido = bool(re.search(r'[^a-zA-Z0-9!@#$%^&*()\-_=+\[\]{};:\'",.<>?/\\|`~ ]', pw))
        self._lbl_simbolo_invalido.configure(text=T("simbolo_invalido") if hay_invalido else "")

    def _actualizar_match(self):
        pw1 = self._entradas["Contrasena"].get()
        pw2 = self._entradas["Confirmar contrasena"].get()
        if not pw2:
            self._lbl_match.configure(text="", fg=FG_DIM)
        elif pw1 == pw2:
            self._lbl_match.configure(text=T("contrasenas_coinciden"), fg=ACCENT)
        else:
            self._lbl_match.configure(text=T("contrasenas_no_coinciden"), fg=DANGER)

    def _registrar(self):
        username = self._entradas["Usuario"].get().strip()
        email    = self._entradas["Email"].get().strip()
        celular  = self._entradas["Celular"].get().strip()
        password = self._entradas["Contrasena"].get().strip()
        confirmar= self._entradas["Confirmar contrasena"].get().strip()
        frase    = self._entradas["Frase"].get().strip()
        if not all([username, email, password, confirmar, frase]):
            _modal_msg(self, T("campos_vacios"), T("campos_obligatorios"), "warning")
            return
        if password != confirmar:
            _modal_msg(self, T("error"), T("contrasenas_error"), "error")
            return
        try:
            username, needs_verification = auth.iniciar_registro(
                username, email, password, frase, phone=celular or None
            )
        except Exception as e:
            _modal_msg(self, T("error"), str(e), "error")
            return
        if needs_verification:
            self.app.ir_a_verificacion_registro(username)
        else:
            _modal_msg(self, T("cuenta_creada"), T("cuenta_creada_msg"), "info",
                       on_cerrar=self.app.ir_a_login)


# ---------------------------------------------------------------------------
# Pantalla de verificación de registro
# ---------------------------------------------------------------------------

class PantallaVerificacionRegistro(tk.Frame):
    def __init__(self, app: Aplicacion, username: str):
        super().__init__(app, bg=BG, padx=PAD, pady=PAD)
        self.app = app
        self.username = username
        self._construir()

    def _construir(self):
        tk.Label(self, text=T("verificar_cuenta"), font=FONT_GRANDE, fg=ACCENT, bg=BG).pack(pady=(20, 0))
        tk.Label(self, text=T("cod_activacion"), font=FONT_SMALL, fg=FG_DIM, bg=BG).pack()
        _separador(self).pack(fill="x", pady=14)
        tk.Label(self, text=T("enviado_email"),
                 font=FONT_SMALL, fg=FG_DIM, bg=BG, justify="center").pack(pady=(0, 12))
        _label(self, T("codigo_lbl"), font=FONT_MONO, fg=FG_DIM, anchor="w").pack(fill="x")
        self._codigo = _entry(self)
        self._codigo.pack(fill="x", ipady=5, pady=(2, 18))
        self._codigo.focus_set()
        self._codigo.bind("<Return>", lambda _: self._verificar())
        _boton(self, T("verificar_activar"), self._verificar).pack(fill="x", ipady=6)
        _separador(self).pack(fill="x", pady=14)
        _boton_oscuro(self, T("reenviar_codigo"), self._reenviar, fg=ACCENT).pack(fill="x", ipady=4, pady=(0,6))
        _boton_oscuro(self, T("volver"), self.app.ir_a_login).pack(fill="x", ipady=4)

    def _verificar(self):
        codigo = self._codigo.get().strip()
        if not codigo:
            _modal_msg(self, T("vacio"), T("ingresa_codigo"), "warning")
            return
        usuario = auth.verificar_otp_registro_y_activar(self.username, codigo)
        if usuario is None:
            _modal_msg(self, T("codigo_invalido"), T("codigo_expirado"), "error")
            self._codigo.delete(0, tk.END)
            return
        _modal_msg(self, T("cuenta_creada"), T("cuenta_activada"), "info",
                   on_cerrar=self.app.ir_a_login)

    def _reenviar(self):
        try:
            auth.reenviar_otp_registro(self.username)
            _modal_msg(self, T("enviado"), T("nuevo_codigo_enviado"))
        except Exception as e:
            _modal_msg(self, T("error"), str(e), "error")


# ---------------------------------------------------------------------------
# Pantalla de elección de método 2FA
# ---------------------------------------------------------------------------

class PantallaElegir2FA(tk.Frame):
    def __init__(self, app: Aplicacion, username: str):
        super().__init__(app, bg=BG, padx=PAD, pady=PAD)
        self.app = app
        self.username = username
        self._construir()

    def _construir(self):
        tk.Label(self, text=T("verificacion"), font=FONT_GRANDE, fg=ACCENT, bg=BG).pack(pady=(20, 0))
        tk.Label(self, text=T("elige_verificacion"), font=FONT_SMALL, fg=FG_DIM, bg=BG).pack()
        _separador(self).pack(fill="x", pady=14)
        metodos = auth.get_metodos_2fa_disponibles(self.username)
        touch_ok = _touch_id_disponible()

        hay_opciones = False
        if "biometrico" in metodos and touch_ok:
            _boton(self, T("touch_id_configurado"),
                   self._touch_id, color=CURSOR_COL).pack(fill="x", ipady=8, pady=(0,8))
            hay_opciones = True
        if "email" in metodos:
            _boton(self, T("correo_2fa"), lambda: self._elegir("email")).pack(fill="x", ipady=8, pady=(0,8))
            hay_opciones = True
        if "phone" in metodos:
            _boton(self, T("celular_2fa"), lambda: self._elegir("phone")).pack(fill="x", ipady=8, pady=(0,8))
            hay_opciones = True
        if "totp_app" in metodos:
            btn = _boton(self, T("app_totp"), lambda: self._elegir("totp_app"), color=BTN_OSCURO)
            btn.configure(fg=FG)
            btn.pack(fill="x", ipady=8, pady=(0,8))
            hay_opciones = True
        if touch_ok and "biometrico" not in metodos:
            _boton(self, T("touch_id_btn"), self._touch_id, color=CURSOR_COL).pack(fill="x", ipady=8, pady=(0,8))
            hay_opciones = True
        if not hay_opciones:
            tk.Label(self, text=T("sin_metodos"),
                     font=FONT_SMALL, fg=DANGER, bg=BG, justify="center").pack(pady=20)
        _separador(self).pack(fill="x", pady=14)
        _boton_oscuro(self, T("volver_login"), self.app.ir_a_login).pack(fill="x", ipady=4)

    def _elegir(self, method: str):
        try:
            if method == "email":
                auth.generar_otp_2fa_email(self.username)
            elif method == "phone":
                auth.generar_otp_2fa_phone(self.username)
        except Exception as e:
            _modal_msg(self, T("error_enviar_codigo"), str(e), "error")
            return
        self.app.ir_a_2fa_codigo(self.username, method)

    def _touch_id(self):
        if _verificar_touch_id():
            usuario = auth._obtener_usuario_activo(self.username)
            if usuario:
                self.app.ir_a_dashboard(usuario)
        else:
            _modal_msg(self, "Touch ID", T("touch_id_fallo"), "error")


# ---------------------------------------------------------------------------
# Pantalla de código 2FA
# ---------------------------------------------------------------------------

class PantallaCodigo2FA(tk.Frame):
    def __init__(self, app: Aplicacion, username: str, method: str):
        super().__init__(app, bg=BG, padx=PAD, pady=PAD)
        self.app = app
        self.username = username
        self.method = method
        self._construir()

    def _construir(self):
        tk.Label(self, text=T("verificacion"), font=FONT_GRANDE, fg=ACCENT, bg=BG).pack(pady=(20, 0))
        _separador(self).pack(fill="x", pady=14)
        msgs = {
            "email":    (T("codigo_enviado_email"), T("revisa_bandeja")),
            "phone":    (T("codigo_enviado_celular"), T("revisa_mensajes")),
            "totp_app": (T("codigo_totp"), T("app_hint")),
        }
        linea1, linea2 = msgs.get(self.method, msgs["email"])
        _label(self, linea1, font=FONT_MONO, fg=FG_DIM, anchor="w").pack(fill="x")
        _label(self, linea2, font=FONT_TINY, fg=FG_DIM, anchor="w").pack(fill="x", pady=(0, 8))
        self._codigo = _entry(self)
        self._codigo.pack(fill="x", ipady=5, pady=(2, 18))
        self._codigo.focus_set()
        self._codigo.bind("<Return>", lambda _: self._verificar())
        _boton(self, T("verificar_codigo"), self._verificar).pack(fill="x", ipady=6)
        _separador(self).pack(fill="x", pady=14)
        if self.method in ("email", "phone"):
            _boton_oscuro(self, T("reenviar_codigo"), self._reenviar, fg=ACCENT).pack(fill="x", ipady=4, pady=(0,6))
        _boton_oscuro(self, T("elegir_otro"), lambda: self.app.ir_a_elegir_2fa(self.username)).pack(fill="x", ipady=4, pady=(0,6))
        _boton_oscuro(self, T("volver_login"), self.app.ir_a_login).pack(fill="x", ipady=4)

    def _verificar(self):
        codigo = self._codigo.get().strip()
        if not codigo:
            _modal_msg(self, T("vacio"), T("ingresa_codigo"), "warning")
            return
        usuario = (auth.autenticar_paso2_totp(self.username, codigo)
                   if self.method == "totp_app"
                   else auth.autenticar_paso2_generico(self.username, codigo))
        if usuario is None:
            _modal_msg(self, T("codigo_invalido"), T("codigo_invalido2"), "error")
            self._codigo.delete(0, tk.END)
            return
        self.app.ir_a_dashboard(usuario)

    def _reenviar(self):
        try:
            if self.method == "email":
                auth.generar_otp_2fa_email(self.username)
            elif self.method == "phone":
                auth.generar_otp_2fa_phone(self.username)
            _modal_msg(self, T("enviado"), T("nuevo_codigo_enviado"))
        except Exception as e:
            _modal_msg(self, T("error"), str(e), "error")


# ---------------------------------------------------------------------------
# Dashboard — diseno con sidebar
# ---------------------------------------------------------------------------

class PantallaDashboard(tk.Frame):
    def __init__(self, app: Aplicacion, usuario: auth.Usuario):
        super().__init__(app, bg=BG)
        self.app = app
        self.usuario = usuario
        self._vista_actual = None
        self._timer_inactividad = None
        self._construir_layout()
        self._cambiar_vista("bienvenida")
        # Timer de inactividad
        self._reiniciar_timer()
        self.bind_all("<Motion>",  self._actividad)
        self.bind_all("<Key>",     self._actividad)
        self.bind_all("<Button>",  self._actividad)

    def _actividad(self, event=None):
        self._reiniciar_timer()

    def _reiniciar_timer(self):
        if self._timer_inactividad:
            self.after_cancel(self._timer_inactividad)
        self._timer_inactividad = self.after(INACTIVITY_TIMEOUT_MS, self._cerrar_sesion_inactiva)

    def _cerrar_sesion_inactiva(self):
        _modal_msg(self._content, T("sesion_expirada"), T("sesion_expiro"), "warning",
                   on_cerrar=self.app.ir_a_login)

    # ---- Layout ----

    def _construir_layout(self):
        # Sidebar fija izquierda
        self._sidebar = tk.Frame(self, bg=BG_PANEL, width=190)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        self._construir_sidebar()

        # Divisor vertical
        tk.Frame(self, width=1, bg=BORDER).pack(side="left", fill="y")

        # Área de contenido
        self._content = tk.Frame(self, bg=BG)
        self._content.pack(side="left", fill="both", expand=True)

    def _construir_sidebar(self):
        for w in self._sidebar.winfo_children():
            w.destroy()
        sb = self._sidebar

        # Logo + usuario
        if _QR_OK and _LOGO_PATH.exists():
            _logo_img = ImageTk.PhotoImage(Image.open(_LOGO_PATH).resize((80, 80), Image.LANCZOS))
            lbl_logo = tk.Label(sb, image=_logo_img, bg=BG_PANEL)
            lbl_logo.image = _logo_img  # mantener referencia
            lbl_logo.pack(pady=(18, 4), padx=18, anchor="w")
        else:
            tk.Label(sb, text="ciphie", font=("Courier New", 15, "bold"), fg=ACCENT, bg=BG_PANEL
                     ).pack(pady=(22, 2), padx=18, anchor="w")
        tk.Label(sb, text=f"@{self.usuario.username}", font=FONT_TINY, fg=FG_DIM, bg=BG_PANEL
                 ).pack(padx=18, anchor="w", pady=(0, 14))
        tk.Frame(sb, height=1, bg=BORDER).pack(fill="x")

        # Nav items
        self._nav_btns: dict[str, tk.Label] = {}
        nav_items = [
            (T("nav_inicio"),    "bienvenida"),
            (T("nav_nuevo"),     "inicio"),
            (T("nav_secretos"),  "secretos"),
            (T("nav_actividad"), "actividad"),
            (T("nav_usuario"),   "usuario"),
        ]
        for texto, vista in nav_items:
            btn = tk.Label(sb, text=texto, font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL,
                           cursor="hand2", anchor="w", padx=18, pady=10)
            btn.pack(fill="x")
            btn.bind("<Button-1>", lambda e, v=vista: self._cambiar_vista(v))
            btn.bind("<Enter>",    lambda e, b=btn: b.configure(bg=BORDER) if b["bg"] != BORDER else None)
            btn.bind("<Leave>",    lambda e, b=btn, v=vista: b.configure(
                bg=BORDER if self._vista_actual == v else BG_PANEL))
            self._nav_btns[vista] = btn

        # Fondo: idioma + logout
        tk.Frame(sb, height=1, bg=BORDER).pack(side="bottom", fill="x")
        logout = tk.Label(sb, text=T("nav_salir"), font=FONT_SMALL, fg=DANGER, bg=BG_PANEL,
                          cursor="hand2", anchor="w", padx=18, pady=12)
        logout.pack(side="bottom", fill="x")
        logout.bind("<Button-1>", lambda e: self.app.ir_a_login())
        logout.bind("<Enter>", lambda e: logout.configure(bg=BORDER))
        logout.bind("<Leave>", lambda e: logout.configure(bg=BG_PANEL))

        lang_btn = tk.Label(sb, text=T("cambiar_idioma"), font=FONT_TINY, fg=FG_DIM, bg=BG_PANEL,
                            cursor="hand2", anchor="w", padx=18, pady=8)
        lang_btn.pack(side="bottom", fill="x")
        lang_btn.bind("<Button-1>", lambda e: self._toggle_idioma())
        lang_btn.bind("<Enter>", lambda e: lang_btn.configure(fg=ACCENT))
        lang_btn.bind("<Leave>", lambda e: lang_btn.configure(fg=FG_DIM))

    # ---- Navegación entre vistas ----

    def _toggle_idioma(self):
        _LANG[0] = "en" if _LANG[0] == "es" else "es"
        self._construir_sidebar()
        self._cambiar_vista(self._vista_actual)

    def _cambiar_vista(self, vista: str):
        self._vista_actual = vista
        for v, btn in self._nav_btns.items():
            btn.configure(bg=BORDER if v == vista else BG_PANEL,
                          fg=FG if v == vista else FG_DIM)
        for w in self._content.winfo_children():
            w.destroy()
        if vista == "bienvenida":
            self._vista_bienvenida()
        elif vista == "inicio":
            self._vista_inicio()
        elif vista == "secretos":
            self._vista_lista_secretos()
        elif vista == "actividad":
            self._vista_actividad()
        elif vista == "usuario":
            self._vista_usuario()

    # ---- Vista: bienvenida ----

    def _vista_bienvenida(self):
        ct = self._content
        panel = tk.Frame(ct, bg=BG)
        panel.pack(fill="both", expand=True)
        # Centrar verticalmente
        inner = tk.Frame(panel, bg=BG)
        inner.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(inner, text=f"{T('bienvenido')},",
                 font=("Courier New", 26, "bold"), fg=ACCENT, bg=BG).pack()
        tk.Label(inner, text=f"@{self.usuario.username}!",
                 font=("Courier New", 26, "bold"), fg=FG, bg=BG).pack()
        tk.Frame(inner, height=2, bg=BORDER).pack(fill="x", pady=16)
        tk.Label(inner, text=T("bienvenido_sub"),
                 font=FONT_SMALL, fg=FG_DIM, bg=BG).pack()

    # ---- Vista: inicio (formulario nuevo secreto) ----

    def _vista_inicio(self):
        ct = self._content

        panel = tk.Frame(ct, bg=BG, padx=40, pady=30)
        panel.pack(fill="both", expand=True)

        tk.Label(panel, text=T("nuevo_secreto"), font=("Courier New", 18, "bold"), fg=ACCENT, bg=BG
                 ).pack(anchor="w")
        tk.Label(panel, text=T("agrega_secreto"), font=FONT_SMALL, fg=FG_DIM, bg=BG
                 ).pack(anchor="w", pady=(2, 0))
        tk.Frame(panel, height=1, bg=BORDER).pack(fill="x", pady=12)

        form = tk.Frame(panel, bg=BG)
        form.pack(fill="x")

        # Nombre
        tk.Label(form, text=T("nombre_lbl"), font=FONT_SMALL, fg=FG_DIM, bg=BG).pack(anchor="w")
        self._nombre = _entry(form, width=50)
        self._nombre.pack(fill="x", ipady=5, pady=(2, 10))
        self._nombre.focus_set()

        # Fila: categoria + expiry
        fila = tk.Frame(form, bg=BG)
        fila.pack(fill="x", pady=(0, 10))

        cf = tk.Frame(fila, bg=BG)
        cf.pack(side="left")
        tk.Label(cf, text=T("categoria_lbl"), font=FONT_SMALL, fg=FG_DIM, bg=BG).pack(anchor="w")
        self._categoria = tk.StringVar(value=TC(CATEGORIAS[0]))
        om = tk.OptionMenu(cf, self._categoria, *[TC(c) for c in CATEGORIAS], command=self._actualizar_campos_inicio)
        om.configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER, activeforeground=FG,
                     highlightbackground=BG_ENTRY, relief="flat", font=FONT_SMALL,
                     cursor="hand2", width=12)
        om["menu"].configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER, activeforeground=FG,
                             font=FONT_SMALL, bd=0)
        om.pack(pady=(2, 0))

        ef = tk.Frame(fila, bg=BG)
        ef.pack(side="left", padx=(24, 0))
        tk.Label(ef, text=T("expira_lbl"), font=FONT_SMALL, fg=FG_DIM, bg=BG).pack(anchor="w")
        self._expiry_var = tk.StringVar(value=T("nunca"))
        om_exp = tk.OptionMenu(ef, self._expiry_var, *[T("nunca"), T("dias_30"), T("dias_60"), T("dias_90"), T("personalizada")],
                               command=self._toggle_expiry_custom)
        om_exp.configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER, activeforeground=FG,
                         highlightbackground=BG_ENTRY, relief="flat", font=FONT_SMALL,
                         cursor="hand2", width=12)
        om_exp["menu"].configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER, activeforeground=FG,
                                 font=FONT_SMALL, bd=0)
        om_exp.pack(pady=(2, 0))
        self._expiry_custom_entry = _entry(ef, width=14)
        self._expiry_custom_entry.insert(0, T("fecha_placeholder"))

        # Contenedor de campos dinamicos (segun categoria)
        self._campos_frame = tk.Frame(form, bg=BG)
        self._campos_frame.pack(fill="x", pady=(0, 8))
        self._campos_entradas: dict[str, tk.Widget] = {}
        self._actualizar_campos_inicio(CATEGORIAS[0])

        _boton(form, T("guardar_secreto"), self._guardar_secreto).pack(anchor="w", ipadx=16, ipady=6, pady=(4, 0))

    def _actualizar_campos_inicio(self, categoria: str):
        """Regenera los campos dinamicos al cambiar de categoria."""
        for w in self._campos_frame.winfo_children():
            w.destroy()
        self._campos_entradas = {}
        cat_key = _cat_key(categoria)
        plantilla = PLANTILLAS_CAMPOS.get(cat_key, PLANTILLAS_CAMPOS["otro"])
        for campo in plantilla:
            nombre = campo["nombre"]
            tipo   = campo["tipo"]
            tk.Label(self._campos_frame, text=f"{TF(nombre)}:", font=FONT_SMALL,
                     fg=FG_DIM, bg=BG).pack(anchor="w")
            if tipo == "textarea":
                txt = tk.Text(self._campos_frame, font=FONT_MONO, bg=BG_ENTRY, fg=FG,
                              insertbackground=ACCENT, relief="flat",
                              highlightthickness=1, highlightbackground=BORDER,
                              highlightcolor=ACCENT, width=50, height=6)
                txt.pack(fill="x", pady=(2, 8))
                self._campos_entradas[nombre] = txt
            elif tipo == "password":
                frm, e = _entry_password(self._campos_frame)
                frm.pack(fill="x", pady=(2, 8))
                self._campos_entradas[nombre] = e
            else:
                e = _entry(self._campos_frame, width=50)
                e.pack(fill="x", ipady=4, pady=(2, 8))
                # Auto-fill "usuario" con el usuario logueado en la categoria contrasena
                if nombre == "usuario" and cat_key == "contrasena":
                    e.insert(0, self.usuario.username)
                self._campos_entradas[nombre] = e

    # ---- Vista: lista de secretos (columnas por categoría) ----

    def _vista_lista_secretos(self):
        ct = self._content

        try:
            secretos  = listar_secretos(self.usuario.id)
            vencidos  = secretos_vencidos(self.usuario.id)
            por_vencer = secretos_por_vencer(self.usuario.id)
        except Exception as e:
            tk.Label(ct, text=f"error: {e}", bg=BG, fg=DANGER, font=FONT_SMALL).pack(padx=22, pady=20)
            return

        vencidos_ids   = {s.id for s in vencidos}
        por_vencer_ids = {s.id for s in por_vencer}

        # Header
        hdr = tk.Frame(ct, bg=BG, padx=22, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text=T("secretos_guardados"), font=("Courier New", 15, "bold"), fg=ACCENT, bg=BG
                 ).pack(side="left")
        tk.Frame(ct, height=1, bg=BORDER).pack(fill="x")

        # Banner vencidos
        if vencidos:
            banner = tk.Frame(ct, bg="#2d1b1b", padx=16, pady=8)
            banner.pack(fill="x")
            tk.Label(banner, text=T("vencidos_banner", n=len(vencidos)),
                     font=FONT_SMALL, fg=DANGER, bg="#2d1b1b").pack(side="left")
            for sv in vencidos:
                _boton(banner, f"{T('renovar')} {sv.name}", lambda s=sv: self._editar_secreto(s),
                       color=AMARILLO).pack(side="right", ipadx=6, ipady=2, padx=(4, 0))
            tk.Frame(ct, height=1, bg=BORDER).pack(fill="x")

        if not secretos:
            tk.Label(ct, text=T("no_secretos"), bg=BG, fg=FG_DIM,
                     font=FONT_SMALL).pack(padx=22, pady=30)
            return

        # Agrupar por categoría
        por_cat: dict[str, list] = {}
        for s in secretos:
            por_cat.setdefault(s.category, []).append(s)

        # Canvas con scroll horizontal
        wrap = tk.Frame(ct, bg=BG)
        wrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        sb_h = ttk.Scrollbar(wrap, orient="horizontal", command=canvas.xview)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(xscrollcommand=sb_h.set)
        canvas.unbind_all("<MouseWheel>")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.xview_scroll(-1*(e.delta//120), "units"))
        canvas.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))
        canvas.pack(fill="both", expand=True)
        sb_h.pack(fill="x", side="bottom")

        ahora  = datetime.now().isoformat()
        pronto = (datetime.now() + timedelta(days=7)).isoformat()

        COL_W = 210
        for cat in CATEGORIAS:
            if cat not in por_cat:
                continue
            cat_color = CAT_COLORS.get(cat, FG_DIM)

            col = tk.Frame(inner, bg=BG_PANEL, padx=10, pady=10)
            col.pack(side="left", anchor="n", padx=(0, 8), pady=8)

            # Cabecera de columna
            hdr_col = tk.Frame(col, bg=cat_color)
            hdr_col.pack(fill="x", pady=(0, 8))
            tk.Label(hdr_col, text=f"  {TC(cat)}  ({len(por_cat[cat])})",
                     font=FONT_SMALL, fg="#0d1117", bg=cat_color, width=22
                     ).pack(anchor="w", pady=4)

            for s in por_cat[cat]:
                card = tk.Frame(col, bg=BG, padx=8, pady=8,
                                highlightthickness=1, highlightbackground=BORDER)
                card.pack(fill="x", pady=(0, 6))

                # Fila: nombre + ⋮
                top = tk.Frame(card, bg=BG)
                top.pack(fill="x")

                expiry_icon = ""
                if s.id in vencidos_ids:
                    expiry_icon = " 🔴"
                elif s.id in por_vencer_ids:
                    expiry_icon = " ⚠️"

                tk.Label(top, text=f"{s.name}{expiry_icon}", bg=BG, fg=FG,
                         font=FONT_SMALL, anchor="w", wraplength=150
                         ).pack(side="left", fill="x", expand=True)

                mb = tk.Label(top, text="⋮", bg=BG, fg=FG_DIM,
                              font=("Courier New", 15), cursor="hand2")
                mb.pack(side="right")
                mb.bind("<Button-1>", lambda e, sec=s: self._popup_secreto(e, sec))
                mb.bind("<Enter>",    lambda e, b=mb: b.configure(fg=FG))
                mb.bind("<Leave>",    lambda e, b=mb: b.configure(fg=FG_DIM))

                # Creador
                tk.Label(card, text=f"@{self.usuario.username}", bg=BG,
                         fg=FG_DIM, font=FONT_TINY, anchor="w").pack(fill="x", pady=(4, 0))

    def _popup_secreto(self, event, secreto):
        m = tk.Menu(self, tearoff=0, bg=BG_PANEL, fg=FG, activebackground=BORDER,
                    activeforeground=FG, font=FONT_SMALL, bd=0, relief="flat")
        m.add_command(label=f"  {T('copiar_btn')}",    command=lambda: self._copiar_secreto(secreto))
        m.add_command(label=f"  {T('editar_btn')}",    command=lambda: self._editar_secreto(secreto))
        m.add_command(label=f"  {T('historial_btn')}", command=lambda: self._historial_secreto(secreto))
        m.add_separator()
        m.add_command(label=f"  {T('eliminar_btn')}",  command=lambda: self._eliminar_secreto(secreto))
        m.post(event.x_root, event.y_root)

    # ---- Vista: usuario ----

    def _vista_usuario(self):
        ct = self._content
        panel = tk.Frame(ct, bg=BG, padx=28, pady=24)
        panel.pack(fill="both", expand=True)

        tk.Label(panel, text=T("perfil"), font=("Courier New", 18, "bold"), fg=ACCENT, bg=BG
                 ).pack(anchor="w")
        tk.Frame(panel, height=1, bg=BORDER).pack(fill="x", pady=12)

        for etiqueta, valor in [(T("usuario_tag"), self.usuario.username), (T("email_tag"), self.usuario.email)]:
            fila = tk.Frame(panel, bg=BG)
            fila.pack(fill="x", pady=(0, 8))
            tk.Label(fila, text=f"{etiqueta}:", font=FONT_MONO, fg=FG_DIM, bg=BG, width=10,
                     anchor="w").pack(side="left")
            tk.Label(fila, text=valor, font=FONT_SMALL, fg=FG, bg=BG).pack(side="left")

        _boton_oscuro(panel, T("editar_perfil"), self._editar_perfil_modal
                      ).pack(anchor="w", ipadx=10, ipady=4, pady=(4, 0))

        tk.Frame(panel, height=1, bg=BORDER).pack(fill="x", pady=16)

        # — Seguridad —
        tk.Label(panel, text=T("seguridad"), font=("Courier New", 14, "bold"), fg=FG_DIM, bg=BG
                 ).pack(anchor="w", pady=(0, 10))
        _boton(panel, T("config_2fa"), self._abrir_config_2fa).pack(anchor="w", ipadx=10, ipady=5)

        tk.Frame(panel, height=1, bg=BORDER).pack(fill="x", pady=16)

        # — Cuentas —
        tk.Label(panel, text=T("cuentas"), font=("Courier New", 14, "bold"), fg=FG_DIM, bg=BG
                 ).pack(anchor="w", pady=(0, 10))

        fila_btns = tk.Frame(panel, bg=BG)
        fila_btns.pack(anchor="w")
        _boton(fila_btns, T("nueva_cuenta_btn"), self._crear_usuario_modal
               ).pack(side="left", ipadx=10, ipady=5)
        _boton_oscuro(fila_btns, T("cambiar_cuenta"), self._cambiar_usuario_modal
                      ).pack(side="left", padx=(10, 0), ipadx=10, ipady=5)

    def _editar_perfil_modal(self):
        def construir(box, cerrar):
            tk.Label(box, text=T("editar_perfil_titulo"), font=("Courier New", 13, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
            tk.Frame(box, height=1, bg=BORDER).pack(fill="x", pady=10)

            tk.Label(box, text=T("nuevo_usuario_hint"),
                     font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
            e_usr = _entry(box, width=38)
            e_usr.insert(0, self.usuario.username)
            e_usr.pack(fill="x", ipady=4, pady=(2, 8))

            tk.Label(box, text=T("nuevo_email_hint"),
                     font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
            e_email = _entry(box, width=38)
            e_email.insert(0, self.usuario.email)
            e_email.pack(fill="x", ipady=4, pady=(2, 8))

            def _guardar():
                new_usr   = e_usr.get().strip()
                new_email = e_email.get().strip()
                # Solo actualizar si cambio
                u = new_usr   if new_usr   != self.usuario.username else None
                e = new_email if new_email != self.usuario.email    else None
                if not u and not e:
                    cerrar()
                    return
                try:
                    auth.actualizar_usuario(self.usuario.id, new_username=u, new_email=e)
                    if u:
                        self.usuario = auth.Usuario(
                            id=self.usuario.id, username=u,
                            email=e or self.usuario.email, is_active=True)
                    if e:
                        self.usuario = auth.Usuario(
                            id=self.usuario.id, username=self.usuario.username,
                            email=e, is_active=True)
                    def _cerrar_y_refrescar():
                        cerrar()
                        self._cambiar_vista("usuario")
                    _modal_msg(box, T("confirmar"), T("perfil_actualizado"),
                               on_cerrar=_cerrar_y_refrescar)
                except Exception as ex:
                    _modal_msg(box, T("error"), str(ex), "error")

            _boton(box, T("guardar_cambios"), _guardar).pack(fill="x", ipady=5, pady=(4, 0))
            _boton_oscuro(box, T("cancelar"), cerrar).pack(fill="x", ipady=4, pady=(6, 0))

        self._modal(construir)

    def _crear_usuario_modal(self):
        def construir(box, cerrar):
            tk.Label(box, text=T("nueva_cuenta_titulo"), font=("Courier New", 13, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
            tk.Frame(box, height=1, bg=BORDER).pack(fill="x", pady=10)

            campos = [
                ("usuario",  T("usuario_lbl"),      False),
                ("email",    T("email_lbl"),         False),
                ("password", T("contrasena_lbl"),    True),
                ("frase",    T("frase_recuperacion"), False),
            ]
            entradas: dict[str, tk.Entry] = {}
            for key, prompt, es_pass in campos:
                tk.Label(box, text=prompt, font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
                if es_pass:
                    frm, e = _entry_password(box)
                    frm.pack(fill="x", pady=(2, 8))
                else:
                    e = _entry(box, width=38)
                    e.pack(fill="x", ipady=4, pady=(2, 8))
                entradas[key] = e

            def _guardar():
                username = entradas["usuario"].get().strip()
                email    = entradas["email"].get().strip()
                password = entradas["password"].get().strip()
                frase    = entradas["frase"].get().strip()
                if not all([username, email, password, frase]):
                    _modal_msg(box, T("campos_vacios"), T("completa_campos"), "warning")
                    return
                try:
                    auth.registrar_usuario(username, email, password, frase)
                    _modal_msg(box, T("cuenta_creada"), T("cuenta_ok", username=username),
                               on_cerrar=cerrar)
                except Exception as ex:
                    _modal_msg(box, T("error"), str(ex), "error")

            _boton(box, T("crear_cuenta_btn"), _guardar).pack(fill="x", ipady=5, pady=(4, 0))
            _boton_oscuro(box, T("cancelar"), cerrar).pack(fill="x", ipady=4, pady=(6, 0))

        self._modal(construir)

    def _cambiar_usuario_modal(self):
        usuarios = listar_usuarios_basico()

        def construir(box, cerrar):
            tk.Label(box, text=T("cambiar_cuenta_titulo"), font=("Courier New", 13, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
            tk.Frame(box, height=1, bg=BORDER).pack(fill="x", pady=10)

            if not usuarios:
                tk.Label(box, text=T("no_otras_cuentas"), font=FONT_SMALL,
                         fg=FG_DIM, bg=BG_PANEL).pack(pady=10)
                _boton_oscuro(box, T("cerrar"), cerrar).pack(fill="x", ipady=4, pady=(10, 0))
                return

            usuario_var = tk.StringVar(value=usuarios[0].username)
            tk.Label(box, text=T("seleccionar_cuenta"), font=FONT_SMALL,
                     fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
            for u in usuarios:
                color = ACCENT if u.username == self.usuario.username else FG_DIM
                rb = tk.Radiobutton(box, text=f"@{u.username}", variable=usuario_var,
                                    value=u.username, font=FONT_SMALL,
                                    bg=BG_PANEL, fg=color, activebackground=BG_PANEL,
                                    selectcolor=BG_ENTRY, cursor="hand2")
                rb.pack(anchor="w", pady=(2, 0))

            tk.Label(box, text=T("contrasena_lbl"), font=FONT_SMALL, fg=FG_DIM,
                     bg=BG_PANEL).pack(anchor="w", pady=(10, 0))
            frm_pw, e_pw = _entry_password(box)
            frm_pw.pack(fill="x", pady=(2, 8))

            def _entrar():
                username = usuario_var.get()
                password = e_pw.get()
                if not password:
                    _modal_msg(box, T("vacio"), T("ingresa_contrasena"), "warning")
                    return
                try:
                    estado, usuario = auth.autenticar_paso1(username, password)
                except Exception as ex:
                    _modal_msg(box, T("error"), str(ex), "error")
                    return
                cerrar()
                if estado == "ok":
                    self.app.ir_a_dashboard(usuario)
                elif estado == "2fa_requerido":
                    self.app.ir_a_elegir_2fa(username)
                else:
                    _modal_msg(self._content, T("acceso_denegado"), T("contrasena_incorrecta"), "error")

            _boton(box, T("entrar"), _entrar).pack(fill="x", ipady=5, pady=(4, 0))
            _boton_oscuro(box, T("cancelar"), cerrar).pack(fill="x", ipady=4, pady=(6, 0))

        self._modal(construir)

    # ---- Acciones secretos ----

    def _toggle_expiry_custom(self, valor):
        if valor == T("personalizada"):
            self._expiry_custom_entry.pack(fill="x", ipady=4)
        else:
            self._expiry_custom_entry.pack_forget()

    def _calcular_expires_at(self) -> "str | None":
        opcion = self._expiry_var.get()
        if opcion == T("nunca"):
            return None
        dias_map = {T("dias_30"): 30, T("dias_60"): 60, T("dias_90"): 90}
        if opcion in dias_map:
            return (datetime.now() + timedelta(days=dias_map[opcion])).isoformat()
        # personalizada
        texto = self._expiry_custom_entry.get().strip()
        try:
            return datetime.strptime(texto, "%Y-%m-%d").isoformat()
        except ValueError:
            _modal_msg(self._content, T("fecha_invalida"), T("formato_fecha"), "error")
            raise

    def _guardar_secreto(self):
        nombre    = self._nombre.get().strip()
        categoria = _cat_key(self._categoria.get())
        if not nombre:
            _modal_msg(self._content, T("campo_vacio"), T("ingresa_nombre"), "warning")
            return
        try:
            expires_at = self._calcular_expires_at()
        except ValueError:
            return

        # Leer campos del formulario dinamico
        campos_vals: dict[str, str] = {}
        for nombre_campo, widget in self._campos_entradas.items():
            if isinstance(widget, tk.Text):
                val = widget.get("1.0", "end-1c").strip()
            else:
                val = widget.get().strip()
            campos_vals[nombre_campo] = val

        # Serializar y cifrar
        valor_serializado = _serializar_campos(campos_vals)
        try:
            agregar_secreto(nombre, crypto.cifrar(valor_serializado), self.usuario.id, categoria, expires_at)
            registrar_auditoria(self.usuario.id, "crear", nombre)
        except (ValueError, RuntimeError) as e:
            _modal_msg(self._content, T("error_al_guardar"), str(e), "error")
            return
        self._nombre.delete(0, tk.END)
        self._expiry_var.set(T("nunca"))
        self._expiry_custom_entry.pack_forget()
        self._cambiar_vista("secretos")

    def _toast(self, mensaje: str, duracion_ms: int = 2500):
        """Notificación temporal en la esquina inferior del área de contenido."""
        t = tk.Label(self._content, text=mensaje, font=FONT_SMALL,
                     bg=BG_PANEL, fg=ACCENT, padx=16, pady=10,
                     highlightthickness=1, highlightbackground=BORDER)
        t.place(relx=0.5, rely=0.92, anchor="center")
        self.after(duracion_ms, t.destroy)

    # ---- Modal helper ----

    def _modal(self, construir_fn):
        """Muestra un modal sobre el área de contenido actual."""
        overlay = tk.Frame(self._content, bg="#0a0e14")
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        box = tk.Frame(overlay, bg=BG_PANEL, padx=28, pady=22,
                       highlightthickness=1, highlightbackground=BORDER)
        box.pack(expand=True)
        def cerrar():
            overlay.destroy()
        construir_fn(box, cerrar)
        overlay.lift()

    def _ver_secreto(self, secreto):
        try:
            valor = crypto.descifrar(secreto.encrypted_value)
        except ValueError as e:
            _modal_msg(self._content, T("error_cifrado"), str(e), "error")
            return
        registrar_auditoria(self.usuario.id, "ver", secreto.name)

        def construir(box, cerrar):
            tk.Label(box, text=f"[ {secreto.name} ]", font=("Courier New", 13, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
            tk.Label(box, text=T("ver_valor"), font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL
                     ).pack(anchor="w", pady=(12, 2))
            campo = _entry(box, width=44)
            campo.insert(0, valor)
            campo.configure(state="readonly")
            campo.pack(fill="x", ipady=5)
            _boton_oscuro(box, f"> {T('cerrar')}", cerrar, fg=FG).pack(pady=(14, 0), ipady=4, fill="x")

        self._modal(construir)

    def _copiar_secreto(self, secreto):
        try:
            valor_descifrado = crypto.descifrar(secreto.encrypted_value)
        except ValueError as e:
            _modal_msg(self._content, T("error_cifrado"), str(e), "error")
            return

        parsed = _parsear_valor(valor_descifrado)

        if parsed["tipo"] == "simple":
            self._copiar_al_portapapeles(parsed["valor"], secreto.name)
            registrar_auditoria(self.usuario.id, "copiar", secreto.name)
            return

        # Multi-campo: mostrar dialogo para elegir que campo copiar
        campos = parsed["campos"]
        campos_con_valor = {k: v for k, v in campos.items() if v}

        if secreto.category == "env":
            # Para .env: ofrecer copiar todo o campo individual
            def construir(box, cerrar):
                tk.Label(box, text=T("copiar_titulo", name=secreto.name), font=("Courier New", 13, "bold"),
                         fg=ACCENT, bg=BG_PANEL).pack(anchor="w", pady=(0, 8))
                _boton(box, T("copiar_todo_env"), lambda: (
                    self._copiar_al_portapapeles(campos.get("contenido", ""), secreto.name),
                    registrar_auditoria(self.usuario.id, "copiar", secreto.name),
                    cerrar(),
                )).pack(fill="x", ipady=4, pady=(0, 8))
                _boton_oscuro(box, T("cancelar"), cerrar).pack(fill="x", ipady=4)
            self._modal(construir)
            return

        if len(campos_con_valor) == 1:
            campo_unico = next(iter(campos_con_valor))
            self._copiar_al_portapapeles(campos_con_valor[campo_unico], secreto.name)
            registrar_auditoria(self.usuario.id, "copiar", secreto.name)
            return

        def construir(box, cerrar):
            tk.Label(box, text=T("copiar_campo_titulo", name=secreto.name), font=("Courier New", 13, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w", pady=(0, 8))
            for nombre_campo, val in campos_con_valor.items():
                def _hacer_copia(v=val, n=nombre_campo):
                    self._copiar_al_portapapeles(v, f"{secreto.name}/{n}")
                    registrar_auditoria(self.usuario.id, "copiar", secreto.name)
                    cerrar()
                _boton(box, f"> {TF(nombre_campo)}", _hacer_copia).pack(fill="x", ipady=4, pady=(0, 4))
            _boton_oscuro(box, T("cancelar"), cerrar).pack(fill="x", ipady=4, pady=(4, 0))
        self._modal(construir)

    def _copiar_al_portapapeles(self, valor: str, nombre: str):
        """Copia al portapapeles y lo borra en 30s solo si no cambio."""
        self.app.clipboard_clear()
        self.app.clipboard_append(valor)
        _val_ref = [valor]

        def _limpiar():
            try:
                actual = self.app.clipboard_get()
                if actual == _val_ref[0]:
                    self.app.clipboard_clear()
            except Exception:
                pass

        self.app.after(30_000, _limpiar)
        # Toast temporal en lugar de modal bloqueante
        self._toast(T("copiado_msg", name=nombre))

    def _eliminar_secreto(self, secreto):
        def _confirmar():
            try:
                eliminar_secreto(secreto.id, self.usuario.id)
                registrar_auditoria(self.usuario.id, "eliminar", secreto.name)
            except Exception as e:
                _modal_msg(self._content, T("error"), str(e), "error")
                return
            self._cambiar_vista("secretos")
        _modal_confirmar(self._content, T("confirmar"),
                         T("eliminar_confirmar", name=secreto.name), _confirmar)

    def _editar_secreto(self, secreto):
        # Descifrar valor actual para pre-rellenar campos
        try:
            valor_actual = crypto.descifrar(secreto.encrypted_value)
            parsed_actual = _parsear_valor(valor_actual)
        except Exception:
            parsed_actual = {"tipo": "simple", "valor": ""}

        campos_actuales = (parsed_actual.get("campos", {})
                           if parsed_actual["tipo"] == "multi" else {})

        def construir(box, cerrar):
            tk.Label(box, text=T("editar_secreto"), font=("Courier New", 13, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
            tk.Frame(box, height=1, bg=BORDER).pack(fill="x", pady=10)

            tk.Label(box, text=T("nombre_lbl"), font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
            e_nombre = _entry(box, width=44)
            e_nombre.insert(0, secreto.name)
            e_nombre.pack(fill="x", ipady=4, pady=(2, 8))

            tk.Label(box, text=T("categoria_lbl"), font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
            cat_var = tk.StringVar(value=TC(secreto.category))
            om = tk.OptionMenu(box, cat_var, *[TC(c) for c in CATEGORIAS])
            om.configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER, activeforeground=FG,
                         highlightbackground=BG_ENTRY, relief="flat", font=FONT_SMALL, cursor="hand2")
            om["menu"].configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER,
                                 activeforeground=FG, font=FONT_SMALL, bd=0)
            om.pack(anchor="w", pady=(2, 8))

            # Campos multi-campo
            tk.Label(box, text=T("valores_lbl"), font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
            campos_frame = tk.Frame(box, bg=BG_PANEL)
            campos_frame.pack(fill="x", pady=(2, 8))
            plantilla = PLANTILLAS_CAMPOS.get(secreto.category, PLANTILLAS_CAMPOS["otro"])
            campos_widgets: dict[str, tk.Widget] = {}
            for campo in plantilla:
                nc = campo["nombre"]
                tipo = campo["tipo"]
                tk.Label(campos_frame, text=f"  {TF(nc)}:", font=FONT_TINY,
                         fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
                if tipo == "textarea":
                    txt = tk.Text(campos_frame, font=FONT_MONO, bg=BG_ENTRY, fg=FG,
                                  insertbackground=ACCENT, relief="flat",
                                  highlightthickness=1, highlightbackground=BORDER,
                                  highlightcolor=ACCENT, width=44, height=5)
                    txt.pack(fill="x", pady=(2, 6))
                    val_prev = campos_actuales.get(nc, "")
                    if val_prev:
                        txt.insert("1.0", val_prev)
                    campos_widgets[nc] = txt
                elif tipo == "password":
                    frm, e = _entry_password(campos_frame)
                    frm.pack(fill="x", pady=(2, 6))
                    val_prev = campos_actuales.get(nc, "")
                    if val_prev:
                        e.insert(0, val_prev)
                    campos_widgets[nc] = e
                else:
                    e = _entry(campos_frame, width=44)
                    e.pack(fill="x", ipady=4, pady=(2, 6))
                    val_prev = campos_actuales.get(nc, "")
                    if val_prev:
                        e.insert(0, val_prev)
                    campos_widgets[nc] = e

            tk.Label(box, text=T("expira_lbl"), font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
            opciones_exp = [T("sin_cambio"), T("nunca"), T("dias_30"), T("dias_60"), T("dias_90"), T("personalizada")]
            exp_var = tk.StringVar(value=T("sin_cambio"))
            exp_custom = _entry(box, width=16)
            exp_custom.insert(0, T("fecha_placeholder"))

            def _on_exp(v):
                exp_custom.pack(fill="x", ipady=4, pady=(2, 8)) if v == T("personalizada") else exp_custom.pack_forget()

            om_exp = tk.OptionMenu(box, exp_var, *opciones_exp, command=_on_exp)
            om_exp.configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER, activeforeground=FG,
                             highlightbackground=BG_ENTRY, relief="flat", font=FONT_SMALL, cursor="hand2")
            om_exp["menu"].configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER,
                                     activeforeground=FG, font=FONT_SMALL, bd=0)
            om_exp.pack(anchor="w", pady=(2, 8))

            def _guardar():
                nuevo_nombre = e_nombre.get().strip() or secreto.name
                nuevo_cat    = _cat_key(cat_var.get())
                opcion_exp   = exp_var.get()

                # Leer todos los campos
                nuevos_campos: dict[str, str] = {}
                for nc, widget in campos_widgets.items():
                    if isinstance(widget, tk.Text):
                        nuevos_campos[nc] = widget.get("1.0", "end-1c").strip()
                    else:
                        nuevos_campos[nc] = widget.get().strip()

                enc = crypto.cifrar(_serializar_campos(nuevos_campos))

                if opcion_exp == T("sin_cambio"):
                    nuevo_expires = secreto.expires_at
                elif opcion_exp == T("nunca"):
                    nuevo_expires = None
                elif opcion_exp == T("personalizada"):
                    try:
                        nuevo_expires = datetime.strptime(exp_custom.get().strip(), "%Y-%m-%d").isoformat()
                    except ValueError:
                        _modal_msg(box, T("fecha_invalida"), T("formato_fecha"), "error")
                        return
                else:
                    nuevo_expires = (datetime.now() + timedelta(days={T("dias_30"):30,T("dias_60"):60,T("dias_90"):90}[opcion_exp])).isoformat()

                ok = editar_secreto(secreto.id, self.usuario.id, enc, nuevo_nombre, nuevo_cat, nuevo_expires)
                if not ok:
                    _modal_msg(box, T("error"), T("editar_error"), "error")
                    return
                registrar_auditoria(self.usuario.id, "editar", nuevo_nombre)
                cerrar()
                self._cambiar_vista("secretos")

            _boton(box, T("guardar_cambios"), _guardar).pack(fill="x", ipady=5, pady=(4, 0))
            _boton_oscuro(box, T("cancelar"), cerrar).pack(fill="x", ipady=4, pady=(6, 0))

        self._modal(construir)

    def _historial_secreto(self, secreto):
        versiones = listar_versiones(secreto.id, self.usuario.id)

        def construir(box, cerrar):
            tk.Label(box, text=T("historial_secreto", name=secreto.name), font=("Courier New", 13, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
            tk.Label(box, text=T("versiones", n=len(versiones)),
                     font=FONT_TINY, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w", pady=(2, 0))
            tk.Frame(box, height=1, bg=BORDER).pack(fill="x", pady=10)

            if not versiones:
                tk.Label(box, text=T("sin_historial"),
                         font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(pady=10)
                _boton_oscuro(box, T("cerrar"), cerrar).pack(fill="x", ipady=4, pady=(10, 0))
                return

            for i, v in enumerate(versiones):
                fila = tk.Frame(box, bg=BG if i % 2 == 0 else BG_ENTRY, padx=8, pady=6)
                fila.pack(fill="x")
                fecha = v.changed_at[:16].replace("T", " ")
                tk.Label(fila, text=f"v{len(versiones)-i}  —  {fecha}",
                         font=FONT_TINY, fg=FG_DIM, bg=fila["bg"]).pack(side="left")

                def _restaurar(ver=v):
                    def _hacer_restaurar():
                        ok = restaurar_version(ver.id, secreto.id, self.usuario.id)
                        if not ok:
                            _modal_msg(box, T("error"), T("restaurar_error"), "error")
                            return
                        registrar_auditoria(self.usuario.id, "restaurar", secreto.name)
                        cerrar()
                        self._cambiar_vista("secretos")
                    _modal_confirmar(box, T("confirmar"), T("restaurar_confirmar"), _hacer_restaurar)

                _boton(fila, T("restaurar_btn"), _restaurar, color=AMARILLO).pack(side="right", ipadx=6, ipady=2)

            _boton_oscuro(box, T("cerrar"), cerrar).pack(fill="x", ipady=4, pady=(10, 0))

        self._modal(construir)

    # ---- Vista: actividad ----

    def _vista_actividad(self):
        ct = self._content
        panel = tk.Frame(ct, bg=BG, padx=28, pady=24)
        panel.pack(fill="both", expand=True)

        tk.Label(panel, text=T("actividad"), font=("Courier New", 18, "bold"), fg=ACCENT, bg=BG
                 ).pack(anchor="w")
        tk.Label(panel, text=T("historial_acciones"), font=FONT_SMALL, fg=FG_DIM, bg=BG
                 ).pack(anchor="w", pady=(2, 0))
        tk.Frame(panel, height=1, bg=BORDER).pack(fill="x", pady=12)

        entradas = listar_auditoria(self.usuario.id, limite=200)
        if not entradas:
            tk.Label(panel, text=T("sin_actividad"), font=FONT_SMALL, fg=FG_DIM, bg=BG
                     ).pack(pady=20)
            return

        ACCION_COLORES = {
            "crear":     ACCENT,
            "ver":       FG_DIM,
            "copiar":    AMARILLO,
            "eliminar":  DANGER,
            "editar":    CURSOR_COL,
            "restaurar": "#bc8cff",
        }

        wrap = tk.Frame(panel, bg=BG)
        wrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview, style="Vertical.TScrollbar")
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")
        canvas.configure(yscrollcommand=sb.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("inner", width=e.width))
        canvas.unbind_all("<MouseWheel>")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        canvas.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for i, entrada in enumerate(entradas):
            fila = tk.Frame(inner, bg=BG_PANEL if i % 2 == 0 else BG, padx=12, pady=7)
            fila.pack(fill="x")
            color = ACCION_COLORES.get(entrada.action, FG_DIM)
            tk.Label(fila, text=f"[{entrada.action:^10}]", font=FONT_TINY, fg=color,
                     bg=fila["bg"], width=12).pack(side="left")
            tk.Label(fila, text=f"@{self.usuario.username}  ·  {entrada.secret_name}",
                     font=FONT_SMALL, fg=FG, bg=fila["bg"]).pack(side="left", padx=(10, 0))
            fecha = entrada.timestamp[:16].replace("T", " ") if "T" in entrada.timestamp else entrada.timestamp[:16]
            tk.Label(fila, text=fecha, font=FONT_TINY, fg=FG_DIM,
                     bg=fila["bg"]).pack(side="right")

    # ---- Config 2FA ----

    def _abrir_config_2fa(self):
        cfg = auth.obtener_config_2fa(self.usuario.username)
        if cfg is None:
            return

        smtp_ok    = auth._smtp_configurado()
        touch_ok   = _touch_id_disponible()

        def construir(box, cerrar):
            tk.Label(box, text=T("2fa_titulo"), font=("Courier New", 14, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
            estado_txt = T("2fa_activado_estado", method=cfg['method']) if cfg["enabled"] else T("2fa_desactivado_estado")
            tk.Label(box, text=f"{T('estado_lbl')}: {estado_txt}", font=FONT_SMALL,
                     fg=ACCENT if cfg["enabled"] else DANGER, bg=BG_PANEL).pack(anchor="w", pady=(6, 0))
            tk.Frame(box, height=1, bg=BORDER).pack(fill="x", pady=12)

            if cfg["enabled"]:
                def _desactivar():
                    cerrar()
                    def _ok_desactivar():
                        auth.desactivar_2fa(self.usuario.id)
                        _modal_msg(self._content, T("confirmar"), T("2fa_desactivado_ok"))
                    self._verificar_2fa_antes_de(cfg, _ok_desactivar)
                _boton(box, T("desactivar_2fa"), _desactivar, color=DANGER).pack(fill="x", ipady=5)
            else:
                tk.Label(box, text=T("elegir_metodo"), font=FONT_SMALL, fg=FG_DIM,
                         bg=BG_PANEL).pack(anchor="w")

                def _activar_app():
                    cerrar()
                    totp_sec = auth.generar_secreto_totp()
                    self._setup_totp(totp_sec, auth.uri_totp(self.usuario.username, totp_sec))
                _boton(box, T("app_autenticadora_btn"), _activar_app).pack(fill="x", ipady=5, pady=(8, 0))

                if smtp_ok:
                    def _activar_email():
                        auth.activar_2fa(self.usuario.id, "email")
                        _modal_msg(box, "2FA", T("2fa_email_ok", email=cfg["email"]), on_cerrar=cerrar)
                    _boton(box, T("email_2fa_btn", email=cfg["email"]), _activar_email,
                           color=AMARILLO).pack(fill="x", ipady=5, pady=(8, 0))
                else:
                    tk.Label(box, text=T("email_no_disponible"),
                             font=FONT_TINY, fg=DANGER, bg=BG_PANEL).pack(anchor="w", pady=(4, 0))

                if touch_ok:
                    def _activar_bio():
                        if _verificar_touch_id():
                            auth.activar_2fa(self.usuario.id, "biometrico")
                            _modal_msg(box, "2FA", T("touch_id_ok"), on_cerrar=cerrar)
                        else:
                            _modal_msg(box, "Touch ID", T("verificacion_fallo"), "error")
                    _boton(box, T("touch_id_btn"), _activar_bio,
                           color=CURSOR_COL).pack(fill="x", ipady=5, pady=(8, 0))

            _boton_oscuro(box, T("cancelar"), cerrar).pack(fill="x", ipady=4, pady=(10, 0))

        self._modal(construir)

    def _verificar_2fa_antes_de(self, cfg: dict, accion_ok):
        """Muestra un dialogo de verificacion 2FA y ejecuta accion_ok si pasa."""
        method = cfg.get("method", "")

        if method == "biometrico":
            if _verificar_touch_id():
                accion_ok()
            else:
                _modal_msg(self._content, "Touch ID", T("verificacion_fallo"), "error")
            return

        if method == "app":
            def construir(box, cerrar):
                tk.Label(box, text=T("verificar_identidad"), font=("Courier New", 13, "bold"),
                         fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
                tk.Label(box, text=T("ingresa_cod_app"),
                         font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w", pady=(8, 4))
                e = _entry(box, width=20)
                e.pack(fill="x", ipady=5)
                e.focus_set()
                def _ok():
                    if auth.verificar_totp(cfg["secret"], e.get().strip()):
                        cerrar()
                        accion_ok()
                    else:
                        _modal_msg(box, T("error"), T("cod_incorrecto"), "error")
                _boton(box, T("verificar_btn"), _ok).pack(fill="x", ipady=5, pady=(8, 0))
                _boton_oscuro(box, T("cancelar"), cerrar).pack(fill="x", ipady=4, pady=(6, 0))
            self._modal(construir)
            return

        if method == "email":
            try:
                auth.generar_otp_2fa_email(self.usuario.username)
            except Exception as ex:
                _modal_msg(self._content, T("error"), str(ex), "error")
                return
            def construir(box, cerrar):
                tk.Label(box, text=T("verificar_identidad"), font=("Courier New", 13, "bold"),
                         fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
                tk.Label(box, text=T("ingresa_cod_email"),
                         font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w", pady=(8, 4))
                e = _entry(box, width=20)
                e.pack(fill="x", ipady=5)
                e.focus_set()
                def _ok():
                    if auth.verificar_otp_2fa(self.usuario.username, e.get().strip()):
                        cerrar()
                        accion_ok()
                    else:
                        _modal_msg(box, T("error"), T("cod_incorrecto"), "error")
                _boton(box, T("verificar_btn"), _ok).pack(fill="x", ipady=5, pady=(8, 0))
                _boton_oscuro(box, T("cancelar"), cerrar).pack(fill="x", ipady=4, pady=(6, 0))
            self._modal(construir)
            return

        # Fallback sin 2FA configurado: ejecutar directamente
        accion_ok()

    def _setup_totp(self, totp_sec: str, uri: str):
        def construir(box, cerrar):
            tk.Label(box, text=T("config_totp"), font=("Courier New", 13, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")

            # Mostrar QR si qrcode esta disponible
            if _QR_OK:
                try:
                    qr = qrcode.QRCode(box_size=4, border=2)
                    qr.add_data(uri)
                    qr.make(fit=True)
                    img_pil = qr.make_image(fill_color="white", back_color="#161b22")
                    buf = BytesIO()
                    img_pil.save(buf, format="PNG")
                    buf.seek(0)
                    photo = ImageTk.PhotoImage(Image.open(buf))
                    lbl_qr = tk.Label(box, image=photo, bg=BG_PANEL)
                    lbl_qr.image = photo  # mantener referencia
                    lbl_qr.pack(pady=(8, 4))
                    tk.Label(box, text=T("escanear_qr"),
                             font=FONT_TINY, fg=FG_DIM, bg=BG_PANEL).pack()
                except Exception:
                    pass  # Si falla la imagen, continua con instrucciones manuales
            else:
                for paso in T("totp_pasos"):
                    tk.Label(box, text=paso, font=FONT_TINY, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w", pady=(4, 0))

            tk.Label(box, text=T("secreto_lbl"), font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w", pady=(10, 2))
            campo = _entry(box, width=44)
            campo.insert(0, totp_sec)
            campo.configure(state="readonly")
            campo.pack(fill="x", ipady=5)
            tk.Label(box, text=T("cod_verificacion_lbl"), font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w", pady=(10, 2))
            entrada = _entry(box, width=44)
            entrada.pack(fill="x", ipady=5)
            entrada.focus_set()
            def _confirmar():
                if not auth.verificar_totp(totp_sec, entrada.get().strip()):
                    _modal_msg(box, T("incorrecto"), T("cod_no_coincide"), "error")
                    return
                auth.activar_2fa(self.usuario.id, "app", totp_sec)
                _modal_msg(box, T("confirmar"), T("totp_activado"), on_cerrar=cerrar)
            _boton(box, T("confirmar_activar"), _confirmar).pack(fill="x", ipady=5, pady=(12, 0))
            _boton_oscuro(box, T("cancelar"), cerrar).pack(fill="x", ipady=4, pady=(6, 0))

        self._modal(construir)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main():
    Aplicacion().mainloop()


if __name__ == "__main__":
    main()
