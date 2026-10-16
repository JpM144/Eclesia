# AGENTS.md

Reglas para cualquier agente que trabaje en este proyecto.

## Entorno

- Proyecto **Django 5.2 + PostgreSQL 17** en Windows/PowerShell.
- Intérprete: `.\.venv\Scripts\python.exe`
- Linter/formateador: `.\.venv\Scripts\ruff.exe`
- En PowerShell usa `;` en lugar de `&&` para encadenar comandos.

## Edición de archivos

- **Nunca** edites archivos con `Get-Content`/`Set-Content` ni con redirecciones de PowerShell
  (`>`, `>>`): dañan los caracteres UTF-8.
- Usa las herramientas de edición del agente o Python con `encoding='utf-8'`.

## Git

- **Nunca** uses `git stash`, `git checkout` ni `git reset` sobre archivos con cambios sin commit.
- **No hagas commits** salvo que el usuario lo pida explícitamente.

## Sesiones y credenciales

- No toques la contraseña del usuario `"admin"`.
- Si pruebas con un servidor real, crea un usuario temporal y bórralo al terminar.
- **Una sola sesión de agente a la vez** sobre el proyecto.

## Antes de cambiar sacramentos

Lee, en este orden:

1. `docs/especificacion_sacramentos.md`
2. `docs/libros_parroquiales.md`
3. `docs/requisitos_sacramentos.md` (cuando exista)

## Cierre de cada tarea

Ninguna tarea se considera terminada hasta ejecutar, con éxito:

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format .
.\.venv\Scripts\python.exe manage.py test
```

- Ningún error de usuario debe terminar en un **500**.
- **No entregues** esqueletos ni mensajes de éxito sin haber hecho el trabajo; si algo no se
  puede hacer, dilo.

## Seguridad

- Formularios con campos explícitos (nunca `__all__`).
- Sesión obligatoria en las vistas.
- Nada de `|safe`, `mark_safe` ni `innerHTML` con datos de personas.
- Nada de SQL construido con strings (usa el ORM o consultas parametrizadas).
