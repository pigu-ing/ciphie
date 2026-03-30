# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
python3 -m pytest

# Run a single test file
python3 -m pytest backend/tests/test_auth.py -v

# Run a single test
python3 -m pytest backend/tests/test_auth.py::TestRegistrarUsuario::test_crea_usuario_correctamente -v

# Launch the GUI
PYTHONPATH=backend python3 frontend/app.py

# CLI usage (if installed via pip install -e .)
ciphie start
ciphie secrets list
ciphie secrets get <nombre>
ciphie secrets add <nombre> --categoria contrasena

# Install in dev mode (enables `ciphie` CLI command)
pip install -e .
```

## Architecture

The project has a strict `backend/` / `frontend/` split. The frontend adds `backend/` to `sys.path` at startup, so all imports use `from app.xxx import yyy`.

```
backend/app/
  config.py    — loads .env, exposes get_smtp_config(), get_twilio_config(), get_master_key(), DB_PATH
  crypto.py    — cifrar(str) → str, descifrar(str) → str  (AES-256-GCM, HKDF key derivation)
  database.py  — all SQLite CRUD; inicializar_bd() creates tables on first run
  auth.py      — registration, login (2-step), 2FA (TOTP/email/SMS/biometric), user updates
  cli.py       — argparse entry point; `ciphie start` launches GUI subprocess

frontend/app.py — single-file Tkinter GUI (~1700 lines); all screens are tk.Frame subclasses
```

### Data flow: secrets storage

Secrets are always stored encrypted. The value in `secrets.encrypted_value` is `cifrar(json_string)` where the JSON has the shape:

```json
{"__type": "multi", "campos": {"usuario": "...", "contrasena": "...", "url": "..."}}
```

Use `_parsear_valor(descifrar(s.encrypted_value))` in `frontend/app.py` to decode. Returns `{"tipo": "multi", "campos": {...}}` or `{"tipo": "simple", "valor": "..."}` for legacy records. New secrets are always written as multi-campo JSON via `_serializar_campos(campos_dict)`.

Field templates per category are in `PLANTILLAS_CAMPOS` (frontend/app.py). Categories: `contrasena`, `tarjeta`, `api key`, `token`, `nota`, `env`, `otro`.

### Authentication flow

`autenticar_paso1(username, password)` returns `("ok", usuario)`, `("2fa_requerido", None)`, or `("fallo", None)`. If 2FA is required, the UI goes to `PantallaElegir2FA`, which calls `get_metodos_2fa_disponibles()` to show only available methods. OTPs are stored in-memory dicts (`_otp_2fa_pendientes`, etc.) with 5-minute TTL — they are not persisted to the DB.

### Registration flow

`iniciar_registro()` returns `(username, needs_verification: bool)`. If SMTP is not configured, the user is activated immediately (`is_active=1`) and `needs_verification=False`. If SMTP is configured, the user starts inactive and an OTP is sent by email.

### 2FA methods

Stored in `users.totp_method`: `"app"` (TOTP), `"email"`, `"biometrico"`. Touch ID is evaluated client-side via subprocess calling macOS `LocalAuthentication`. When disabling 2FA, the app always asks for the current 2FA verification first (`_verificar_2fa_antes_de()`).

### Database

SQLite at `PROJECT_ROOT/ciphie.db`. Schema migrations use `try/except ALTER TABLE` for backwards compatibility. FK constraints are enabled per-connection (`PRAGMA foreign_keys = ON`). When deleting a secret, `secret_versions` must be deleted first (FK constraint) — `eliminar_secreto()` handles this.

### Tests

Each test gets an isolated SQLite DB via the `bd_temporal` autouse fixture in `conftest.py` (uses `monkeypatch` to redirect `DB_PATH`). `MASTER_ENCRYPTION_KEY` is set to a random value at import time. Tests only use `registrar_usuario()` (direct activation, no SMTP), not `iniciar_registro()`.
