# JANUS Studio Editor — Subproyecto

Editor interactivo no-lineal para corrección quirúrgica de videos doblados post-procesamiento. Depende del pipeline principal del Traductor pero tiene su propia lógica, frontend y plan de desarrollo.

---

## Archivos del subproyecto

| Archivo | Propósito |
|---------|-----------|
| `README.md` | Este archivo. Descripción general del subproyecto. |
| `architecture.md` | Arquitectura actual del Studio: layout, endpoints, flujo de datos, diagramas. |
| `implementation_plan.md` | Plan de implementación: split por frase, cambios en endpoints y frontend. |
| `bugs.md` | Bugs conocidos, desyncs y problemas pendientes. |

## Características

- **Split por frase individual**: Cada bloque en la timeline = 1 frase. Edición y regeneración granular.
- **Multi-Language Support (V4.0)**: Soporte para cualquier par de idiomas origen/destino. La UI se adapta dinámicamente al idioma real detectado desde `task_meta.json`. Labels, botones y track names se muestran con los nombres correctos (ej: "Japonés / Español") en lugar de "Inglés / Español".
- **Backward compatible**: Si no existe `task_meta.json`, el editor usa English/Spanish como defaults.
- **Endpoint `/api/studio/{id}/meta`**: Devuelve `{source_language, target_language}` para que el frontend pueda adaptar la UI antes de cargar los datos completos.

### Dependencias externas (fuera de esta carpeta)

| Archivo | Propósito |
|---------|-----------|
| `frontend_studio/` | Frontend del editor (HTML, CSS, JS). |
| `backend/main.py` | Endpoints del Studio (`/api/studio/*`) y pipeline TTS. |

---

## Flujo de consulta recomendado para una IA

1. Leer `architecture.md` para entender cómo funciona hoy el Studio y dónde está el bug.
2. Leer `bugs.md` para ver los issues conocidos.
3. Leer `implementation_plan.md` para ver qué se planea cambiar y en qué orden.
4. Los cambios de código se hacen en `backend/main.py` y `frontend_studio/`.
