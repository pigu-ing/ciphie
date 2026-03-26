"""
frontend/app.py — Interfaz de escritorio de Ciphie con Tkinter (stdlib).

Tkinter viene incluido en Python, no requiere instalación.
La interfaz usa una ventana principal (Aplicacion) que intercambia
"pantallas" (Frames) según el estado: login → registro → dashboard.
"""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

# Añadimos backend/ al path para poder importar los módulos de la app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import auth, crypto
from app.database import agregar_secreto, eliminar_secreto, inicializar_bd, listar_secretos

# Crear las tablas al arrancar (no hace nada si ya existen)
inicializar_bd()

# ---------------------------------------------------------------------------
# Constantes de estilo
# ---------------------------------------------------------------------------
BG = "#ffffff"
BG_HEADER = "#f8f8f8"
COLOR_PRIMARIO = "#2563eb"       # azul
COLOR_PELIGRO = "#dc2626"        # rojo
FONT = ("Helvetica", 12)
FONT_GRANDE = ("Helvetica", 22, "bold")
FONT_CAPTION = ("Helvetica", 10)
PAD = 20


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------

class Aplicacion(tk.Tk):
    """
    Ventana raíz de la aplicación.
    Gestiona la navegación entre pantallas limpiando y recargando frames.
    """

    def __init__(self):
        super().__init__()
        self.title("Ciphie — Secrets Manager")
        self.geometry("460x540")
        self.resizable(False, False)
        self.configure(bg=BG)
        # Centrar la ventana en la pantalla
        self.eval("tk::PlaceWindow . center")
        self.ir_a_login()

    def _limpiar(self) -> None:
        """Destruye todos los widgets actuales de la ventana."""
        for widget in self.winfo_children():
            widget.destroy()

    def ir_a_login(self) -> None:
        self._limpiar()
        PantallaLogin(self).pack(fill="both", expand=True)

    def ir_a_registro(self) -> None:
        self._limpiar()
        PantallaRegistro(self).pack(fill="both", expand=True)

    def ir_a_dashboard(self, usuario: auth.Usuario) -> None:
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

    def _construir(self) -> None:
        tk.Label(self, text="Ciphie", font=FONT_GRANDE, bg=BG).pack(pady=(10, 0))
        tk.Label(self, text="Secrets Manager", font=FONT_CAPTION, fg="gray", bg=BG).pack()
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=15)

        tk.Label(self, text="Usuario", font=FONT, bg=BG, anchor="w").pack(fill="x")
        self._usuario = tk.Entry(self, font=FONT)
        self._usuario.pack(fill="x", ipady=4, pady=(2, 10))
        self._usuario.focus_set()

        tk.Label(self, text="Contraseña", font=FONT, bg=BG, anchor="w").pack(fill="x")
        self._password = tk.Entry(self, font=FONT, show="*")
        self._password.pack(fill="x", ipady=4, pady=(2, 20))
        # Enter en el campo de contraseña dispara el login
        self._password.bind("<Return>", lambda _: self._login())

        btn = tk.Button(
            self, text="Entrar", font=FONT,
            bg=COLOR_PRIMARIO, fg="white", relief="flat",
            cursor="hand2", command=self._login,
        )
        btn.pack(fill="x", ipady=6)

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=15)
        tk.Label(self, text="¿No tienes cuenta?", font=FONT_CAPTION, fg="gray", bg=BG).pack()
        tk.Button(
            self, text="Registrarse", font=FONT,
            bg=BG, fg=COLOR_PRIMARIO, relief="flat",
            cursor="hand2", command=self.app.ir_a_registro,
        ).pack(fill="x", ipady=4, pady=(4, 0))

    def _login(self) -> None:
        username = self._usuario.get().strip()
        password = self._password.get()

        if not username or not password:
            messagebox.showwarning("Campos vacíos", "Completa todos los campos.")
            return

        usuario = auth.autenticar_usuario(username, password)
        if usuario is None:
            messagebox.showerror("Error", "Usuario o contraseña incorrectos.")
            self._password.delete(0, tk.END)
            return

        self.app.ir_a_dashboard(usuario)


# ---------------------------------------------------------------------------
# Pantalla de registro
# ---------------------------------------------------------------------------

class PantallaRegistro(tk.Frame):
    def __init__(self, app: Aplicacion):
        super().__init__(app, bg=BG, padx=PAD, pady=PAD)
        self.app = app
        self._construir()

    def _construir(self) -> None:
        tk.Label(self, text="Crear cuenta", font=FONT_GRANDE, bg=BG).pack(pady=(10, 0))
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=15)

        campos = [
            ("Usuario", False),
            ("Email", False),
            ("Contraseña", True),
            ("Confirmar contraseña", True),
        ]
        self._entradas: dict[str, tk.Entry] = {}
        for etiqueta, es_password in campos:
            tk.Label(self, text=etiqueta, font=FONT, bg=BG, anchor="w").pack(fill="x")
            entrada = tk.Entry(self, font=FONT, show="*" if es_password else "")
            entrada.pack(fill="x", ipady=4, pady=(2, 10))
            self._entradas[etiqueta] = entrada

        self._entradas["Usuario"].focus_set()

        tk.Button(
            self, text="Crear cuenta", font=FONT,
            bg=COLOR_PRIMARIO, fg="white", relief="flat",
            cursor="hand2", command=self._registrar,
        ).pack(fill="x", ipady=6)

        tk.Button(
            self, text="Ya tengo cuenta", font=FONT,
            bg=BG, fg=COLOR_PRIMARIO, relief="flat",
            cursor="hand2", command=self.app.ir_a_login,
        ).pack(fill="x", ipady=4, pady=(8, 0))

    def _registrar(self) -> None:
        username = self._entradas["Usuario"].get().strip()
        email = self._entradas["Email"].get().strip()
        password = self._entradas["Contraseña"].get()
        confirmar = self._entradas["Confirmar contraseña"].get()

        if not all([username, email, password, confirmar]):
            messagebox.showwarning("Campos vacíos", "Completa todos los campos.")
            return

        if password != confirmar:
            messagebox.showerror("Error", "Las contraseñas no coinciden.")
            return

        try:
            auth.registrar_usuario(username, email, password)
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return

        messagebox.showinfo("Cuenta creada", "Cuenta creada correctamente. Ahora inicia sesión.")
        self.app.ir_a_login()


# ---------------------------------------------------------------------------
# Pantalla de dashboard
# ---------------------------------------------------------------------------

class PantallaDashboard(tk.Frame):
    def __init__(self, app: Aplicacion, usuario: auth.Usuario):
        super().__init__(app, bg=BG)
        self.app = app
        self.usuario = usuario
        self._construir()
        self._cargar_secretos()

    def _construir(self) -> None:
        # --- Cabecera ---
        cabecera = tk.Frame(self, bg=BG_HEADER, padx=PAD, pady=10)
        cabecera.pack(fill="x")

        tk.Label(
            cabecera, text="Mis secretos", font=("Helvetica", 16, "bold"),
            bg=BG_HEADER,
        ).pack(side="left")

        tk.Label(
            cabecera, text=f"  {self.usuario.username}",
            font=FONT_CAPTION, fg="gray", bg=BG_HEADER,
        ).pack(side="left")

        tk.Button(
            cabecera, text="Cerrar sesión", font=FONT_CAPTION,
            bg=BG_HEADER, fg=COLOR_PELIGRO, relief="flat",
            cursor="hand2", command=self.app.ir_a_login,
        ).pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        # --- Formulario para agregar secreto ---
        form = tk.Frame(self, bg=BG, padx=PAD, pady=12)
        form.pack(fill="x")

        tk.Label(form, text="Nombre", font=FONT_CAPTION, fg="gray", bg=BG).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(form, text="Valor", font=FONT_CAPTION, fg="gray", bg=BG).grid(
            row=0, column=1, sticky="w", padx=(10, 0)
        )

        self._nombre = tk.Entry(form, font=FONT)
        self._nombre.grid(row=1, column=0, ipady=4, sticky="ew")

        self._valor = tk.Entry(form, font=FONT, show="*")
        self._valor.grid(row=1, column=1, ipady=4, sticky="ew", padx=(10, 0))

        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        tk.Button(
            form, text="Guardar", font=FONT,
            bg=COLOR_PRIMARIO, fg="white", relief="flat",
            cursor="hand2", command=self._guardar_secreto,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0), ipady=5)

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        # --- Tabla de secretos (Treeview) ---
        contenedor = tk.Frame(self, bg=BG, padx=PAD, pady=10)
        contenedor.pack(fill="both", expand=True)

        tk.Label(contenedor, text="Secretos guardados", font=FONT, bg=BG, anchor="w").pack(
            fill="x", pady=(0, 6)
        )

        cols = ("Nombre", "Creado")
        self._tabla = ttk.Treeview(contenedor, columns=cols, show="headings", height=6)
        self._tabla.heading("Nombre", text="Nombre")
        self._tabla.heading("Creado", text="Creado")
        self._tabla.column("Nombre", width=200)
        self._tabla.column("Creado", width=150)
        self._tabla.pack(fill="both", expand=True)

        # --- Botones de acción ---
        botones = tk.Frame(self, bg=BG, padx=PAD, pady=8)
        botones.pack(fill="x")

        for texto, comando, color in [
            ("Ver valor",  self._ver_secreto, COLOR_PRIMARIO),
            ("Copiar",     self._copiar_secreto, "#059669"),
            ("Eliminar",   self._eliminar_secreto, COLOR_PELIGRO),
        ]:
            tk.Button(
                botones, text=texto, font=FONT_CAPTION,
                bg=color, fg="white", relief="flat",
                cursor="hand2", command=comando,
            ).pack(side="left", padx=(0, 8), ipady=4, ipadx=8)

    # --- Lógica de la tabla ---

    def _cargar_secretos(self) -> None:
        """Lee los secretos de la BD y los muestra en la tabla."""
        # Limpia la tabla antes de recargar
        for item in self._tabla.get_children():
            self._tabla.delete(item)

        secretos = listar_secretos(self.usuario.id)
        for s in secretos:
            # Guardamos el id como tag oculto para poder recuperarlo luego
            self._tabla.insert("", "end", iid=str(s.id), values=(s.name, s.created_at))

    def _secreto_seleccionado(self) -> str | None:
        """Devuelve el id del secreto seleccionado, o muestra aviso si no hay ninguno."""
        seleccion = self._tabla.selection()
        if not seleccion:
            messagebox.showwarning("Sin selección", "Selecciona un secreto de la lista.")
            return None
        return seleccion[0]  # el iid es el id del secreto

    def _guardar_secreto(self) -> None:
        nombre = self._nombre.get().strip()
        valor = self._valor.get()

        if not nombre or not valor:
            messagebox.showwarning("Campos vacíos", "Completa el nombre y el valor.")
            return

        try:
            valor_cifrado = crypto.cifrar(valor)
            agregar_secreto(nombre, valor_cifrado, self.usuario.id)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        self._nombre.delete(0, tk.END)
        self._valor.delete(0, tk.END)
        self._cargar_secretos()

    def _ver_secreto(self) -> None:
        secreto_id = self._secreto_seleccionado()
        if secreto_id is None:
            return

        # Buscamos el secreto en la lista para obtener el valor cifrado
        secretos = listar_secretos(self.usuario.id)
        secreto = next((s for s in secretos if str(s.id) == secreto_id), None)
        if secreto is None:
            return

        try:
            valor = crypto.descifrar(secreto.encrypted_value)
        except ValueError as e:
            messagebox.showerror("Error de cifrado", str(e))
            return

        # Mostrar en un diálogo que se puede cerrar
        dialogo = tk.Toplevel(self)
        dialogo.title(f"Secreto: {secreto.name}")
        dialogo.geometry("380x160")
        dialogo.resizable(False, False)
        dialogo.configure(bg=BG, padx=PAD, pady=PAD)

        tk.Label(dialogo, text=secreto.name, font=("Helvetica", 13, "bold"), bg=BG).pack(anchor="w")
        tk.Label(dialogo, text="Valor:", font=FONT_CAPTION, fg="gray", bg=BG).pack(anchor="w", pady=(8, 2))

        # Campo de texto solo lectura con el valor descifrado
        campo = tk.Entry(dialogo, font=FONT)
        campo.insert(0, valor)
        campo.configure(state="readonly")
        campo.pack(fill="x", ipady=4)

        tk.Button(
            dialogo, text="Cerrar", font=FONT,
            bg=BG, relief="flat", cursor="hand2",
            command=dialogo.destroy,
        ).pack(pady=(12, 0))

    def _copiar_secreto(self) -> None:
        secreto_id = self._secreto_seleccionado()
        if secreto_id is None:
            return

        secretos = listar_secretos(self.usuario.id)
        secreto = next((s for s in secretos if str(s.id) == secreto_id), None)
        if secreto is None:
            return

        try:
            valor = crypto.descifrar(secreto.encrypted_value)
        except ValueError as e:
            messagebox.showerror("Error de cifrado", str(e))
            return

        # Copiar al portapapeles del sistema
        self.app.clipboard_clear()
        self.app.clipboard_append(valor)
        messagebox.showinfo("Copiado", f'"{secreto.name}" copiado al portapapeles.')

    def _eliminar_secreto(self) -> None:
        secreto_id = self._secreto_seleccionado()
        if secreto_id is None:
            return

        nombre = self._tabla.item(secreto_id)["values"][0]
        confirmar = messagebox.askyesno(
            "Confirmar eliminación",
            f'¿Eliminar el secreto "{nombre}"?\nEsta acción no se puede deshacer.',
        )
        if not confirmar:
            return

        eliminar_secreto(int(secreto_id), self.usuario.id)
        self._cargar_secretos()


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    app = Aplicacion()
    app.mainloop()


if __name__ == "__main__":
    main()
