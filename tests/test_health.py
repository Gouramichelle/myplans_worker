"""PW-001 — Health check del Worker IA."""


async def test_PW001_health_retorna_ok(client):
    """PW-001: GET /api/v1/worker/health → HTTP 200 + {"status": "ok"}."""
    resp = await client.get("/api/v1/worker/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_no_requiere_token(client):
    """El endpoint de health no exige Authorization header."""
    resp = await client.get("/api/v1/worker/health")

    assert resp.status_code == 200
