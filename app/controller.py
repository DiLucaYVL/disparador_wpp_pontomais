from app.processamento.csv_reader import carregar_dados
from app.whatsapp.mensagem import gerar_mensagens
from app.whatsapp.mensagem_assinaturas import gerar_mensagens_assinaturas
from app.routes import enviar_whatsapp
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.whatsapp.numeros_equipes import carregar_numeros_equipes
from app.processamento.log import configurar_log
from app.processamento.mapear_gerencia import eh_loja
from app.processamento.resumo_matricial import gerar_resumo_matricial
from collections import defaultdict
from datetime import datetime
import logging
import pandas as pd

def processar_csv(caminho_csv, ignorar_sabados, tipo_relatorio, equipes_selecionadas=None):
    nome_arquivo_log = configurar_log()
    logging.info(f">>> Iniciando processamento CSV: {caminho_csv}")
    logging.info(f">>> Parâmetros: ignorar_sabados={ignorar_sabados}, tipo={tipo_relatorio}")
    
    df = carregar_dados(caminho_csv, ignorar_sabados, tipo_relatorio)
    
    # Renomeia colunas comuns
    df.columns = df.columns.str.strip()
    df.rename(columns={
        "Funcionário": "Nome",
        "Funcionario": "Nome",
        "Colaborador": "Nome",
        "Data do ponto": "Data",
        "Data Registro": "Data"
    }, inplace=True)
    logging.info(f"🧪 Colunas carregadas: {df.columns.tolist()}")

    df["EquipeTratada"] = df["EquipeTratada"].astype(str).str.strip().str.upper()

    numero_equipe = carregar_numeros_equipes()
    resumo_matricial = gerar_resumo_matricial(df, tipo_relatorio)

    logs = []
    equipes_sem_numero = []
    stats = {"total": 0, "equipes": set(), "sucesso": 0, "erro": 0}

    if tipo_relatorio == "Assinaturas":
        mensagens_por_equipe = gerar_mensagens_assinaturas(df)
        futures = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            for equipe, mensagem_final in sorted(mensagens_por_equipe.items()):
                equipe_normalizada = str(equipe).strip().upper()
                if equipes_selecionadas:
                    equipes_normalizadas = {e.strip().upper() for e in equipes_selecionadas}
                    if equipe_normalizada not in equipes_normalizadas:
                        continue

                numero = numero_equipe.get(equipe_normalizada)
                if not numero or numero.strip().lower() in ["nan", "none", ""]:
                    equipes_sem_numero.append(equipe)
                    stats["erro"] += 1
                    continue

                equipe_original = df[df["EquipeTratada"] == equipe_normalizada]["Equipe"].iloc[0]
                titulo = f"LOJA {equipe_normalizada}" if eh_loja(equipe_original) else f"{equipe_normalizada}"

                future = executor.submit(
                    enviar_whatsapp, numero, mensagem_final.strip(), equipe_normalizada
                )
                futures[future] = titulo
                stats["total"] += 1
                stats["equipes"].add(equipe_normalizada)

        for future in as_completed(futures):
            titulo = futures[future]
            try:
                future.result()
                logs.append({"type": "success", "message": f" Mensagem enviada para {titulo}"})
                stats["sucesso"] += 1
            except Exception as e:
                logs.append({"type": "error", "message": f" Erro ao enviar para {titulo}: {str(e)}"})
                stats["erro"] += 1

    else:
        mensagens_por_grupo = gerar_mensagens(df, tipo_relatorio)
        mensagens_por_equipe_data = defaultdict(lambda: defaultdict(list))

        for (nome, data), mensagem in mensagens_por_grupo.items():
            equipe_match = df.loc[(df["Nome"] == nome) & (df["Data"] == data), "EquipeTratada"]
            if equipe_match.empty:
                continue
            equipe = equipe_match.iloc[0]
            mensagens_por_equipe_data[equipe][data].append(mensagem)

        futures = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            for equipe, datas in sorted(mensagens_por_equipe_data.items()):
                equipe_normalizada = str(equipe).strip().upper()
                if equipes_selecionadas:
                    equipes_normalizadas = {e.strip().upper() for e in equipes_selecionadas}
                    if equipe_normalizada not in equipes_normalizadas:
                        continue

                numero = numero_equipe.get(equipe_normalizada)
                if not numero or numero.strip().lower() in ["nan", "none", ""]:
                    equipes_sem_numero.append(equipe)
                    stats["erro"] += 1
                    continue

                mensagens_sub = datas
                datas_sub = defaultdict(list)

                for data, mensagens in mensagens_sub.items():
                    mensagens_validas = [m for m in mensagens if m and isinstance(m, str)]
                    if mensagens_validas:
                        datas_sub[data].extend(mensagens_validas)

                if not datas_sub:
                    continue

                equipe_original = df[df["EquipeTratada"] == equipe_normalizada]["Equipe"].iloc[0]
                titulo = f"LOJA {equipe}" if eh_loja(equipe_original) else f"{equipe}"
                mensagem_final = f"*{titulo}*\n\n"

                for data in sorted(datas_sub.keys(), key=lambda d: datetime.strptime(d, "%d/%m/%Y")):
                    mensagens_validas = [m.strip() for m in datas_sub[data] if m and m.strip()]
                    if not mensagens_validas:
                        continue
                    mensagem_final += f"*NO DIA {data}:*\n"
                    for m in mensagens_validas:
                        mensagem_final += f"• {m}\n"
                    mensagem_final += "\n"

                future = executor.submit(
                    enviar_whatsapp, numero, mensagem_final.strip(), equipe
                )
                futures[future] = titulo
                stats["total"] += 1
                stats["equipes"].add(equipe)

        for future in as_completed(futures):
            titulo = futures[future]
            try:
                future.result()
                logs.append({"type": "success", "message": f" Mensagem enviada para {titulo}"})
                stats["sucesso"] += 1
            except Exception as e:
                logs.append({"type": "error", "message": f" Erro ao enviar para {titulo}: {str(e)}"})
                stats["erro"] += 1

    if equipes_sem_numero:
        logs.append({"type": "warning", "message": f" Números não encontrados para: {', '.join(equipes_sem_numero)}"})

    stats["equipes"] = len(stats["equipes"])
    logging.info(">>> Finalizando processamento CSV. Total de equipes: %d", stats["total"])
    return logs, stats, nome_arquivo_log, resumo_matricial
