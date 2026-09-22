import pandas as pd
import pytest

from app.whatsapp.mensagem import formatar_horas_extras, gerar_mensagem


@pytest.mark.parametrize(
    "valor,esperado",
    [
        ("00:05", "5 minutos"),
        ("00:01", "1 minuto"),
        ("01:00", "1 hora"),
        ("02:00", "2 horas"),
        ("02:15", "2 horas e 15 minutos"),
        ("01:01", "1 hora e 1 minuto"),
        ("00:00", "0 minutos"),
    ],
)
def test_formatar_horas_extras(valor, esperado):
    assert formatar_horas_extras(valor) == esperado


def _grupo_horas_extras(valor):
    return pd.DataFrame([
        {
            "Nome": "Fulano",
            "Data": "10/11/2025",
            "Ocorrência": "Horas extras",
            "Valor": valor,
            "FaltaAbonadaJustificada": False,
        }
    ])


def test_gerar_mensagem_ignora_poucos_minutos_extras():
    resultado = gerar_mensagem(_grupo_horas_extras("00:05"))
    assert resultado is None


def test_gerar_mensagem_ignora_abaixo_do_corte_de_2h():
    resultado = gerar_mensagem(_grupo_horas_extras("01:59"))
    assert resultado is None


def test_gerar_mensagem_envia_a_partir_de_2h():
    resultado = gerar_mensagem(_grupo_horas_extras("02:00"))
    assert resultado is not None
    assert "2 horas extras" in resultado.texto
    assert "Fulano" in resultado.texto


def test_gerar_mensagem_envia_horas_e_minutos_acima_do_corte():
    resultado = gerar_mensagem(_grupo_horas_extras("02:15"))
    assert resultado is not None
    assert "2 horas e 15 minutos extras" in resultado.texto


def test_gerar_mensagem_ignora_zero_horas_extras():
    resultado = gerar_mensagem(_grupo_horas_extras("00:00"))
    assert resultado is None


def test_gerar_mensagem_ignora_valor_invalido():
    resultado = gerar_mensagem(_grupo_horas_extras("invalido"))
    assert resultado is None


def _grupo_intervalo(valor):
    return pd.DataFrame([
        {
            "Nome": "Fulano",
            "Data": "10/11/2025",
            "Ocorrência": "Mais de 2 horas de intervalo",
            "Valor": valor,
            "FaltaAbonadaJustificada": False,
        }
    ])


def test_gerar_mensagem_mais_de_2_horas_intervalo():
    resultado = gerar_mensagem(_grupo_intervalo("02:01"))
    assert resultado is not None
    assert "2 horas e 1 minuto" in resultado.texto
    assert "Fulano" in resultado.texto
    assert "Mais de 2 horas de intervalo" in resultado.motivos


def test_gerar_mensagem_mais_de_2_horas_intervalo_redondo():
    resultado = gerar_mensagem(_grupo_intervalo("02:00"))
    assert resultado is not None
    assert "2 horas" in resultado.texto
    assert "Fulano" in resultado.texto

