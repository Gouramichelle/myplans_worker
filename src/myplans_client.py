"""Cliente HTTP para la API de MyPlans (via gateway en :8095)."""
import logging

import httpx

from src.config import settings
from src.schemas import TagEstado, TagInfo

logger = logging.getLogger(__name__)
TIMEOUT = 15.0


async def get_tags_by_plano(id_plano: int, jwt_token: str) -> list[TagInfo]:
    url = f"{settings.MYPLANS_API_URL}/api/v1/planos/{id_plano}/tags"
    headers = {"Authorization": f"Bearer {jwt_token}"}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
    return [TagInfo(**item) for item in resp.json()]


async def update_tag_estado(
    id_tag: int,
    estado: TagEstado,
    comentario: str | None,
    jwt_token: str,
) -> dict:
    url = f"{settings.MYPLANS_API_URL}/api/v1/tags/{id_tag}/estado"
    headers = {"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"}
    payload: dict = {"estadoNuevo": estado.value}
    if comentario:
        payload["comentario"] = comentario
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.patch(url, json=payload, headers=headers)
        resp.raise_for_status()
    return resp.json()
