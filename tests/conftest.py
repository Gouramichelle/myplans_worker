"""Fixtures compartidos para los tests del worker."""
import pytest
from httpx import AsyncClient, ASGITransport

from src.app import app

# Cabecera válida para todos los endpoints que requieren Authorization
VALID_AUTH = {"Authorization": "Bearer test_jwt_valido"}

# PDF mínimo válido: > 100 bytes, < 50 MB
MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<</Type /Catalog>>\nendobj\n" + b"x" * 200


@pytest.fixture
async def client():
    """Cliente HTTP asíncrono apuntando a la app ASGI de FastAPI."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
