from unittest.mock import patch

import pytest

from app.services import estados_lojas
from app.services.estados_lojas import (
    ESTADO_SETORES,
    carregar_estados_lojas,
    montar_mapa_estados,
    normalizar_chave_privada,
    normalizar_loja,
    obter_estado_equipe,
)

LINHAS = [
    ["Código", "Loja", "Cidade", "UF"],
    ["1", "Loja 75 - Centro", "Palmas", "TO"],
    ["2", "LOJA NOVA A1", "Goiânia", "go"],
    ["3", "B4", "Belém", "PA"],
    ["4", "Departamento Pessoal", "Palmas", "TO"],
    ["5", "Loja 80", "Imperatriz", ""],
]


def test_normalizar_loja_usa_mapear_equipe():
    assert normalizar_loja("Loja 75 - Centro") == "75"
    assert normalizar_loja("Filial Nova B2") == "B2"
    assert normalizar_loja("a1") == "A1"
    assert normalizar_loja("") == ""


def test_montar_mapa_estados_relaciona_coluna_b():
    mapa = montar_mapa_estados(LINHAS)
    assert mapa == {"75": "TO", "A1": "GO", "B4": "PA"}


def test_montar_mapa_estados_aceita_cabecalho_estado():
    linhas = [["Id", "Loja", "Estado"], ["1", "Loja 10", "MA"]]
    assert montar_mapa_estados(linhas) == {"10": "MA"}


def test_montar_mapa_estados_sem_coluna_estado():
    with pytest.raises(ValueError):
        montar_mapa_estados([["Id", "Loja"], ["1", "Loja 10"]])


def test_setores_sao_tocantins():
    mapa = {"75": "PA"}
    for setor in ["DP", "CD10", "Comercial", "Financeiro 01", "Outro"]:
        assert obter_estado_equipe(setor, mapa) == ESTADO_SETORES == "TO"


def test_loja_usa_estado_da_planilha():
    mapa = {"75": "PA", "A1": "GO"}
    assert obter_estado_equipe("75", mapa) == "PA"
    assert obter_estado_equipe("a1", mapa) == "GO"
    assert obter_estado_equipe("99", mapa) is None


def test_carregar_estados_lojas_usa_cache():
    with patch.object(estados_lojas, "_ler_linhas_planilha", return_value=LINHAS) as ler:
        assert carregar_estados_lojas()["75"] == "TO"
        carregar_estados_lojas()
        assert ler.call_count == 1
        carregar_estados_lojas(forcar_atualizacao=True)
        assert ler.call_count == 2


def test_normalizar_chave_privada_reconstroi_pem():
    corpo = "A" * 70
    esperado = f"-----BEGIN PRIVATE KEY-----\n{'A' * 64}\n{'A' * 6}\n-----END PRIVATE KEY-----\n"
    assert normalizar_chave_privada(
        f'"-----BEGIN PRIVATE KEY-----\\n{corpo[:30]}\\n{corpo[30:]}\\n-----END PRIVATE KEY-----\\n"'
    ) == esperado
    assert normalizar_chave_privada(
        f" -----BEGIN PRIVATE KEY----- {corpo[:30]} {corpo[30:]} -----END PRIVATE KEY-----"
    ) == esperado
