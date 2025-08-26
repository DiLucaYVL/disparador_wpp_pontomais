import re
from datetime import datetime
from typing import Dict, List

import pandas as pd


MESES_PT: Dict[str, str] = {
    "01": "janeiro",
    "02": "fevereiro",
    "03": "março",
    "04": "abril",
    "05": "maio",
    "06": "junho",
    "07": "julho",
    "08": "agosto",
    "09": "setembro",
    "10": "outubro",
    "11": "novembro",
    "12": "dezembro",
}
NOMES_MESES = list(MESES_PT.values())


def _extrair_meses(periodos: List[str]) -> List[str]:
    """Extrai nomes de meses de uma lista de períodos.

    O período pode estar no formato ``dd/mm/aaaa à dd/mm/aaaa``. Todos os
    meses abrangidos entre as datas inicial e final serão considerados.
    Também são suportados períodos que mencionem diretamente o nome do mês ou
    no formato ``mm/aaaa``.
    """

    meses: List[str] = []
    for periodo in periodos:
        periodo_lower = periodo.lower()
        encontrados = [m for m in NOMES_MESES if m in periodo_lower]
        if encontrados:
            for nome in encontrados:
                if nome not in meses:
                    meses.append(nome)
            continue

        datas_str = re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b", periodo_lower)
        if datas_str:
            datas = [datetime.strptime(d, "%d/%m/%Y") for d in datas_str]
            datas.sort()
            inicio, fim = datas[0], datas[-1]
            corrente = inicio
            while corrente <= fim:
                nome = MESES_PT[f"{corrente.month:02d}"]
                if nome not in meses:
                    meses.append(nome)
                if corrente.month == 12:
                    corrente = corrente.replace(year=corrente.year + 1, month=1)
                else:
                    corrente = corrente.replace(month=corrente.month + 1)
            continue

        matches = re.findall(r"\b(\d{1,2})/\d{4}\b", periodo_lower)
        for m in matches:
            nome = MESES_PT.get(m.zfill(2))
            if nome and nome not in meses:
                meses.append(nome)

    return meses


def gerar_mensagens_assinaturas(df: pd.DataFrame) -> Dict[str, str]:
    """Gera um dicionário de mensagens por equipe para o relatório de Assinaturas.

    Retorna um dicionário {equipe_tratada: mensagem_final} para cada equipe que
    possui pelo menos um colaborador com pendência de assinatura.

    Caso a coluna ``Assinado?`` esteja presente, apenas colaboradores com valor
    "Não" permanecerão na lista e, consequentemente, na prévia de envio.
    """
    mensagens = {}
    if df.empty:
        return mensagens

    if "Assinado?" in df.columns:
        df = df[df["Assinado?"].astype(str).str.strip().str.lower() == "não"]
        if df.empty:
            return mensagens

    for equipe, grupo in df.groupby("EquipeTratada"):
        nomes = grupo["Nome"].dropna().tolist()
        if not nomes:
            continue

        periodos = grupo["Período (Fechamento)"].dropna().tolist()
        meses_encontrados = _extrair_meses(periodos)
        if not meses_encontrados:
            frase_mes = "do mês"
        elif len(meses_encontrados) == 1:
            frase_mes = f"do mês {meses_encontrados[0]}"
        else:
            meses_texto = ", ".join(meses_encontrados[:-1]) + f" e {meses_encontrados[-1]}"
            frase_mes = f"dos meses de {meses_texto}"

        linhas = "\n".join(f"- {n}" for n in nomes)

        if re.fullmatch(r"[A-Z]?\d{1,3}[A-Z]?", equipe):
            titulo = f"LOJA {equipe}"
        else:
            titulo = f"ASSINATURA DE ESPELHO PONTO | {equipe}"

        mensagem = (
            f"{titulo}\n"
            f"Por favor assinar o espelho ponto {frase_mes}\n"
            f"{linhas}"
        ).strip()
        mensagens[equipe] = mensagem

    return mensagens
