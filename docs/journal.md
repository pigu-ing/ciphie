# Diario de desarrollo — Ciphie

Registro personal del progreso, decisiones y aprendizajes durante la construcción del proyecto.

---

## Plantilla de entrada

```
## [YYYY-MM-DD]

### Qué hice hoy
-

### Qué aprendí
-

### Problemas encontrados
-

### Cómo los resolví
-

### Próximos pasos
-
```

---

## [2026-03-29]

### Qué hice hoy
- Implementé 3 features nuevas en Ciphie: auditoría de accesos, versionado de secretos y expiración automática de credenciales.
- Reescribí `database.py` anadiendo las tablas `audit_log` y `secret_versions`, la columna `expires_at` en `secrets` (con migración automática via `ALTER TABLE` + try/except), nuevos dataclasses (`AuditEntry`, `SecretVersion`) y 7 funciones nuevas de CRUD.
- Actualicé `frontend/app.py`: sidebar con vista "📋 actividad", dropdown de expiración en el formulario de nuevo secreto, íconos ⚠️/🔴 en la lista, banner de secretos vencidos, opciones editar/historial en el menú ⋮, diálogos de edición y de historial con botón restaurar.
- Escribí 29 tests nuevos en 3 archivos (`test_audit.py`, `test_versioning.py`, `test_expiry.py`). Suite completa: 51 tests, todos en verde.

### Qué aprendí
- En SQLite, `ALTER TABLE ADD COLUMN` lanza excepción si la columna ya existe — envolverlo en try/except es el patrón correcto para migraciones sin romper bases de datos existentes.
- `restaurar_version()` debe guardar el valor actual antes de restaurar para que la operación sea reversible (el "restaurar" en sí se puede deshacer).
- En Tkinter/macOS, `tk.Label` con bindings es más confiable que `tk.Button` para respetar colores de fondo.

### Problemas encontrados
- El `Secreto` dataclass ya existía; anadir `expires_at` podía romper instancias creadas con `**dict(fila)` si la columna no estaba en todas las consultas.

### Cómo los resolví
- Anadí `expires_at` al final del dataclass con `= None` como default, y lo incluí en la constante `_COLS_SECRETO` usada por todas las consultas. Así todas las instancias reciben el campo y el código existente sigue funcionando sin cambios.

### Próximos pasos
- [ ] Implementar notificaciones proactivas (push/email) cuando un secreto está por vencer
- [ ] Agregar búsqueda/filtro en la lista de secretos
- [ ] Exportar/importar secretos cifrados

---

## [2026-03-25]

### Qué hice hoy
- Creé la estructura inicial del proyecto Ciphie
- Configuré FastAPI con un endpoint básico de health check
- Definí las variables de entorno necesarias en `.env.example`
- Elegí el stack: FastAPI + SQLAlchemy + SQLite + Streamlit (más adelante)

### Qué aprendí
- FastAPI genera documentación interactiva automáticamente en `/docs`
- Las variables de entorno nunca deben hardcodearse; se cargan con `python-dotenv`
- Fernet (de la librería `cryptography`) usa AES-128 en modo CBC para cifrado simétrico

### Problemas encontrados
- Ninguno en esta sesión

### Próximos pasos
- [ ] Crear el modelo de base de datos para usuarios y secretos
- [ ] Configurar SQLAlchemy con SQLite
- [ ] Implementar hashing de contrasenas con passlib
- [ ] Crear endpoint de registro e inicio de sesión

---
