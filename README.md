# MyPlans Worker

Microservicio de análisis de planos eléctricos con IA. Recibe un PDF con anotaciones de terreno ("plano amarillado"), usa **Claude Vision** para detectar el estado de cada TAG y devuelve sugerencias al usuario para revisión antes de aplicarlas.

## Cómo funciona

```
Frontend → POST /api/v1/worker/planos/{id}/analizar (PDF)
              ↓
         Convierte páginas PDF → imágenes JPEG
              ↓
         Envía imágenes + lista de TAGs a Claude Vision
              ↓
         Retorna sugerencias (APROBADO / OBSERVADO) por TAG
              ↓
Frontend → POST /api/v1/worker/planos/{id}/aplicar
              ↓
         Actualiza estado de cada TAG confirmado en MyPlans
```

El worker es **stateless** — no tiene base de datos. Todo el estado vive en el API Gateway de MyPlans.

## Stack

- Python 3.12
- FastAPI + Uvicorn
- [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python) (Claude Vision)
- PyMuPDF — conversión PDF → imágenes
- httpx — cliente HTTP hacia MyPlans

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/worker/planos/{id}/analizar` | Analiza el PDF y devuelve sugerencias |
| `POST` | `/api/v1/worker/planos/{id}/aplicar` | Aplica las sugerencias confirmadas |
| `GET` | `/health` | Healthcheck |
| `GET` | `/docs` | Documentación interactiva (Swagger UI) |

## Instalación local

```bash
# 1. Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env y completar ANTHROPIC_API_KEY

# 4. Levantar el servidor
uvicorn src.app:app --port 8099 --reload
```

La documentación interactiva queda disponible en http://localhost:8099/docs

## Variables de entorno

| Variable | Requerida | Descripción |
|---|---|---|
| `ANTHROPIC_API_KEY` | Sí | Clave de API de Anthropic |
| `MYPLANS_API_URL` | No | URL del API Gateway (default: `http://localhost:8095`) |
| `CLAUDE_MODEL` | No | Modelo a usar (default: `claude-sonnet-4-6`) |
| `PORT` | No | Puerto del servidor (default: `8099`) |
| `PDF_DPI` | No | Resolución de conversión PDF→imagen (default: `150`) |
| `MAX_PAGES` | No | Máximo de páginas a analizar por request (default: `20`) |
| `CORS_ORIGINS` | No | Orígenes permitidos (default: `http://localhost:5173`) |
| `LOG_LEVEL` | No | Nivel de logs: DEBUG / INFO / WARNING (default: `INFO`) |

## Docker

```bash
docker build -t myplans-worker .
docker run -p 8099:8099 --env-file .env myplans-worker
```

## Estructura

```
src/
├── app.py            # Aplicación FastAPI
├── config.py         # Variables de entorno (pydantic-settings)
├── analyzer.py       # Lógica de análisis con Claude Vision
├── myplans_client.py # Cliente HTTP hacia el API Gateway
├── schemas.py        # Modelos Pydantic (request/response)
└── routes/
    └── analyze.py    # Endpoints /analizar y /aplicar
```
