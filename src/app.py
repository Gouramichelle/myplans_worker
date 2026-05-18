"""MyPlans Worker — FastAPI app."""
import logging

from fastapi import FastAPI

from src.config import settings
from src.routes.analyze import router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="MyPlans Worker — Análisis de Planos con IA",
    description=(
        "Microservicio que recibe un plano amarillado (PDF con anotaciones de terreno) "
        "y usa Claude Vision para detectar automáticamente el estado de cada TAG "
        "(APROBADO / OBSERVADO). Los resultados se presentan al usuario para revisión "
        "antes de ser aplicados en MyPlans."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

app.include_router(router)
