# AEGIS Studio Editor — Subproyecto

Editor interactivo no-lineal para corrección quirúrgica de videos doblados post-procesamiento. Depende del pipeline principal del Traductor pero tiene su propia lógica, frontend y plan de desarrollo.

---

## Archivos del subproyecto

| Archivo | Propósito |
|---------|-----------|
| `README.md` | Este archivo. Descripción general del subproyecto. |
| `architecture.md` | Arquitectura actual del Studio: layout, endpoints, flujo de datos, diagramas. |
| `implementation_plan.md` | Plan de implementación: split por frase, cambios en endpoints y frontend. |
| `bugs.md` | Bugs conocidos, desyncs y problemas pendientes. |

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
