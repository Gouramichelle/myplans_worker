"""
Tests de integración para POST /api/v1/worker/planos/{id}/aplicar.
IDs del plan: PW-008, PW-009
"""
from unittest.mock import AsyncMock, patch

from tests.conftest import VALID_AUTH
from src.schemas import TagEstado, TagSugerencia


def _body(sugerencias: list[TagSugerencia]) -> dict:
    return {"sugerencias": [s.model_dump() for s in sugerencias]}


def _sug(id_tag: int, codigo: str, estado_sugerido: TagEstado = TagEstado.APROBADO) -> TagSugerencia:
    return TagSugerencia(
        idTag=id_tag,
        codigo=codigo,
        estadoActual=TagEstado.PENDIENTE,
        estadoSugerido=estado_sugerido,
        confidence=0.9,
    )


# ─────────────────────────────────────────────────────────────
# PW-008: Aplicar sugerencias → actualiza TAGs en Core
# ─────────────────────────────────────────────────────────────

async def test_PW008_aplicar_sugerencias_retorna_aplicados(client):
    """PW-008: Aplicar sugerencias → HTTP 200 + aplicados=1, errores=0."""
    with patch(
        "src.routes.analyze.myplans_client.update_tag_estado",
        new_callable=AsyncMock,
        return_value={"message": "ok"},
    ) as mock_update:
        resp = await client.post(
            "/api/v1/worker/planos/1/aplicar",
            json=_body([_sug(10, "TAG-010")]),
            headers=VALID_AUTH,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["aplicados"] == 1
    assert body["errores"] == 0
    assert body["detalle"][0]["ok"] is True
    assert body["detalle"][0]["idTag"] == 10
    mock_update.assert_awaited_once()


async def test_PW008_update_llamado_con_por_ia_true(client):
    """update_tag_estado debe ser llamado con porIa=True para el historial de auditoría."""
    with patch(
        "src.routes.analyze.myplans_client.update_tag_estado",
        new_callable=AsyncMock,
        return_value={"message": "ok"},
    ) as mock_update:
        await client.post(
            "/api/v1/worker/planos/1/aplicar",
            json=_body([_sug(5, "TAG-005")]),
            headers=VALID_AUTH,
        )

    _, kwargs = mock_update.call_args
    assert kwargs.get("por_ia") is True


async def test_aplicar_multiples_sugerencias_todas_ok(client):
    """Tres sugerencias, todas exitosas → aplicados=3, errores=0."""
    sugs = [_sug(1, "TAG-001"), _sug(2, "TAG-002"), _sug(3, "TAG-003")]

    with patch(
        "src.routes.analyze.myplans_client.update_tag_estado",
        new_callable=AsyncMock,
        return_value={"message": "ok"},
    ):
        resp = await client.post(
            "/api/v1/worker/planos/1/aplicar",
            json=_body(sugs),
            headers=VALID_AUTH,
        )

    body = resp.json()
    assert body["aplicados"] == 3
    assert body["errores"] == 0


# ─────────────────────────────────────────────────────────────
# PW-009: TAG con error → reportado sin fallar todo
# ─────────────────────────────────────────────────────────────

async def test_PW009_tag_con_error_reportado_sin_abortar(client):
    """PW-009: Si un TAG falla → aplicados=0, errores=1, HTTP 200."""
    with patch(
        "src.routes.analyze.myplans_client.update_tag_estado",
        new_callable=AsyncMock,
        side_effect=Exception("Core no disponible"),
    ):
        resp = await client.post(
            "/api/v1/worker/planos/1/aplicar",
            json=_body([_sug(99, "TAG-099")]),
            headers=VALID_AUTH,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["aplicados"] == 0
    assert body["errores"] == 1
    assert body["detalle"][0]["ok"] is False
    assert "error" in body["detalle"][0]


async def test_dos_tags_uno_falla_parcial(client):
    """PW-009: Dos TAGs, el segundo falla → aplicados=1, errores=1, HTTP 200."""
    call_count = 0

    async def update_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise Exception("Error al actualizar TAG-002")
        return {"message": "ok"}

    with patch(
        "src.routes.analyze.myplans_client.update_tag_estado",
        new_callable=AsyncMock,
        side_effect=update_side_effect,
    ):
        resp = await client.post(
            "/api/v1/worker/planos/1/aplicar",
            json=_body([_sug(1, "TAG-001"), _sug(2, "TAG-002")]),
            headers=VALID_AUTH,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["aplicados"] == 1
    assert body["errores"] == 1


async def test_aplicar_lista_vacia_retorna_cero(client):
    """Lista vacía de sugerencias → aplicados=0, errores=0."""
    resp = await client.post(
        "/api/v1/worker/planos/1/aplicar",
        json={"sugerencias": []},
        headers=VALID_AUTH,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["aplicados"] == 0
    assert body["errores"] == 0
    assert body["detalle"] == []


async def test_aplicar_sin_token_retorna_422(client):
    """Sin Authorization header → 422 (parámetro requerido)."""
    resp = await client.post(
        "/api/v1/worker/planos/1/aplicar",
        json={"sugerencias": []},
    )
    assert resp.status_code == 422
