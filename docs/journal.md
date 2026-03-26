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
- [ ] Implementar hashing de contraseñas con passlib
- [ ] Crear endpoint de registro e inicio de sesión

---
