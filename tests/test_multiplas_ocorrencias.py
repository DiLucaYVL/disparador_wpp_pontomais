import pandas as pd
import pytest

from app.whatsapp.mensagem import (
    gerar_mensagem,
    gerar_mensagens,
    validar_ocorrencia,
    TEMPLATES,
)
from app.types import MensagemDetalhada
from app.processamento.ocorrencias_processor import gerar_linha_ocorrencia


def test_validar_ocorrencia_interjornada():
    """Garante que tanto 'Interjornada insuficiente' quanto 'Menos de 11:00 horas interjornada' são aceitas."""
    assert validar_ocorrencia("Interjornada insuficiente") is True
    assert validar_ocorrencia("Menos de 11:00 horas interjornada") is True
    assert validar_ocorrencia("menos de 11:00 horas interjornada") is True
    assert validar_ocorrencia("Interjornada") is True
    assert validar_ocorrencia("Falta") is True
    assert validar_ocorrencia("Invalido") is False


def test_gerar_mensagem_multiplas_ocorrencias_sem_perda():
    """Garante que Falta + Horas Faltantes não corta uma 3ª ocorrência (ex: Intrajornada ou Intervalo)."""
    grupo = pd.DataFrame([
        {
            "Nome": "Carlos Eduardo",
            "Data": "10/11/2025",
            "Ocorrência": "Falta",
            "Valor": "",
            "FaltaAbonadaJustificada": False,
        },
        {
            "Nome": "Carlos Eduardo",
            "Data": "10/11/2025",
            "Ocorrência": "Horas Faltantes",
            "Valor": "08:00",
            "FaltaAbonadaJustificada": False,
        },
        {
            "Nome": "Carlos Eduardo",
            "Data": "10/11/2025",
            "Ocorrência": "Intrajornada insuficiente",
            "Valor": "00:40",
            "FaltaAbonadaJustificada": False,
        },
        {
            "Nome": "Carlos Eduardo",
            "Data": "10/11/2025",
            "Ocorrência": "Mais de 2 horas de intervalo",
            "Valor": "02:30",
            "FaltaAbonadaJustificada": False,
        },
    ])

    detalhes = gerar_mensagem(grupo)
    assert isinstance(detalhes, MensagemDetalhada)
    # Deve conter a mensagem combinada de falta + horas faltantes
    assert "faltou" in detalhes.texto and "08:00 horas" in detalhes.texto
    # Deve conter a mensagem de intrajornada
    assert "pausa de almoço menor que 1h" in detalhes.texto
    # Deve conter a mensagem de mais de 2h de intervalo
    assert "mais de 2 horas de intervalo" in detalhes.texto

    # Todos os motivos devem estar na lista
    assert "Falta" in detalhes.motivos
    assert "Horas Faltantes" in detalhes.motivos
    assert "Intrajornada insuficiente" in detalhes.motivos
    assert "Mais de 2 horas de intervalo" in detalhes.motivos


def test_gerar_mensagem_multiplas_ocorrencias_intervalo_abaixo_de_2h10_ignorado():
    """Garante que intervalo menor que 2h10 (ex: 02:05) é ignorado sem afetar outras ocorrências."""
    grupo = pd.DataFrame([
        {
            "Nome": "Carlos Eduardo",
            "Data": "10/11/2025",
            "Ocorrência": "Falta",
            "Valor": "",
            "FaltaAbonadaJustificada": False,
        },
        {
            "Nome": "Carlos Eduardo",
            "Data": "10/11/2025",
            "Ocorrência": "Mais de 2 horas de intervalo",
            "Valor": "02:05",
            "FaltaAbonadaJustificada": False,
        },
    ])

    detalhes = gerar_mensagem(grupo)
    assert isinstance(detalhes, MensagemDetalhada)
    assert "faltou" in detalhes.texto
    assert "mais de 2 horas de intervalo" not in detalhes.texto
    assert "Falta" in detalhes.motivos
    assert "Mais de 2 horas de intervalo" not in detalhes.motivos


def test_gerar_mensagem_interjornada_pontomais():
    """Verifica mensagem gerada para 'Menos de 11:00 horas interjornada' vindo do Pontomais."""
    grupo = pd.DataFrame([
        {
            "Nome": "Ana Paula",
            "Data": "15/11/2025",
            "Ocorrência": "Menos de 11:00 horas interjornada",
            "Valor": "09:30",
            "FaltaAbonadaJustificada": False,
        }
    ])

    detalhes = gerar_mensagem(grupo)
    assert isinstance(detalhes, MensagemDetalhada)
    assert "interjornada" in detalhes.texto
    assert "09:30" in detalhes.texto
    assert "Interjornada insuficiente" in detalhes.motivos


def test_gerar_mensagem_mista_auditoria_e_ocorrencia():
    """Verifica grupo contendo ao mesmo tempo irregularidade de auditoria e ocorrência de ponto."""
    grupo = pd.DataFrame([
        {
            "Nome": "Lucas Silva",
            "Data": "20/11/2025",
            "Ocorrência": "Horas extras",
            "Valor": "02:30",
            "Motivo": "",
            "Ação pendente": "",
            "FaltaAbonadaJustificada": False,
        },
        {
            "Nome": "Lucas Silva",
            "Data": "20/11/2025",
            "Ocorrência": "",
            "Valor": "",
            "Motivo": "Número errado de pontos",
            "Ação pendente": "Gestor aprovar solicitação de ajuste",
            "FaltaAbonadaJustificada": False,
        },
    ])

    detalhes = gerar_mensagem(grupo)
    assert isinstance(detalhes, MensagemDetalhada)
    # Auditoria
    assert "2 horas e 30 minutos extras" in detalhes.texto
    # Ocorrência
    assert "apresentou _número errado de pontos_" in detalhes.texto
    assert "Gestor aprovar solicitação de ajuste" in detalhes.texto

    # Ambos os motivos presentes
    assert "Horas extras" in detalhes.motivos
    assert "Número errado de pontos" in detalhes.motivos


def test_gerar_mensagens_serie_completa():
    """Testa geração de Series por gerar_mensagens com múltiplos colaboradores e tipos."""
    df = pd.DataFrame([
        {
            "Nome": "Lucas Silva",
            "Data": "20/11/2025",
            "Ocorrência": "Horas extras",
            "Valor": "02:30",
            "Motivo": "",
            "Ação pendente": "",
            "FaltaAbonadaJustificada": False,
        },
        {
            "Nome": "Maria Santos",
            "Data": "20/11/2025",
            "Ocorrência": "Menos de 11:00 horas interjornada",
            "Valor": "08:00",
            "Motivo": "",
            "Ação pendente": "",
            "FaltaAbonadaJustificada": False,
        },
    ])

    series = gerar_mensagens(df, tipo_relatorio="Auditoria")
    assert len(series) == 2
    assert ("Lucas Silva", "20/11/2025") in series.index
    assert ("Maria Santos", "20/11/2025") in series.index


def test_carregar_dados_auditoria_com_interjornada(tmp_path):
    """Testa carregar_dados normalizando 'Menos de 11:00 horas interjornada'."""
    from app.processamento.csv_reader import carregar_dados

    csv_content = """Relatório de Auditoria
Por Usuário Master DP em 21/11/2025
De 01/11/2025 até 10/11/2025

Nome,Equipe,Data,Ocorrência,Valor
Adriana Silva,Loja 97,"Seg, 03/11/2025",Menos de 11:00 horas interjornada,09:30
Adriana Silva,Loja 97,"Ter, 04/11/2025",Falta,
Resumo,Totais
Total,2
"""
    csv_file = tmp_path / "auditoria_teste.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    df = carregar_dados(str(csv_file), ignorar_sabados=False, tipo_relatorio="Auditoria")
    assert len(df) == 2
    # Normalizou para 'Interjornada insuficiente'
    assert "Interjornada insuficiente" in df["Ocorrência"].values
    assert "Falta" in df["Ocorrência"].values


def test_carregar_dados_ocorrencias_dinamico(tmp_path):
    """Testa carregar_dados_ocorrencias com cabeçalho e rodapé dinâmicos."""
    from app.processamento.csv_reader_ocorrencias import carregar_dados_ocorrencias

    csv_content = """Relatório de Ocorrências
Por Usuário Master DP em 21/11/2025
De 01/11/2025 até 21/11/2025

Nome,Equipe,Data,Motivo,Ação pendente
Adriana Silva,Loja 97,"Qua, 19/11/2025",Número errado de pontos,Gestor aprovar solicitação de ajuste
Resumo,Totais
Total,1
"""
    csv_file = tmp_path / "ocorrencias_teste.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    df = carregar_dados_ocorrencias(str(csv_file))
    assert len(df) == 1
    assert df.iloc[0]["Nome"] == "Adriana Silva"
    assert df.iloc[0]["Motivo"] == "Número errado de pontos"


def test_carregar_dados_auditoria_com_intervalo_variacao(tmp_path):
    """Testa carregar_dados normalizando variações como '+2 de intervalo'."""
    from app.processamento.csv_reader import carregar_dados

    csv_content = """Relatório de Auditoria
Por Usuário Master DP em 21/11/2025
De 01/11/2025 até 10/11/2025

Nome,Equipe,Data,Ocorrência,Valor
Adriana Silva,Loja 97,"Seg, 03/11/2025",+2 de intervalo,02:15
Adriana Silva,Loja 97,"Ter, 04/11/2025",Mais de 2 horas de intervalo,02:20
Resumo,Totais
Total,2
"""
    csv_file = tmp_path / "auditoria_intervalo.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    df = carregar_dados(str(csv_file), ignorar_sabados=False, tipo_relatorio="Auditoria")
    assert len(df) == 2
    assert (df["Ocorrência"] == "Mais de 2 horas de intervalo").all()


