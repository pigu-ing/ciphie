# Changelog

Todos los cambios notables de este proyecto se documentan aquí.

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
y este proyecto sigue [Semantic Versioning](https://semver.org/lang/es/).

---

## [Unreleased]

### Added
- **Auditoría de accesos**: tabla `audit_log` en SQLite; se registran las acciones crear, ver, copiar, editar, eliminar y restaurar con timestamp. Vista "📋 actividad" en el sidebar del dashboard con entradas color-coded.
- **Versionado de secretos**: tabla `secret_versions`; cada edición guarda el valor anterior automáticamente. Opción "historial" en el menú ⋮ de cada secreto con lista de versiones y botón "restaurar" por versión. Restaurar es reversible (guarda el valor actual antes de sobreescribir).
- **Expiración de secretos**: columna `expires_at` en la tabla `secrets`. Dropdown "expira en" en el formulario de nuevo secreto (nunca / 30 / 60 / 90 días / personalizada). Ícono ⚠️ para secretos que vencen en menos de 7 días, 🔴 para vencidos. Banner de alerta al inicio con botón "renovar" por cada secreto vencido.
- **Edición de secretos**: opción "editar" en el menú ⋮; permite cambiar nombre, categoría, valor y fecha de expiración. Llama a `editar_secreto()` que guarda versión anterior antes de sobreescribir.
- **Tests**: 29 tests nuevos cubriendo las 3 features (`test_audit.py`, `test_versioning.py`, `test_expiry.py`). Suite completa: 51 tests, todos en verde.

### Changed
- `agregar_secreto()` acepta parámetro opcional `expires_at`.
- `editar_secreto()` reemplaza al viejo flujo de eliminar+crear; guarda versión anterior en `secret_versions`.
- Menú contextual ⋮ expandido: ver, copiar, editar, historial, eliminar.
- Sidebar del dashboard: se añade entrada "📋 actividad" entre secretos y usuario.
- Estructura inicial del proyecto (backend, frontend, docs)
- Configuración base de FastAPI con endpoint de health check (`GET /`)
- Archivo `.env.example` con las variables de entorno necesarias
- `requirements.txt` con todas las dependencias del proyecto
- `README.md` con descripción, features e instrucciones de instalación
- Diario de desarrollo en `docs/journal.md`

---

<!-- Versiones futuras se añaden aquí siguiendo el mismo formato:

## [0.2.0] - YYYY-MM-DD

### Added
- Nuevas funcionalidades

### Changed
- Cambios en funcionalidades existentes

### Fixed
- Correcciones de bugs

### Removed
- Funcionalidades eliminadas

-->
