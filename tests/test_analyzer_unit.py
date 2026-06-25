"""
Pruebas unitarias de funciones puras en src/analyzer.py.
No requieren servidor, base de datos ni API keys.
"""
import json

import pytest

from src.analyzer import _build_tag_list, _extract_json_array, _parse_estado
from src.schemas import TagEstado, TagInfo


# ─────────────────────────────────────────────────────────────
# _parse_estado
# ─────────────────────────────────────────────────────────────

class TestParseEstado:
    def test_aprobado_exacto(self):
        assert _parse_estado("APROBADO") == TagEstado.APROBADO

    def test_aprobado_alias_ok(self):
        assert _parse_estado("OK") == TagEstado.APROBADO

    def test_aprobado_alias_approved(self):
        assert _parse_estado("APPROVED") == TagEstado.APROBADO

    def test_aprobado_alias_verificado(self):
        assert _parse_estado("VERIFICADO") == TagEstado.APROBADO

    def test_observado_exacto(self):
        assert _parse_estado("OBSERVADO") == TagEstado.OBSERVADO

    def test_observado_alias_redline(self):
        assert _parse_estado("REDLINE") == TagEstado.OBSERVADO

    def test_observado_alias_rechazado(self):
        assert _parse_estado("RECHAZADO") == TagEstado.OBSERVADO

    def test_observado_alias_flagged(self):
        assert _parse_estado("FLAGGED") == TagEstado.OBSERVADO

    def test_observado_alias_observed(self):
        assert _parse_estado("OBSERVED") == TagEstado.OBSERVADO

    def test_pendiente_para_valor_desconocido(self):
        assert _parse_estado("DESCONOCIDO") == TagEstado.PENDIENTE

    def test_pendiente_para_cadena_vacia(self):
        assert _parse_estado("") == TagEstado.PENDIENTE

    def test_case_insensitive_aprobado(self):
        assert _parse_estado("aprobado") == TagEstado.APROBADO

    def test_case_insensitive_observado(self):
        assert _parse_estado("observado") == TagEstado.OBSERVADO

    def test_case_insensitive_mixto(self):
        assert _parse_estado("Aprobado") == TagEstado.APROBADO


# ─────────────────────────────────────────────────────────────
# _extract_json_array
# ─────────────────────────────────────────────────────────────

class TestExtractJsonArray:
    def test_array_json_limpio(self):
        raw = '[{"codigo": "TAG-001", "estado": "APROBADO", "confidence": 0.9, "pagina": 1}]'
        result = _extract_json_array(raw)
        assert len(result) == 1
        assert result[0]["codigo"] == "TAG-001"

    def test_array_con_cerca_json(self):
        raw = '```json\n[{"codigo": "TAG-001", "estado": "APROBADO", "confidence": 0.9}]\n```'
        result = _extract_json_array(raw)
        assert len(result) == 1

    def test_array_con_cerca_sin_lenguaje(self):
        raw = '```\n[{"codigo": "TAG-002", "estado": "OBSERVADO", "confidence": 0.7}]\n```'
        result = _extract_json_array(raw)
        assert result[0]["codigo"] == "TAG-002"

    def test_array_con_texto_introductorio(self):
        raw = 'Aquí está el análisis:\n[{"codigo": "TAG-003", "estado": "PENDIENTE", "confidence": 0.5}]'
        result = _extract_json_array(raw)
        assert result[0]["codigo"] == "TAG-003"

    def test_array_vacio(self):
        result = _extract_json_array("[]")
        assert result == []

    def test_multiples_elementos(self):
        raw = json.dumps([
            {"codigo": "TAG-001", "estado": "APROBADO", "confidence": 0.95},
            {"codigo": "TAG-002", "estado": "OBSERVADO", "confidence": 0.75},
        ])
        result = _extract_json_array(raw)
        assert len(result) == 2

    def test_lanza_value_error_sin_array(self):
        with pytest.raises(ValueError, match="Sin array JSON"):
            _extract_json_array("texto plano sin ningún array")

    def test_lanza_exception_con_json_invalido(self):
        with pytest.raises(Exception):
            _extract_json_array("[{clave_sin_comillas: valor}]")

    def test_ignora_espacios_y_saltos_de_linea(self):
        raw = "\n\n   []\n\n"
        result = _extract_json_array(raw)
        assert result == []


# ─────────────────────────────────────────────────────────────
# _build_tag_list
# ─────────────────────────────────────────────────────────────

class TestBuildTagList:
    def test_incluye_el_codigo_del_tag(self):
        tags = [TagInfo(idTag=1, codigo="TAG-001", estadoActual=TagEstado.PENDIENTE)]
        assert "TAG-001" in _build_tag_list(tags)

    def test_incluye_la_descripcion_si_existe(self):
        tags = [TagInfo(idTag=1, codigo="TAG-001", descripcion="Motor principal", estadoActual=TagEstado.PENDIENTE)]
        assert "Motor principal" in _build_tag_list(tags)

    def test_incluye_el_area_si_existe(self):
        tags = [TagInfo(idTag=1, codigo="TAG-001", area="AREA-A", estadoActual=TagEstado.PENDIENTE)]
        assert "AREA-A" in _build_tag_list(tags)

    def test_lista_vacia_retorna_cadena_vacia(self):
        assert _build_tag_list([]) == ""

    def test_multiples_tags_en_lineas_separadas(self):
        tags = [
            TagInfo(idTag=1, codigo="TAG-001", estadoActual=TagEstado.PENDIENTE),
            TagInfo(idTag=2, codigo="TAG-002", estadoActual=TagEstado.APROBADO),
            TagInfo(idTag=3, codigo="TAG-003", estadoActual=TagEstado.OBSERVADO),
        ]
        result = _build_tag_list(tags)
        assert "TAG-001" in result
        assert "TAG-002" in result
        assert "TAG-003" in result
        assert result.count("\n") == 2  # 3 tags → 2 saltos de línea

    def test_sin_descripcion_ni_area_solo_codigo(self):
        tags = [TagInfo(idTag=1, codigo="TAG-X", estadoActual=TagEstado.PENDIENTE)]
        result = _build_tag_list(tags)
        assert "TAG-X" in result
        assert "—" not in result  # sin descripción no debe haber separador
        assert "[" not in result   # sin área no debe haber corchetes
