# Plan: Separar Frontend de JANUS e Integrarlo en Janus Landing

> **Estado:** PENDIENTE DE EJECUCIÓN  
> **Alcance:** Cross-project (TRADUCTOR + janus-landing)  
> **Auditor:** opencode (sesión 2026-07-07)  
> **Motivación:** Unificar la experiencia de usuario bajo un solo dominio (Vercel), eliminar la dependencia de la URL del túnel Cloudflare para acceder al editor, y desacoplar el frontend del backend FastAPI.

---

## 1. Arquitectura Actual

```
🌐 Usuario → https://janus-landing.vercel.app (Landing marketing)
                ↓ (abre nueva pestaña)
            https://*.trycloudflare.com (Frontend + Backend servidos por FastAPI)
                ↓ interno
            localhost:8000 (FastAPI sirve frontend/ + frontend_studio/ como static)
```

**Problemas:**
- La URL del túnel Cloudflare cambia cada vez que se reinicia `cloudflared` → el landing tiene una URL hardcodeada que hay que actualizar manualmente
- El frontend y backend están acoplados en el mismo proceso FastAPI
- No hay un dominio estable para la app

## 2. Arquitectura Propuesta

```
🌐 Usuario → https://janus-landing.vercel.app
                ├── /         → Landing page (marketing)
                ├── /app      → Editor de doblaje (frontend/)
                └── /studio   → Studio editor (frontend_studio/)
                        ↓ fetch() + video streams
                    https://*.trycloudflare.com (FastAPI: solo API)
                        ↓ interno
                    localhost:8000 (FastAPI: /api/* + /cache/*)
```

**Ventajas:**
- Dominio único y estable para el usuario (`janus-landing.vercel.app`)
- El túnel Cloudflare queda como detalle de infraestructura interna
- Landing y app comparten mismo origen → sin CORS en la navegación usuario
- El frontend puede tener CI/CD independiente del backend

## 3. Cambios Necesarios

### 3.1 Backend (`TRADUCTOR/backend/main.py`)

Agregar `CORSMiddleware` para permitir peticiones desde el dominio de Vercel:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://janus-landing.vercel.app",
        "http://localhost:8000",  # desarrollo local
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Esto asegura que las peticiones `fetch()` y los streams de video/audio desde el frontend en Vercel funcionen correctamente.

### 3.2 Frontend (ambos `app.js`) — Centralizar URL base

En cada `app.js`, agregar al inicio:

```javascript
const API_BASE = window.location.origin === 'http://localhost:8000'
    ? ''  // desarrollo local, rutas relativas
    : 'https://tu-tunel.trycloudflare.com';  // producción vía tunnel
```

Y reemplazar todas las URLs hardcodeadas:

| Patrón original | Reemplazo |
|----------------|-----------|
| `fetch('/api/...')` | `fetch(API_BASE + '/api/...')` |
| `fetch(\`/api/...\`` | `fetch(\`${API_BASE}/api/...\`` |
| `xhr.open('GET', '/api/...')` | `xhr.open('GET', API_BASE + '/api/...')` |
| `videoPlayer.src = '/api/stream/...'` | `videoPlayer.src = API_BASE + '/api/stream/...'` |
| `videoPlayer.src = \`/api/stream/...\`` | `videoPlayer.src = \`${API_BASE}/api/stream/...\`` |
| `src="/cache/..."` (generado en JS) | `src="${API_BASE}/cache/..."` |

**Archivos a modificar:**
- `TRADUCTOR/frontend/app.js` (~40 URLs)
- `TRADUCTOR/frontend_studio/app.js` (~20 URLs)
- `TRADUCTOR/frontend/index.html` (revisar si hay URLs absolutas)
- `TRADUCTOR/frontend_studio/index.html` (revisar)

### 3.3 Janus Landing — Agregar frontends

Copiar los directorios al repo del landing:

```
janus-landing/
├── index.html              ← Landing actual (sin cambios)
├── style.css               ← Estilos actuales (sin cambios)
├── app.js                  ← Landing app.js (cambiar JANUS_APP_URL)
├── assets/
│   └── video_demos/
├── frontend/               ← COPIADO de TRADUCTOR/frontend/
│   ├── index.html
│   ├── app.js              ← MODIFICADO con API_BASE
│   └── style.css
├── frontend_studio/        ← COPIADO de TRADUCTOR/frontend_studio/
│   ├── index.html
│   ├── app.js              ← MODIFICADO con API_BASE
│   └── style.css
└── vercel.json             ← NUEVO: rewrites para /app y /studio
```

### 3.4 `vercel.json` (en janus-landing)

```json
{
  "rewrites": [
    { "source": "/app/(.*)", "destination": "/frontend/$1" },
    { "source": "/studio/(.*)", "destination": "/frontend_studio/$1" }
  ]
}
```

### 3.5 Landing `app.js` — Actualizar enlace

Cambiar:
```javascript
var JANUS_APP_URL = 'https://looking-gold-legend-okay.trycloudflare.com';
```
a:
```javascript
var JANUS_APP_URL = '/app';  // Mismo dominio, ruta relativa
```

## 4. Archivos en Juego

### Traductor (backend + frontend original)
- `backend/main.py` — agregar CORS middleware
- `frontend/app.js` — centralizar API_BASE + reemplazar URLs
- `frontend/index.html` — revisar URLs absolutas
- `frontend_studio/app.js` — centralizar API_BASE + reemplazar URLs
- `frontend_studio/index.html` — revisar URLs absolutas

### Janus Landing (receptor)
- `vercel.json` — nuevo archivo con rewrites
- `app.js` — actualizar JANUS_APP_URL
- `frontend/` — nuevo directorio (copia de TRADUCTOR/frontend/)
- `frontend_studio/` — nuevo directorio (copia de TRADUCTOR/frontend_studio/)

## 5. Riesgos y Consideraciones

| Riesgo | Mitigación |
|--------|------------|
| **CORS en streaming de video**: `/api/stream/{task_id}` y `/cache/*` deben enviar `Access-Control-Allow-Origin` | El `CORSMiddleware` de FastAPI ya agrega estos headers a todas las respuestas |
| **Credenciales**: Sin auth, cualquiera con la URL del túnel accede al backend | El túnel puede requerir un header secreto (Cloudflare Tunnel permite `--header`); o mantener el túnel como internal y agregar auth después |
| **Cambio de URL del túnel**: Si cloudflared se reinicia, hay que actualizar `API_BASE` en los frontends | Usar un dominio Cloudflare fijo (tunnel permanente) en vez de quick tunnels (`*.trycloudflare.com`) |
| **Rendimiento**: Vercel sirve estáticos globalmente, el túnel agrega latencia | La latencia del túnel es la misma que hoy; el estático en Vercel es más rápido que desde tu PC |
| **Dos repos**: Mantener sincronizados los frontends entre TRADUCTOR y janus-landing | El plan asume copia manual; a futuro se podría hacer un script de deploy |

## 6. Orden de Ejecución Recomendado

1. **Backend**: Agregar `CORSMiddleware` en `main.py`
2. **Frontend Traductor**: Agregar `API_BASE` y reemplazar URLs en ambos `app.js`
3. **Probar local**: Abrir `frontend/index.html` directamente (sin FastAPI) apuntando a `localhost:8000`
4. **Copiar a landing**: Mover `frontend/` y `frontend_studio/` al repo janus-landing
5. **Configurar landing**: Crear `vercel.json` + actualizar `app.js` del landing
6. **Desplegar**: Push a `main` del landing → Vercel despliega automáticamente
7. **Probar producción**: Abrir `https://janus-landing.vercel.app/app` y verificar que funcione con el túnel
8. **Configurar túnel permanente** (opcional): Migrar de `*.trycloudflare.com` a un tunnel con dominio fijo

## 7. Notas

- El frontend de Vercel NO necesita build step — son archivos estáticos puros (HTML/CSS/JS)
- Vercel Framework Preset: **Other** (ya está configurado así en el landing)
- El túnel Cloudflare actual (`looking-gold-legend-okay.trycloudflare.com`) expira al reiniciar cloudflared; considera configurar un tunnel persistente con `cloudflared tunnel create`
- El editor actual ya usa polling (`/api/status/{task_id}`) en vez de WebSockets, lo que facilita el manejo cross-origin
