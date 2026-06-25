"""
Tests de integración para POST /api/v1/worker/planos/{id}/analizar.
IDs del plan: PW-002, PW-003, PW-004, PW-005, PW-006, PW-007
"""
from unittest.mock import AsyncMock, patch

from tests.conftest import MINIMAL_PDF, VALID_AUTH
from src.schemas import TagEstado, TagInfo, TagSugerencia


def _multipart_pdf(content=MINIMAL_PDF, filename="plano.pdf", content_type="application/pdf"):
    """Helper: construye el dict de archivos para httpx."""
    return {"file": (filename, content, content_type)}


# ─────────────────────────────────────────────────────────────
# PW-007: Autenticación
# ─────────────────────────────────────────────────────────────

async def test_PW007_sin_header_authorization_retorna_422(client):
    """
    PW-007: Sin Authorization header el worker responde 422
    (FastAPI valida el parámetro requerido antes de llegar al handler).
    En producción el Gateway bloquea antes con 401.
    """
    resp = await client.post(
        "/api/v1/worker/planos/1/analizar",
        files=_multipart_pdf(),
    )
    assert resp.status_code == 422


async def test_sin_bearer_retorna_401(client):
    """Authorization sin prefijo 'Bearer ' → 401."""
    resp = await client.post(
        "/api/v1/worker/planos/1/analizar",
        files=_multipart_pdf(),
        headers={"Authorization": "token-sin-prefijo-bearer"},
    )
    assert resp.status_code == 401
    assert "Token requerido" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────
# PW-004: Archivo no PDF
# ─────────────────────────────────────────────────────────────

async def test_PW004_archivo_no_pdf_retorna_400(client):
    """PW-004: Enviar un PNG en lugar de PDF → 400 con mensaje descriptivo."""
    resp = await client.post(
        "/api/v1/worker/planos/1/analizar",
        files={"file": ("imagen.png", b"PNG" + b"x" * 200, "image/png")},
        headers=VALID_AUTH,
    )
    assert resp.status_code == 400
    assert "PDF" in resp.json()["detail"]


async def test_archivo_con_content_type_incorrecto_retorna_400(client):
    """Un .txt con content_type text/plain también es rechazado."""
    resp = await client.post(
        "/api/v1/worker/planos/1/analizar",
        files={"file": ("doc.txt", b"contenido " * 30, "text/plain")},
        headers=VALID_AUTH,
    )
    assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────
# PW-005: PDF demasiado grande
# ─────────────────────────────────────────────────────────────

async def test_PW005_pdf_mayor_50mb_retorna_413(client):
    """PW-005: PDF > 50 MB → 413 con mensaje que menciona el límite."""
    pdf_grande = b"%PDF-1.4\n" + b"x" * (51 * 1024 * 1024)
    resp = await client.post(
        "/api/v1/worker/planos/1/analizar",
        files=_multipart_pdf(content=pdf_grande),
        headers=VALID_AUTH,
    )
    assert resp.status_code == 413
    assert "50" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────
# PW-006: PDF vacío o corrupto
# ─────────────────────────────────────────────────────────────

async def test_PW006_pdf_menor_100_bytes_retorna_400(client):
    """PW-006: PDF < 100 bytes → 400 (vacío o corrupto)."""
    resp = await client.post(
        "/api/v1/worker/planos/1/analizar",
        files=_multipart_pdf(content=b"%PDF-1.4"),
        headers=VALID_AUTH,
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "vacío" in detail or "corrupto" in detail


# ─────────────────────────────────────────────────────────────
# PW-003: Plano sin TAGs
# ─────────────────────────────────────────────────────────────

async def test_PW003_sin_tags_retorna_200_con_advertencia(client):
    """PW-003: Plano sin TAGs → 200 + totalTags:0 + advertencias[]."""
    with patch(
        "src.routes.analyze.myplans_client.get_tags_by_plano",
        new_callable=AsyncMock,
    ) as mock_tags:
        mock_tags.return_value = []

        resp = await client.post(
            "/api/v1/worker/planos/1/analizar",
            files=_multipart_pdf(),
            headers=VALID_AUTH,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["totalTags"] == 0
    assert body["tagsAnalizados"] == 0
    assert len(body["sugerencias"]) == 0
    assert len(body["advertencias"]) > 0


# ─────────────────────────────────────────────────────────────
# PW-002: PDF válido con TAGs → sugerencias
# ─────────────────────────────────────────────────────────────

async def test_PW002_pdf_valido_con_tags_retorna_sugerencias(client):
    """PW-002: PDF válido + TAGs → 200 + array de sugerencias con confianza."""
    tags_mock = [
        TagInfo(idTag=1, codigo="TAG-001", estadoActual=TagEstado.PENDIENTE),
        TagInfo(idTag=2, codigo="TAG-002", estadoActual=TagEstado.PENDIENTE),
    ]
    sugerencias_mock = [
        TagSugerencia(
            idTag=1,
            codigo="TAG-001",
            estadoActual=TagEstado.PENDIENTE,
            estadoSugerido=TagEstado.APROBADO,
            confidence=0.95,
            pagina=1,
        )
    ]

    with (
        patch("src.routes.analyze.myplans_client.get_tags_by_plano", new_callable=AsyncMock) as mock_tags,
        patch("src.routes.analyze.analyzer.analyze_plano", new_callable=AsyncMock) as mock_analyze,
    ):
        mock_tags.return_value = tags_mock
        mock_analyze.return_value = (sugerencias_mock, 1, [])

        resp = await client.post(
            "/api/v1/worker/planos/1/analizar",
            files=_multipart_pdf(),
            headers=VALID_AUTH,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["totalTags"] == 2
    assert body["tagsAnalizados"] == 1
    assert body["paginasAnalizadas"] == 1
    assert len(body["sugerencias"]) == 1

    sug = body["sugerencias"][0]
    assert sug["codigo"] == "TAG-001"
    assert sug["estadoSugerido"] == "APROBADO"
    assert sug["confidence"] == 0.95


async def test_respuesta_incluye_advertencias_del_analyzer(client):
    """Las advertencias que devuelve el analyzer se propagan en la respuesta."""
    tags_mock = [TagInfo(idTag=1, codigo="TAG-001", estadoActual=TagEstado.PENDIENTE)]

    with (
        patch("src.routes.analyze.myplans_client.get_tags_by_plano", new_callable=AsyncMock) as mock_tags,
        patch("src.routes.analyze.analyzer.analyze_plano", new_callable=AsyncMock) as mock_analyze,
    ):
        mock_tags.return_value = tags_mock
        mock_analyze.return_value = ([], 1, ["Advertencia de prueba"])

        resp = await client.post(
            "/api/v1/worker/planos/1/analizar",
            files=_multipart_pdf(),
            headers=VALID_AUTH,
        )

    assert resp.status_code == 200
    assert "Advertencia de prueba" in resp.json()["advertencias"]


async def test_error_al_obtener_tags_retorna_502(client):
    """Si myplans_client.get_tags_by_plano lanza excepción → 502."""
    with patch(
        "src.routes.analyze.myplans_client.get_tags_by_plano",
        new_callable=AsyncMock,
        side_effect=Exception("Core no disponible"),
    ):
        resp = await client.post(
            "/api/v1/worker/planos/1/analizar",
            files=_multipart_pdf(),
            headers=VALID_AUTH,
        )

    assert resp.status_code == 502
