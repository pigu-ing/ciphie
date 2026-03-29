"""
frontend/app.py — Interfaz de escritorio de Ciphie con Tkinter (stdlib).
"""

import re
import subprocess
import sys
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import auth, crypto
from app.database import (
    agregar_secreto, editar_secreto, eliminar_secreto, inicializar_bd,
    listar_auditoria, listar_secretos, listar_usuarios_basico, listar_versiones,
    obtener_secreto, registrar_auditoria, restaurar_version,
    secretos_por_vencer, secretos_vencidos,
)

inicializar_bd()

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

CATEGORIAS = ["contraseña", "api key", "token", "nota", "otro"]

# Colores de categoría
CAT_COLORS = {
    "contraseña": "#3fb950",
    "api key":    "#58a6ff",
    "token":      "#d29922",
    "nota":       "#bc8cff",
    "otro":       "#7d8590",
}


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
    """Campo contraseña con candado 🔒/🔓."""
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
                    bg=BG_ENTRY, fg=FG_DIM, activebackground=BG_ENTRY, activeforeground=FG,
                    relief="flat", cursor="hand2", bd=0, highlightbackground=BG_ENTRY,
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
        tk.Label(self, text="[ secrets manager ]", font=FONT_SMALL, fg=FG_DIM, bg=BG).pack(pady=(0, 4))
        _separador(self).pack(fill="x", pady=14)

        _label(self, "usuario:", font=FONT_MONO, fg=FG_DIM, anchor="w").pack(fill="x")
        self._usuario = _entry(self)
        self._usuario.pack(fill="x", ipady=5, pady=(2, 10))
        self._usuario.focus_set()

        _label(self, "contraseña:", font=FONT_MONO, fg=FG_DIM, anchor="w").pack(fill="x")
        _frm, self._password = _entry_password(self)
        _frm.pack(fill="x", pady=(2, 18))
        self._password.bind("<Return>", lambda _: self._login())

        _boton(self, "> entrar", self._login).pack(fill="x", ipady=6)
        _separador(self).pack(fill="x", pady=14)
        tk.Label(self, text="¿no tienes cuenta?", font=FONT_SMALL, fg=FG_DIM, bg=BG).pack()
        btn = _boton(self, "[ registrarse ]", self.app.ir_a_registro, color=BG_ENTRY)
        btn.configure(fg=ACCENT)
        btn.pack(fill="x", ipady=4, pady=(4, 0))

    def _login(self):
        username = self._usuario.get().strip()
        password = self._password.get()
        if not username or not password:
            messagebox.showwarning("campos vacíos", "completa todos los campos.")
            return
        try:
            estado, usuario = auth.autenticar_paso1(username, password)
        except Exception as e:
            messagebox.showerror("error", str(e))
            return
        if estado == "fallo":
            messagebox.showerror("acceso denegado", "usuario o contraseña incorrectos.")
            self._password.delete(0, tk.END)
        elif estado == "ok":
            self.app.ir_a_dashboard(usuario)
        elif estado == "2fa_requerido":
            self.app.ir_a_elegir_2fa(username)


# ---------------------------------------------------------------------------
# Utilidad: seguridad de contraseña
# ---------------------------------------------------------------------------

def _calcular_seguridad(password: str) -> "tuple[int, str, str]":
    score = sum([
        len(password) >= 12,
        bool(re.search(r'[A-Z]', password) and re.search(r'[a-z]', password)),
        bool(re.search(r'\d', password)),
        bool(re.search(r'[!@#$%^&*()\-_=+\[\]{};:\'",.<>?/\\|`~]', password)),
    ])
    niveles = {0: ("", BORDER), 1: ("muy débil", DANGER), 2: ("débil", AMARILLO),
               3: ("media", AMARILLO), 4: ("fuerte", ACCENT)}
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
        tk.Label(self, text="crear cuenta", font=FONT_GRANDE, fg=ACCENT, bg=BG).pack(pady=(10, 0))
        tk.Label(self, text="[ nuevo usuario ]", font=FONT_SMALL, fg=FG_DIM, bg=BG).pack()
        _separador(self).pack(fill="x", pady=12)

        campos = [
            ("usuario:",               "Usuario",              False),
            ("email:",                 "Email",                False),
            ("celular (opcional):",    "Celular",              False),
            ("contraseña:",            "Contraseña",           True),
            ("confirmar contraseña:",  "Confirmar contraseña", True),
            ("frase de recuperación:", "Frase",                False),
        ]
        self._entradas: dict[str, tk.Entry] = {}
        for prompt, clave, es_pass in campos:
            _label(self, prompt, font=FONT_MONO, fg=FG_DIM, anchor="w").pack(fill="x")
            if es_pass:
                frm, e = _entry_password(self)
                frm.pack(fill="x", pady=(2, 4 if clave == "Contraseña" else 8))
            else:
                e = _entry(self)
                e.pack(fill="x", ipady=4, pady=(2, 4 if clave == "Contraseña" else 8))
            self._entradas[clave] = e
            if clave == "Contraseña":
                self._construir_barra()
                e.bind("<KeyRelease>", lambda _: self._actualizar_barra())

        self._entradas["Usuario"].focus_set()
        _boton(self, "> crear cuenta", self._registrar).pack(fill="x", ipady=6)
        btn = _boton(self, "[ ya tengo cuenta ]", self.app.ir_a_login, color=BG_ENTRY)
        btn.configure(fg=ACCENT)
        btn.pack(fill="x", ipady=4, pady=(8, 0))

    def _construir_barra(self):
        cont = tk.Frame(self, bg=BG)
        cont.pack(fill="x", pady=(0, 6))
        cf = tk.Frame(cont, bg=BG)
        cf.pack(fill="x", pady=(0, 3))
        self._criterio_labels = {}
        for i, (key, txt) in enumerate([("len","12+ chars"),("case","may/min"),("num","números"),("special","símbolos")]):
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

    def _actualizar_barra(self):
        pw = self._entradas["Contraseña"].get()
        score, texto, color = _calcular_seguridad(pw)
        for i, seg in enumerate(self._segmentos):
            seg.configure(bg=color if i < score else BORDER)
        self._nivel_label.configure(text=texto, fg=color if score > 0 else FG_DIM)
        checks = {"len": len(pw)>=12, "case": bool(re.search(r'[A-Z]',pw) and re.search(r'[a-z]',pw)),
                  "num": bool(re.search(r'\d',pw)), "special": bool(re.search(r'[!@#$%^&*()\-_=+\[\]{};:\'",.<>?/\\|`~]',pw))}
        nombres = {"len":"12+ chars","case":"may/min","num":"números","special":"símbolos"}
        for key, cumple in checks.items():
            self._criterio_labels[key].configure(
                text=f"{'✓' if cumple else '✗'} {nombres[key]}",
                fg=ACCENT if cumple else FG_DIM)

    def _registrar(self):
        username = self._entradas["Usuario"].get().strip()
        email    = self._entradas["Email"].get().strip()
        celular  = self._entradas["Celular"].get().strip()
        password = self._entradas["Contraseña"].get().strip()
        confirmar= self._entradas["Confirmar contraseña"].get().strip()
        frase    = self._entradas["Frase"].get().strip()
        if not all([username, email, password, confirmar, frase]):
            messagebox.showwarning("campos vacíos", "completa todos los campos obligatorios.")
            return
        if password != confirmar:
            messagebox.showerror("error", "las contraseñas no coinciden.")
            return
        try:
            auth.iniciar_registro(username, email, password, frase, phone=celular or None)
        except Exception as e:
            messagebox.showerror("error", str(e))
            return
        self.app.ir_a_verificacion_registro(username)


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
        tk.Label(self, text="verificar cuenta", font=FONT_GRANDE, fg=ACCENT, bg=BG).pack(pady=(20, 0))
        tk.Label(self, text="[ código de activación ]", font=FONT_SMALL, fg=FG_DIM, bg=BG).pack()
        _separador(self).pack(fill="x", pady=14)
        tk.Label(self, text="Te enviamos un código a tu email\n(y celular si lo ingresaste).",
                 font=FONT_SMALL, fg=FG_DIM, bg=BG, justify="center").pack(pady=(0, 12))
        _label(self, "código:", font=FONT_MONO, fg=FG_DIM, anchor="w").pack(fill="x")
        self._codigo = _entry(self)
        self._codigo.pack(fill="x", ipady=5, pady=(2, 18))
        self._codigo.focus_set()
        self._codigo.bind("<Return>", lambda _: self._verificar())
        _boton(self, "> verificar y activar cuenta", self._verificar).pack(fill="x", ipady=6)
        _separador(self).pack(fill="x", pady=14)
        _boton_oscuro(self, "[ reenviar código ]", self._reenviar, fg=ACCENT).pack(fill="x", ipady=4, pady=(0,6))
        _boton_oscuro(self, "[ volver ]", self.app.ir_a_login).pack(fill="x", ipady=4)

    def _verificar(self):
        codigo = self._codigo.get().strip()
        if not codigo:
            messagebox.showwarning("vacío", "ingresa el código.")
            return
        usuario = auth.verificar_otp_registro_y_activar(self.username, codigo)
        if usuario is None:
            messagebox.showerror("código inválido", "el código es incorrecto o ya expiró.")
            self._codigo.delete(0, tk.END)
            return
        messagebox.showinfo("cuenta activada", "¡Cuenta activa! Inicia sesión.")
        self.app.ir_a_login()

    def _reenviar(self):
        try:
            auth.reenviar_otp_registro(self.username)
            messagebox.showinfo("enviado", "nuevo código enviado.")
        except Exception as e:
            messagebox.showerror("error", str(e))


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
        tk.Label(self, text="verificación", font=FONT_GRANDE, fg=ACCENT, bg=BG).pack(pady=(20, 0))
        tk.Label(self, text="[ elegí cómo verificar tu identidad ]", font=FONT_SMALL, fg=FG_DIM, bg=BG).pack()
        _separador(self).pack(fill="x", pady=14)
        metodos = auth.get_metodos_2fa_disponibles(self.username)
        touch_id = _touch_id_disponible()
        if not metodos and not touch_id:
            tk.Label(self, text="No hay métodos configurados.\nConfigurá SMTP en .env para email.",
                     font=FONT_SMALL, fg=DANGER, bg=BG, justify="center").pack(pady=20)
        else:
            if "email" in metodos:
                _boton(self, "✉  código por email", lambda: self._elegir("email")).pack(fill="x", ipady=8, pady=(0,8))
            if "phone" in metodos:
                _boton(self, "📱  código por celular", lambda: self._elegir("phone")).pack(fill="x", ipady=8, pady=(0,8))
            if "totp_app" in metodos:
                btn = _boton(self, "🔑  app autenticadora", lambda: self._elegir("totp_app"), color=BTN_OSCURO)
                btn.configure(fg=FG)
                btn.pack(fill="x", ipady=8, pady=(0,8))
            if touch_id:
                _boton(self, "[Touch ID]  huella digital", self._touch_id, color=CURSOR_COL).pack(fill="x", ipady=8, pady=(0,8))
        _separador(self).pack(fill="x", pady=14)
        _boton_oscuro(self, "[ volver al login ]", self.app.ir_a_login).pack(fill="x", ipady=4)

    def _elegir(self, method: str):
        try:
            if method == "email":
                auth.generar_otp_2fa_email(self.username)
            elif method == "phone":
                auth.generar_otp_2fa_phone(self.username)
        except Exception as e:
            messagebox.showerror("error al enviar código", str(e))
            return
        self.app.ir_a_2fa_codigo(self.username, method)

    def _touch_id(self):
        if _verificar_touch_id():
            usuario = auth._obtener_usuario_activo(self.username)
            if usuario:
                self.app.ir_a_dashboard(usuario)
        else:
            messagebox.showerror("Touch ID", "verificación biométrica fallida o cancelada.")


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
        tk.Label(self, text="verificación", font=FONT_GRANDE, fg=ACCENT, bg=BG).pack(pady=(20, 0))
        _separador(self).pack(fill="x", pady=14)
        msgs = {"email": ("código enviado a tu email:", "revisa tu bandeja (expira en 5 min)"),
                "phone": ("código enviado a tu celular:", "revisa tus mensajes (expira en 5 min)"),
                "totp_app": ("código de tu app autenticadora:", "(Google Authenticator, Authy, etc.)")}
        linea1, linea2 = msgs.get(self.method, msgs["email"])
        _label(self, linea1, font=FONT_MONO, fg=FG_DIM, anchor="w").pack(fill="x")
        _label(self, linea2, font=FONT_TINY, fg=FG_DIM, anchor="w").pack(fill="x", pady=(0, 8))
        self._codigo = _entry(self)
        self._codigo.pack(fill="x", ipady=5, pady=(2, 18))
        self._codigo.focus_set()
        self._codigo.bind("<Return>", lambda _: self._verificar())
        _boton(self, "> verificar código", self._verificar).pack(fill="x", ipady=6)
        _separador(self).pack(fill="x", pady=14)
        if self.method in ("email", "phone"):
            _boton_oscuro(self, "[ reenviar código ]", self._reenviar, fg=ACCENT).pack(fill="x", ipady=4, pady=(0,6))
        _boton_oscuro(self, "[ elegir otro método ]", lambda: self.app.ir_a_elegir_2fa(self.username)).pack(fill="x", ipady=4, pady=(0,6))
        _boton_oscuro(self, "[ volver al login ]", self.app.ir_a_login).pack(fill="x", ipady=4)

    def _verificar(self):
        codigo = self._codigo.get().strip()
        if not codigo:
            messagebox.showwarning("vacío", "ingresa el código.")
            return
        usuario = (auth.autenticar_paso2_totp(self.username, codigo)
                   if self.method == "totp_app"
                   else auth.autenticar_paso2_generico(self.username, codigo))
        if usuario is None:
            messagebox.showerror("código inválido", "incorrecto o expirado.")
            self._codigo.delete(0, tk.END)
            return
        self.app.ir_a_dashboard(usuario)

    def _reenviar(self):
        try:
            if self.method == "email":
                auth.generar_otp_2fa_email(self.username)
            elif self.method == "phone":
                auth.generar_otp_2fa_phone(self.username)
            messagebox.showinfo("enviado", "nuevo código enviado.")
        except Exception as e:
            messagebox.showerror("error", str(e))


# ---------------------------------------------------------------------------
# Dashboard — diseño con sidebar
# ---------------------------------------------------------------------------

class PantallaDashboard(tk.Frame):
    def __init__(self, app: Aplicacion, usuario: auth.Usuario):
        super().__init__(app, bg=BG)
        self.app = app
        self.usuario = usuario
        self._vista_actual = None
        self._construir_layout()
        self._cambiar_vista("usuario")

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
        sb = self._sidebar

        # Logo + usuario
        tk.Label(sb, text="ciphie", font=("Courier New", 15, "bold"), fg=ACCENT, bg=BG_PANEL
                 ).pack(pady=(22, 2), padx=18, anchor="w")
        tk.Label(sb, text=f"@{self.usuario.username}", font=FONT_TINY, fg=FG_DIM, bg=BG_PANEL
                 ).pack(padx=18, anchor="w", pady=(0, 14))
        tk.Frame(sb, height=1, bg=BORDER).pack(fill="x")

        # Nav items
        self._nav_btns: dict[str, tk.Label] = {}
        for texto, vista in [("👤  usuario", "usuario"), ("➕  nuevo", "inicio"), ("🔒  secretos", "secretos"), ("📋  actividad", "actividad")]:
            btn = tk.Label(sb, text=texto, font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL,
                           cursor="hand2", anchor="w", padx=18, pady=10)
            btn.pack(fill="x")
            btn.bind("<Button-1>", lambda e, v=vista: self._cambiar_vista(v))
            btn.bind("<Enter>",    lambda e, b=btn: b.configure(bg=BORDER) if b["bg"] != BORDER else None)
            btn.bind("<Leave>",    lambda e, b=btn, v=vista: b.configure(
                bg=BORDER if self._vista_actual == v else BG_PANEL))
            self._nav_btns[vista] = btn

        # Logout en el fondo
        tk.Frame(sb, height=1, bg=BORDER).pack(side="bottom", fill="x")
        logout = tk.Label(sb, text="[ salir ]", font=FONT_SMALL, fg=DANGER, bg=BG_PANEL,
                          cursor="hand2", anchor="w", padx=18, pady=12)
        logout.pack(side="bottom", fill="x")
        logout.bind("<Button-1>", lambda e: self.app.ir_a_login())
        logout.bind("<Enter>", lambda e: logout.configure(bg=BORDER))
        logout.bind("<Leave>", lambda e: logout.configure(bg=BG_PANEL))

    # ---- Navegación entre vistas ----

    def _cambiar_vista(self, vista: str):
        self._vista_actual = vista
        for v, btn in self._nav_btns.items():
            btn.configure(bg=BORDER if v == vista else BG_PANEL,
                          fg=FG if v == vista else FG_DIM)
        for w in self._content.winfo_children():
            w.destroy()
        if vista == "inicio":
            self._vista_inicio()
        elif vista == "secretos":
            self._vista_lista_secretos()
        elif vista == "actividad":
            self._vista_actividad()
        elif vista == "usuario":
            self._vista_usuario()

    # ---- Vista: inicio (formulario nuevo secreto) ----

    def _vista_inicio(self):
        ct = self._content

        panel = tk.Frame(ct, bg=BG, padx=40, pady=40)
        panel.pack(fill="both", expand=True)

        tk.Label(panel, text="nuevo secreto", font=("Courier New", 18, "bold"), fg=ACCENT, bg=BG
                 ).pack(anchor="w")
        tk.Label(panel, text="agregá un secreto a tu bóveda", font=FONT_SMALL, fg=FG_DIM, bg=BG
                 ).pack(anchor="w", pady=(2, 0))
        tk.Frame(panel, height=1, bg=BORDER).pack(fill="x", pady=16)

        form = tk.Frame(panel, bg=BG)
        form.pack(fill="x")

        # Nombre
        tk.Label(form, text="nombre:", font=FONT_SMALL, fg=FG_DIM, bg=BG).pack(anchor="w")
        self._nombre = _entry(form, width=50)
        self._nombre.pack(fill="x", ipady=5, pady=(2, 12))
        self._nombre.focus_set()

        # Fila: categoría + expiry
        fila = tk.Frame(form, bg=BG)
        fila.pack(fill="x", pady=(0, 12))

        cf = tk.Frame(fila, bg=BG)
        cf.pack(side="left")
        tk.Label(cf, text="categoría:", font=FONT_SMALL, fg=FG_DIM, bg=BG).pack(anchor="w")
        self._categoria = tk.StringVar(value=CATEGORIAS[0])
        om = tk.OptionMenu(cf, self._categoria, *CATEGORIAS)
        om.configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER, activeforeground=FG,
                     highlightbackground=BG_ENTRY, relief="flat", font=FONT_SMALL,
                     cursor="hand2", width=12)
        om["menu"].configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER, activeforeground=FG,
                             font=FONT_SMALL, bd=0)
        om.pack(pady=(2, 0))

        ef = tk.Frame(fila, bg=BG)
        ef.pack(side="left", padx=(24, 0))
        tk.Label(ef, text="expira en:", font=FONT_SMALL, fg=FG_DIM, bg=BG).pack(anchor="w")
        self._expiry_var = tk.StringVar(value="nunca")
        om_exp = tk.OptionMenu(ef, self._expiry_var, *["nunca", "30 días", "60 días", "90 días", "personalizada"],
                               command=self._toggle_expiry_custom)
        om_exp.configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER, activeforeground=FG,
                         highlightbackground=BG_ENTRY, relief="flat", font=FONT_SMALL,
                         cursor="hand2", width=12)
        om_exp["menu"].configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER, activeforeground=FG,
                                 font=FONT_SMALL, bd=0)
        om_exp.pack(pady=(2, 0))
        self._expiry_custom_entry = _entry(ef, width=14)
        self._expiry_custom_entry.insert(0, "AAAA-MM-DD")

        _boton(form, "> guardar secreto", self._guardar_secreto).pack(anchor="w", ipadx=16, ipady=6, pady=(8, 0))

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
        tk.Label(hdr, text="secretos guardados", font=("Courier New", 15, "bold"), fg=ACCENT, bg=BG
                 ).pack(side="left")
        tk.Frame(ct, height=1, bg=BORDER).pack(fill="x")

        # Banner vencidos
        if vencidos:
            banner = tk.Frame(ct, bg="#2d1b1b", padx=16, pady=8)
            banner.pack(fill="x")
            tk.Label(banner, text=f"🔴  {len(vencidos)} secreto(s) vencido(s)",
                     font=FONT_SMALL, fg=DANGER, bg="#2d1b1b").pack(side="left")
            for sv in vencidos:
                _boton(banner, f"renovar {sv.name}", lambda s=sv: self._editar_secreto(s),
                       color=AMARILLO).pack(side="right", ipadx=6, ipady=2, padx=(4, 0))
            tk.Frame(ct, height=1, bg=BORDER).pack(fill="x")

        if not secretos:
            tk.Label(ct, text="no hay secretos guardados.", bg=BG, fg=FG_DIM,
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
        canvas.bind_all("<MouseWheel>", lambda e: canvas.xview_scroll(-1*(e.delta//120), "units"))
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
            tk.Label(hdr_col, text=f"  {cat}  ({len(por_cat[cat])})",
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
        m.add_command(label="  copiar",    command=lambda: self._copiar_secreto(secreto))
        m.add_command(label="  editar",    command=lambda: self._editar_secreto(secreto))
        m.add_command(label="  historial", command=lambda: self._historial_secreto(secreto))
        m.add_separator()
        m.add_command(label="  eliminar",  command=lambda: self._eliminar_secreto(secreto))
        m.post(event.x_root, event.y_root)

    # ---- Vista: usuario ----

    def _vista_usuario(self):
        ct = self._content
        panel = tk.Frame(ct, bg=BG, padx=28, pady=24)
        panel.pack(fill="both", expand=True)

        tk.Label(panel, text="perfil", font=("Courier New", 18, "bold"), fg=ACCENT, bg=BG
                 ).pack(anchor="w")
        tk.Frame(panel, height=1, bg=BORDER).pack(fill="x", pady=12)

        for etiqueta, valor in [("usuario", self.usuario.username), ("email", self.usuario.email)]:
            fila = tk.Frame(panel, bg=BG)
            fila.pack(fill="x", pady=(0, 8))
            tk.Label(fila, text=f"{etiqueta}:", font=FONT_MONO, fg=FG_DIM, bg=BG, width=10,
                     anchor="w").pack(side="left")
            tk.Label(fila, text=valor, font=FONT_SMALL, fg=FG, bg=BG).pack(side="left")

        tk.Frame(panel, height=1, bg=BORDER).pack(fill="x", pady=16)

        # — Seguridad —
        tk.Label(panel, text="seguridad", font=("Courier New", 14, "bold"), fg=FG_DIM, bg=BG
                 ).pack(anchor="w", pady=(0, 10))
        _boton(panel, "> configurar 2FA", self._abrir_config_2fa).pack(anchor="w", ipadx=10, ipady=5)

        tk.Frame(panel, height=1, bg=BORDER).pack(fill="x", pady=16)

        # — Cuentas —
        tk.Label(panel, text="cuentas", font=("Courier New", 14, "bold"), fg=FG_DIM, bg=BG
                 ).pack(anchor="w", pady=(0, 10))

        fila_btns = tk.Frame(panel, bg=BG)
        fila_btns.pack(anchor="w")
        _boton(fila_btns, "> nueva cuenta", self._crear_usuario_modal
               ).pack(side="left", ipadx=10, ipady=5)
        _boton_oscuro(fila_btns, "cambiar cuenta", self._cambiar_usuario_modal
                      ).pack(side="left", padx=(10, 0), ipadx=10, ipady=5)

    def _crear_usuario_modal(self):
        def construir(box, cerrar):
            tk.Label(box, text="nueva cuenta", font=("Courier New", 13, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
            tk.Frame(box, height=1, bg=BORDER).pack(fill="x", pady=10)

            campos = [("usuario:", False), ("email:", False), ("contraseña:", True),
                      ("frase de recuperación:", False)]
            entradas: dict[str, tk.Entry] = {}
            for prompt, es_pass in campos:
                tk.Label(box, text=prompt, font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
                if es_pass:
                    frm, e = _entry_password(box)
                    frm.pack(fill="x", pady=(2, 8))
                else:
                    e = _entry(box, width=38)
                    e.pack(fill="x", ipady=4, pady=(2, 8))
                entradas[prompt] = e

            def _guardar():
                username = entradas["usuario:"].get().strip()
                email    = entradas["email:"].get().strip()
                password = entradas["contraseña:"].get().strip()
                frase    = entradas["frase de recuperación:"].get().strip()
                if not all([username, email, password, frase]):
                    messagebox.showwarning("campos vacíos", "completa todos los campos.")
                    return
                try:
                    auth.registrar_usuario(username, email, password, frase)
                    messagebox.showinfo("cuenta creada", f"@{username} creado correctamente.")
                    cerrar()
                except Exception as ex:
                    messagebox.showerror("error", str(ex))

            _boton(box, "> crear cuenta", _guardar).pack(fill="x", ipady=5, pady=(4, 0))
            _boton_oscuro(box, "cancelar", cerrar).pack(fill="x", ipady=4, pady=(6, 0))

        self._modal(construir)

    def _cambiar_usuario_modal(self):
        usuarios = listar_usuarios_basico()

        def construir(box, cerrar):
            tk.Label(box, text="cambiar cuenta", font=("Courier New", 13, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
            tk.Frame(box, height=1, bg=BORDER).pack(fill="x", pady=10)

            if not usuarios:
                tk.Label(box, text="no hay otras cuentas.", font=FONT_SMALL,
                         fg=FG_DIM, bg=BG_PANEL).pack(pady=10)
                _boton_oscuro(box, "cerrar", cerrar).pack(fill="x", ipady=4, pady=(10, 0))
                return

            usuario_var = tk.StringVar(value=usuarios[0].username)
            tk.Label(box, text="seleccionar cuenta:", font=FONT_SMALL,
                     fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
            for u in usuarios:
                color = ACCENT if u.username == self.usuario.username else FG_DIM
                rb = tk.Radiobutton(box, text=f"@{u.username}", variable=usuario_var,
                                    value=u.username, font=FONT_SMALL,
                                    bg=BG_PANEL, fg=color, activebackground=BG_PANEL,
                                    selectcolor=BG_ENTRY, cursor="hand2")
                rb.pack(anchor="w", pady=(2, 0))

            tk.Label(box, text="contraseña:", font=FONT_SMALL, fg=FG_DIM,
                     bg=BG_PANEL).pack(anchor="w", pady=(10, 0))
            frm_pw, e_pw = _entry_password(box)
            frm_pw.pack(fill="x", pady=(2, 8))

            def _entrar():
                username = usuario_var.get()
                password = e_pw.get()
                if not password:
                    messagebox.showwarning("vacío", "ingresa la contraseña.")
                    return
                try:
                    estado, usuario = auth.autenticar_paso1(username, password)
                except Exception as ex:
                    messagebox.showerror("error", str(ex))
                    return
                cerrar()
                if estado == "ok":
                    self.app.ir_a_dashboard(usuario)
                elif estado == "2fa_requerido":
                    self.app.ir_a_elegir_2fa(username)
                else:
                    messagebox.showerror("acceso denegado", "contraseña incorrecta.")

            _boton(box, "> entrar", _entrar).pack(fill="x", ipady=5, pady=(4, 0))
            _boton_oscuro(box, "cancelar", cerrar).pack(fill="x", ipady=4, pady=(6, 0))

        self._modal(construir)

    # ---- Acciones secretos ----

    def _toggle_expiry_custom(self, valor):
        if valor == "personalizada":
            self._expiry_custom_entry.pack(fill="x", ipady=4)
        else:
            self._expiry_custom_entry.pack_forget()

    def _calcular_expires_at(self) -> "str | None":
        opcion = self._expiry_var.get()
        if opcion == "nunca":
            return None
        dias_map = {"30 días": 30, "60 días": 60, "90 días": 90}
        if opcion in dias_map:
            return (datetime.now() + timedelta(days=dias_map[opcion])).isoformat()
        # personalizada
        texto = self._expiry_custom_entry.get().strip()
        try:
            return datetime.strptime(texto, "%Y-%m-%d").isoformat()
        except ValueError:
            messagebox.showerror("fecha inválida", "usa el formato AAAA-MM-DD.")
            return "error"

    def _guardar_secreto(self):
        nombre    = self._nombre.get().strip()
        categoria = self._categoria.get()
        if not nombre:
            messagebox.showwarning("campo vacío", "ingresa un nombre.")
            return
        expires_at = self._calcular_expires_at()
        if expires_at == "error":
            return
        try:
            s = agregar_secreto(nombre, crypto.cifrar(""), self.usuario.id, categoria, expires_at)
            registrar_auditoria(self.usuario.id, "crear", nombre)
        except (ValueError, RuntimeError) as e:
            messagebox.showerror("error al guardar", str(e))
            return
        self._nombre.delete(0, tk.END)
        self._expiry_var.set("nunca")
        self._expiry_custom_entry.pack_forget()
        self._cambiar_vista("secretos")

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
            messagebox.showerror("error de cifrado", str(e))
            return
        registrar_auditoria(self.usuario.id, "ver", secreto.name)

        def construir(box, cerrar):
            tk.Label(box, text=f"[ {secreto.name} ]", font=("Courier New", 13, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
            tk.Label(box, text="valor:", font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL
                     ).pack(anchor="w", pady=(12, 2))
            campo = _entry(box, width=44)
            campo.insert(0, valor)
            campo.configure(state="readonly")
            campo.pack(fill="x", ipady=5)
            _boton_oscuro(box, "> cerrar", cerrar, fg=FG).pack(pady=(14, 0), ipady=4, fill="x")

        self._modal(construir)

    def _copiar_secreto(self, secreto):
        try:
            valor = crypto.descifrar(secreto.encrypted_value)
        except ValueError as e:
            messagebox.showerror("error de cifrado", str(e))
            return
        registrar_auditoria(self.usuario.id, "copiar", secreto.name)
        self.app.clipboard_clear()
        self.app.clipboard_append(valor)
        self.app.after(30_000, self.app.clipboard_clear)
        messagebox.showinfo("copiado", f'"{secreto.name}" en portapapeles.\nse borrará en 30 s.')

    def _eliminar_secreto(self, secreto):
        if not messagebox.askyesno("confirmar", f'¿eliminar "{secreto.name}"?\nno se puede deshacer.'):
            return
        try:
            eliminar_secreto(secreto.id, self.usuario.id)
            registrar_auditoria(self.usuario.id, "eliminar", secreto.name)
        except Exception as e:
            messagebox.showerror("error", str(e))
            return
        self._cambiar_vista("secretos")

    def _editar_secreto(self, secreto):
        def construir(box, cerrar):
            tk.Label(box, text="editar secreto", font=("Courier New", 13, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
            tk.Frame(box, height=1, bg=BORDER).pack(fill="x", pady=10)

            tk.Label(box, text="nombre:", font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
            e_nombre = _entry(box, width=44)
            e_nombre.insert(0, secreto.name)
            e_nombre.pack(fill="x", ipady=4, pady=(2, 8))

            tk.Label(box, text="categoría:", font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
            cat_var = tk.StringVar(value=secreto.category)
            om = tk.OptionMenu(box, cat_var, *CATEGORIAS)
            om.configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER, activeforeground=FG,
                         highlightbackground=BG_ENTRY, relief="flat", font=FONT_SMALL, cursor="hand2")
            om["menu"].configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER,
                                 activeforeground=FG, font=FONT_SMALL, bd=0)
            om.pack(anchor="w", pady=(2, 8))

            tk.Label(box, text="valor (vacío = no cambiar):", font=FONT_SMALL,
                     fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
            frm_v, e_valor = _entry_password(box)
            frm_v.pack(fill="x", pady=(2, 8))

            tk.Label(box, text="expira en:", font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w")
            opciones_exp = ["sin cambio", "nunca", "30 días", "60 días", "90 días", "personalizada"]
            exp_var = tk.StringVar(value="sin cambio")
            exp_custom = _entry(box, width=16)
            exp_custom.insert(0, "AAAA-MM-DD")

            def _on_exp(v):
                exp_custom.pack(fill="x", ipady=4, pady=(2, 8)) if v == "personalizada" else exp_custom.pack_forget()

            om_exp = tk.OptionMenu(box, exp_var, *opciones_exp, command=_on_exp)
            om_exp.configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER, activeforeground=FG,
                             highlightbackground=BG_ENTRY, relief="flat", font=FONT_SMALL, cursor="hand2")
            om_exp["menu"].configure(bg=BG_ENTRY, fg=FG, activebackground=BORDER,
                                     activeforeground=FG, font=FONT_SMALL, bd=0)
            om_exp.pack(anchor="w", pady=(2, 8))

            def _guardar():
                nuevo_nombre = e_nombre.get().strip() or secreto.name
                nuevo_cat    = cat_var.get()
                nuevo_valor  = e_valor.get().strip()
                opcion_exp   = exp_var.get()
                enc = crypto.cifrar(nuevo_valor) if nuevo_valor else secreto.encrypted_value
                if opcion_exp == "sin cambio":
                    nuevo_expires = secreto.expires_at
                elif opcion_exp == "nunca":
                    nuevo_expires = None
                elif opcion_exp == "personalizada":
                    try:
                        nuevo_expires = datetime.strptime(exp_custom.get().strip(), "%Y-%m-%d").isoformat()
                    except ValueError:
                        messagebox.showerror("fecha inválida", "usa el formato AAAA-MM-DD.")
                        return
                else:
                    nuevo_expires = (datetime.now() + timedelta(days={"30 días":30,"60 días":60,"90 días":90}[opcion_exp])).isoformat()
                ok = editar_secreto(secreto.id, self.usuario.id, enc, nuevo_nombre, nuevo_cat, nuevo_expires)
                if not ok:
                    messagebox.showerror("error", "no se pudo editar el secreto.")
                    return
                registrar_auditoria(self.usuario.id, "editar", nuevo_nombre)
                cerrar()
                self._cambiar_vista("secretos")

            _boton(box, "> guardar cambios", _guardar).pack(fill="x", ipady=5, pady=(4, 0))
            _boton_oscuro(box, "cancelar", cerrar).pack(fill="x", ipady=4, pady=(6, 0))

        self._modal(construir)

    def _historial_secreto(self, secreto):
        versiones = listar_versiones(secreto.id, self.usuario.id)

        def construir(box, cerrar):
            tk.Label(box, text=f"historial: {secreto.name}", font=("Courier New", 13, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
            tk.Label(box, text=f"{len(versiones)} versión(es) anterior(es)",
                     font=FONT_TINY, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w", pady=(2, 0))
            tk.Frame(box, height=1, bg=BORDER).pack(fill="x", pady=10)

            if not versiones:
                tk.Label(box, text="sin historial — este secreto no ha sido editado.",
                         font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(pady=10)
                _boton_oscuro(box, "cerrar", cerrar).pack(fill="x", ipady=4, pady=(10, 0))
                return

            for i, v in enumerate(versiones):
                fila = tk.Frame(box, bg=BG if i % 2 == 0 else BG_ENTRY, padx=8, pady=6)
                fila.pack(fill="x")
                fecha = v.changed_at[:16].replace("T", " ")
                tk.Label(fila, text=f"v{len(versiones)-i}  —  {fecha}",
                         font=FONT_TINY, fg=FG_DIM, bg=fila["bg"]).pack(side="left")

                def _restaurar(ver=v):
                    if not messagebox.askyesno("restaurar",
                            "¿restaurar esta versión?\nEl valor actual quedará guardado en el historial."):
                        return
                    ok = restaurar_version(ver.id, secreto.id, self.usuario.id)
                    if not ok:
                        messagebox.showerror("error", "no se pudo restaurar.")
                        return
                    registrar_auditoria(self.usuario.id, "restaurar", secreto.name)
                    cerrar()
                    self._cambiar_vista("secretos")

                _boton(fila, "restaurar", _restaurar, color=AMARILLO).pack(side="right", ipadx=6, ipady=2)

            _boton_oscuro(box, "cerrar", cerrar).pack(fill="x", ipady=4, pady=(10, 0))

        self._modal(construir)

    # ---- Vista: actividad ----

    def _vista_actividad(self):
        ct = self._content
        panel = tk.Frame(ct, bg=BG, padx=28, pady=24)
        panel.pack(fill="both", expand=True)

        tk.Label(panel, text="actividad", font=("Courier New", 18, "bold"), fg=ACCENT, bg=BG
                 ).pack(anchor="w")
        tk.Label(panel, text="historial de acciones", font=FONT_SMALL, fg=FG_DIM, bg=BG
                 ).pack(anchor="w", pady=(2, 0))
        tk.Frame(panel, height=1, bg=BORDER).pack(fill="x", pady=12)

        entradas = listar_auditoria(self.usuario.id, limite=200)
        if not entradas:
            tk.Label(panel, text="sin actividad registrada.", font=FONT_SMALL, fg=FG_DIM, bg=BG
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
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
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

        def construir(box, cerrar):
            tk.Label(box, text="autenticación de 2 pasos", font=("Courier New", 14, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
            estado_txt = f"activado ({cfg['method']})" if cfg["enabled"] else "desactivado"
            tk.Label(box, text=f"estado: {estado_txt}", font=FONT_SMALL,
                     fg=ACCENT if cfg["enabled"] else DANGER, bg=BG_PANEL).pack(anchor="w", pady=(6, 0))
            tk.Frame(box, height=1, bg=BORDER).pack(fill="x", pady=12)
            if cfg["enabled"]:
                def _desactivar():
                    auth.desactivar_2fa(self.usuario.id)
                    messagebox.showinfo("ok", "2FA desactivado.")
                    cerrar()
                _boton(box, "> desactivar 2FA", _desactivar, color=DANGER).pack(fill="x", ipady=5)
            else:
                tk.Label(box, text="elegir método:", font=FONT_SMALL, fg=FG_DIM,
                         bg=BG_PANEL).pack(anchor="w")
                def _activar_app():
                    cerrar()
                    totp_sec = auth.generar_secreto_totp()
                    self._setup_totp(totp_sec, auth.uri_totp(self.usuario.username, totp_sec))
                _boton(box, "> app autenticadora", _activar_app).pack(fill="x", ipady=5, pady=(8, 0))
                def _activar_email():
                    auth.activar_2fa(self.usuario.id, "email")
                    messagebox.showinfo("2FA activado", f"Códigos a:\n{cfg['email']}")
                    cerrar()
                _boton(box, f"> email  ({cfg['email']})", _activar_email,
                       color=AMARILLO).pack(fill="x", ipady=5, pady=(8, 0))
            _boton_oscuro(box, "cancelar", cerrar).pack(fill="x", ipady=4, pady=(10, 0))

        self._modal(construir)

    def _setup_totp(self, totp_sec: str, uri: str):
        def construir(box, cerrar):
            tk.Label(box, text="configurar app autenticadora", font=("Courier New", 13, "bold"),
                     fg=ACCENT, bg=BG_PANEL).pack(anchor="w")
            for paso in ["1. abrí tu app (Google Auth, Authy…)", "2. pulsá '+' → 'clave manual'",
                         "3. copiá el secreto de abajo y pegalo", "4. ingresá el código que te muestra"]:
                tk.Label(box, text=paso, font=FONT_TINY, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w", pady=(4, 0))
            tk.Label(box, text="secreto:", font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w", pady=(12, 2))
            campo = _entry(box, width=44)
            campo.insert(0, totp_sec)
            campo.configure(state="readonly")
            campo.pack(fill="x", ipady=5)
            tk.Label(box, text="código:", font=FONT_SMALL, fg=FG_DIM, bg=BG_PANEL).pack(anchor="w", pady=(12, 2))
            entrada = _entry(box, width=44)
            entrada.pack(fill="x", ipady=5)
            entrada.focus_set()
            def _confirmar():
                if not auth.verificar_totp(totp_sec, entrada.get().strip()):
                    messagebox.showerror("incorrecto", "el código no coincide.")
                    return
                auth.activar_2fa(self.usuario.id, "app", totp_sec)
                messagebox.showinfo("activado", "app autenticadora configurada.")
                cerrar()
            _boton(box, "> confirmar y activar", _confirmar).pack(fill="x", ipady=5, pady=(12, 0))
            _boton_oscuro(box, "cancelar", cerrar).pack(fill="x", ipady=4, pady=(6, 0))

        self._modal(construir)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main():
    Aplicacion().mainloop()


if __name__ == "__main__":
    main()
