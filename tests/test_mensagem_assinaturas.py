import pytest

from app.whatsapp.mensagem_assinaturas import _extrair_meses


def test_extrair_meses_mes_unico():
    periodos = ["01/02/2025 à 28/02/2025"]
    assert _extrair_meses(periodos) == ["fevereiro"]


def test_extrair_meses_periodo_multiplos_meses():
    periodos = ["01/02/2025 à 31/03/2025"]
    assert _extrair_meses(periodos) == ["fevereiro", "março"]


def test_extrair_meses_periodo_dois_anos():
    periodos = ["01/12/2024 à 31/01/2025"]
    assert _extrair_meses(periodos) == ["dezembro", "janeiro"]
