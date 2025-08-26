from collections import Counter
import re


def gerar_mensagens_assinaturas(df):
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
        if periodos:
            # Usa o período mais frequente; se empate, pega o primeiro
            periodo_counter = Counter(periodos)
            mes = periodo_counter.most_common(1)[0][0]
        else:
            mes = ""

        linhas = "\n".join(f"- {n}" for n in nomes)

        if re.fullmatch(r"[A-Z]?\d{1,3}[A-Z]?", equipe):
            titulo = f"LOJA {equipe}"
        else:
            titulo = f"ASSINATURA DE ESPELHO PONTO | {equipe}"

        mensagem = (
            f"{titulo}\n"
            f"Os colaboradores abaixo não assinaram o espelho ponto do mês {mes}\n"
            f"{linhas}"
        ).strip()
        mensagens[equipe] = mensagem

    return mensagens
