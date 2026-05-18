from enum import Enum
from pydantic import BaseModel


class TagEstado(str, Enum):
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    OBSERVADO = "OBSERVADO"


class TagInfo(BaseModel):
    idTag: int
    codigo: str
    descripcion: str | None = None
    area: str | None = None
    estadoActual: TagEstado


class TagSugerencia(BaseModel):
    idTag: int
    codigo: str
    estadoActual: TagEstado
    estadoSugerido: TagEstado
    comentario: str | None = None
    confidence: float
    pagina: int | None = None


class AnalisisResponse(BaseModel):
    idPlano: int
    totalTags: int
    tagsAnalizados: int
    sugerencias: list[TagSugerencia]
    paginasAnalizadas: int
    advertencias: list[str]


class AplicarCambiosRequest(BaseModel):
    sugerencias: list[TagSugerencia]


class AplicarCambiosResponse(BaseModel):
    aplicados: int
    errores: int
    detalle: list[dict]
