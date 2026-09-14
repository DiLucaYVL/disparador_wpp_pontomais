from app.processamento.csv_reader import carregar_dados
from app.processamento.ocorrencias_processor import filtrar_pendencia_gestor
from app.processamento.motivos_ocorrencias import ACAO_PENDENTE_GESTOR
from app.whatsapp.mensagem import gerar_mensagens
from app.whatsapp.mensagem_assinaturas import gerar_mensagens_assinaturas
from app.routes import enviar_whatsapp
from app.history import (
    registrar_envio,
    registrar_resultado_relatorio,
    normalizar_nome_relatorio,
    buscar_ocorrencias_enviadas,
)
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.whatsapp.numeros_equipes import carregar_numeros_equipes
from app.processamento.log import configurar_log
from app.processamento.mapear_gerencia import eh_loja
from app.services.google_sheets import registrar_dataframe_no_sheets
from collections import defaultdict
from datetime import datetime
import logging
import pandas as pd
from app.types import MensagemDetalhada

def processar_csv(
    caminho_csv,
    ignorar_sabados,
    tipo_relatorio,
    equipes_selecionadas=None,
    nome_relatorio=None,
    nome_relatorio_original=None,
    equipes_permitidas=None,
    apenas_gestor=False,
    incluir_duplicadas=False,
):
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

    logs = []
    equipes_sem_numero = []
    stats = {"total": 0, "equipes": set(), "sucesso": 0, "erro": 0}

    ignoradas_pendencia_colaborador = 0
    ignoradas_duplicadas = 0
    acao_pendente_valor = ACAO_PENDENTE_GESTOR if (tipo_relatorio == "Ocorrências" and apenas_gestor) else None

    if tipo_relatorio == "Ocorrências":
        if apenas_gestor:
            total_antes = len(df)
            df = filtrar_pendencia_gestor(df)
            ignoradas_pendencia_colaborador = total_antes - len(df)
            if ignoradas_pendencia_colaborador:
                logs.append({
                    "type": "info",
                    "message": (
                        f"{ignoradas_pendencia_colaborador} ocorrência(s) ignorada(s): "
                        "pendência é do colaborador, não do gestor."
                    ),
                })

        if not incluir_duplicadas and not df.empty:
            candidatos = list(df[["Nome", "Motivo", "Data"]].itertuples(index=False, name=None))
            ja_enviadas = buscar_ocorrencias_enviadas("Ocorrências", candidatos)
            if ja_enviadas:
                mask_duplicada = df.apply(
                    lambda row: (
                        str(row["Nome"]).strip(),
                        str(row["Motivo"]).strip(),
                        str(row["Data"]).strip(),
                    ) in ja_enviadas,
                    axis=1,
                )
                ignoradas_duplicadas = int(mask_duplicada.sum())
                df = df[~mask_duplicada]
                if ignoradas_duplicadas:
                    logs.append({
                        "type": "info",
                        "message": (
                            f"{ignoradas_duplicadas} ocorrência(s) ignorada(s): "
                            "já haviam sido enviadas anteriormente."
                        ),
                    })

    nome_relatorio_chave = normalizar_nome_relatorio(nome_relatorio or nome_relatorio_original)
    nome_relatorio_exibicao = (nome_relatorio_original or nome_relatorio or nome_relatorio_chave or "relatorio_sem_nome").strip()

    def normalizar_equipe_valor(valor: object) -> str:
        texto = str(valor).strip().upper()
        if texto in {"", "NAN", "NONE", "NULL"}:
            return ""
        return texto

    equipes_selecionadas_norm = None
    if equipes_selecionadas:
        equipes_selecionadas_norm = {
            valor
            for valor in (normalizar_equipe_valor(eq) for eq in equipes_selecionadas)
            if valor
        }

    equipes_permitidas_norm = None
    if equipes_permitidas:
        equipes_permitidas_norm = {
            valor
            for valor in (normalizar_equipe_valor(eq) for eq in equipes_permitidas)
            if valor
        }

    equipes_previstas_norm = set(equipes_permitidas_norm or [])
    equipes_processadas_norm = set()
    equipes_sucesso_norm = set()

    def equipe_autorizada(equipe_normalizada: str) -> bool:
        if equipes_permitidas_norm and equipe_normalizada not in equipes_permitidas_norm:
            return False
        if equipes_selecionadas_norm and equipe_normalizada not in equipes_selecionadas_norm:
            return False
        return True

    equipes_com_erro = set()
    if tipo_relatorio == "Assinaturas":
        mensagens_por_equipe = gerar_mensagens_assinaturas(df)
        if not equipes_previstas_norm:
            equipes_previstas_norm = {
                valor
                for valor in (normalizar_equipe_valor(equipe) for equipe in mensagens_por_equipe.keys())
                if valor
            }
        futures = {}
        historico_por_equipe = defaultdict(list)
        with ThreadPoolExecutor(max_workers=5) as executor:
            for equipe, dados in sorted(mensagens_por_equipe.items()):
                equipe_normalizada = str(equipe).strip().upper()
                if equipes_permitidas_norm and equipe_normalizada not in equipes_permitidas_norm:
                    logs.append({"type": "info", "message": f"Envio ignorado para {equipe_normalizada} (relat?rio j? conclu?do)."})
                    continue
                if equipes_selecionadas_norm and equipe_normalizada not in equipes_selecionadas_norm:
                    continue

                numero = numero_equipe.get(equipe_normalizada)
                if not numero or numero.strip().lower() in ["nan", "none", ""]:
                    equipes_sem_numero.append(equipe)
                    stats["erro"] += 1
                    equipes_com_erro.add(equipe_normalizada)
                    continue

                equipe_original = df[df["EquipeTratada"] == equipe_normalizada]["Equipe"].iloc[0]
                titulo = f"LOJA {equipe_normalizada}" if eh_loja(equipe_original) else f"{equipe_normalizada}"

                mensagem_final = dados["mensagem"].strip()
                future = executor.submit(
                    enviar_whatsapp, numero, mensagem_final, equipe_normalizada
                )
                futures[future] = (titulo, equipe_normalizada)
                stats["total"] += 1
                stats["equipes"].add(equipe_normalizada)

                motivo = str(dados.get("motivo", "")).strip() or "Assinatura pendente"
                nomes_registrados = []
                for nome in dados.get("nomes", []):
                    nome_limpo = str(nome).strip()
                    if not nome_limpo:
                        continue
                    nomes_registrados.append((nome_limpo, motivo))
                if nomes_registrados:
                    historico_por_equipe[equipe_normalizada].extend(nomes_registrados)

        for future in as_completed(futures):
            titulo, equipe_nome = futures[future]
            registros = historico_por_equipe.get(equipe_nome, [])
            try:
                future.result()
                logs.append({"type": "success", "message": f" Mensagem enviada para {titulo}"})
                stats["sucesso"] += 1
                equipe_sucesso = normalizar_equipe_valor(equipe_nome)
                if equipe_sucesso:
                    equipes_sucesso_norm.add(equipe_sucesso)
                if registros:
                    envios_lote = [
                        {
                            "equipe": equipe_nome,
                            "tipo_relatorio": tipo_relatorio,
                            "status": "sucesso",
                            "pessoa": pessoa,
                            "motivo_envio": motivo,
                            "nome_relatorio": nome_relatorio_chave,
                        }
                        for pessoa, motivo in registros
                    ]
                    registrar_envio(envios_lote)
            except Exception as e:
                logs.append({"type": "error", "message": f" Erro ao enviar para {titulo}: {str(e)}"})
                stats["erro"] += 1
                equipes_com_erro.add(str(equipe_nome).strip().upper())
                if registros:
                    envios_lote = [
                        {
                            "equipe": equipe_nome,
                            "tipo_relatorio": tipo_relatorio,
                            "status": "erro",
                            "pessoa": pessoa,
                            "motivo_envio": motivo,
                            "nome_relatorio": nome_relatorio_chave,
                        }
                        for pessoa, motivo in registros
                    ]
                    registrar_envio(envios_lote)

    else:
        mensagens_por_grupo = gerar_mensagens(df, tipo_relatorio)
        mensagens_por_equipe_data = defaultdict(lambda: defaultdict(list))
        historico_por_equipe = defaultdict(list)

        for (nome, data), detalhes in mensagens_por_grupo.items():
            if not isinstance(detalhes, MensagemDetalhada):
                continue

            equipe_match = df.loc[(df["Nome"] == nome) & (df["Data"] == data), "EquipeTratada"]
            if equipe_match.empty:
                continue
            equipe = equipe_match.iloc[0]
            mensagens_por_equipe_data[equipe][data].append(detalhes.texto)

            nome_formatado = str(nome).strip()
            motivos_unicos = []
            for motivo in detalhes.motivos:
                motivo_limpo = str(motivo).strip()
                if motivo_limpo and motivo_limpo not in motivos_unicos:
                    motivos_unicos.append(motivo_limpo)

            if nome_formatado:
                motivo_texto = "; ".join(motivos_unicos) or "Motivo não informado"
                historico_por_equipe[equipe].append((nome_formatado, motivo_texto, str(data)))

        if not equipes_previstas_norm:
            equipes_previstas_norm = {
                valor
                for valor in (normalizar_equipe_valor(equipe) for equipe in mensagens_por_equipe_data.keys())
                if valor
            }

        futures = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            for equipe, datas in sorted(mensagens_por_equipe_data.items()):
                equipe_normalizada = str(equipe).strip().upper()
                if equipes_permitidas_norm and equipe_normalizada not in equipes_permitidas_norm:
                    logs.append({"type": "info", "message": f"Envio ignorado para {equipe_normalizada} (relat?rio j? conclu?do)."})
                    continue
                if equipes_selecionadas_norm and equipe_normalizada not in equipes_selecionadas_norm:
                    continue

                numero = numero_equipe.get(equipe_normalizada)
                if not numero or numero.strip().lower() in ["nan", "none", ""]:
                    equipes_sem_numero.append(equipe)
                    stats["erro"] += 1
                    equipes_com_erro.add(equipe_normalizada)
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
                futures[future] = (titulo, equipe)
                stats["total"] += 1
                stats["equipes"].add(equipe_normalizada)
                equipes_processadas_norm.add(equipe_normalizada)

        for future in as_completed(futures):
            titulo, equipe_nome = futures[future]
            registros = historico_por_equipe.get(equipe_nome, [])
            try:
                future.result()
                logs.append({"type": "success", "message": f" Mensagem enviada para {titulo}"})
                stats["sucesso"] += 1
                equipe_sucesso = normalizar_equipe_valor(equipe_nome)
                if equipe_sucesso:
                    equipes_sucesso_norm.add(equipe_sucesso)
                if registros:
                    envios_lote = [
                        {
                            "equipe": equipe_nome,
                            "tipo_relatorio": tipo_relatorio,
                            "status": "sucesso",
                            "pessoa": pessoa,
                            "motivo_envio": motivo,
                            "nome_relatorio": nome_relatorio_chave,
                            "acao_pendente": acao_pendente_valor,
                            "data_ocorrencia": data_ocorrencia,
                        }
                        for pessoa, motivo, data_ocorrencia in registros
                    ]
                    registrar_envio(envios_lote)
            except Exception as e:
                logs.append({"type": "error", "message": f" Erro ao enviar para {titulo}: {str(e)}"})
                stats["erro"] += 1
                equipes_com_erro.add(str(equipe_nome).strip().upper())
                if registros:
                    envios_lote = [
                        {
                            "equipe": equipe_nome,
                            "tipo_relatorio": tipo_relatorio,
                            "status": "erro",
                            "pessoa": pessoa,
                            "motivo_envio": motivo,
                            "nome_relatorio": nome_relatorio_chave,
                            "acao_pendente": acao_pendente_valor,
                            "data_ocorrencia": data_ocorrencia,
                        }
                        for pessoa, motivo, data_ocorrencia in registros
                    ]
                    registrar_envio(envios_lote)

    # === Sheets: registrar apenas equipes realmente processadas (equipe_norm -> EquipeTratada) ===
    try:
        df_sheets = df
        if equipes_processadas_norm:
            df_sheets = df[df["EquipeTratada"].str.upper().isin(equipes_processadas_norm)].copy()
            if df_sheets.empty:
                logging.info(
                    "DF filtrado para Sheets ficou vazio (equipes_processadas=%s). Usando DF completo para evitar perda de registro.",
                    sorted(equipes_processadas_norm),
                )
                df_sheets = df.copy()
        logging.info(
            "Enviando DF para Sheets: linhas=%s colunas=%s",
            len(df_sheets),
            df_sheets.columns.tolist(),
        )
        registrar_dataframe_no_sheets(
            df_sheets,
            tipo_relatorio=tipo_relatorio,
            nome_relatorio=nome_relatorio_chave,
        )
    except Exception:
        logging.warning("Não foi possível registrar dados no Google Sheets.", exc_info=True)

    # === Pendências ===
    if equipes_selecionadas_norm:
        # Quando há seleção explícita, consideramos pendências apenas do que foi processado nesta execução.
        equipes_previstas_norm = {eq for eq in equipes_processadas_norm if eq}
    elif not equipes_previstas_norm and isinstance(stats["equipes"], set):
        equipes_previstas_norm = {
            valor
            for valor in (normalizar_equipe_valor(eq) for eq in stats["equipes"])
            if valor
        }

    equipes_previstas_norm = {eq for eq in equipes_previstas_norm if eq}

    pendencias_nao_processadas = sorted(
        equipe
        for equipe in equipes_previstas_norm
        if equipe not in equipes_sucesso_norm and equipe not in equipes_com_erro
    )
    if pendencias_nao_processadas:
        for equipe in pendencias_nao_processadas:
            logs.append({
                "type": "warning",
                "message": f" Envio pendente para {equipe}. Nenhuma mensagem foi enviada para esta execucao."
            })
        equipes_com_erro.update(pendencias_nao_processadas)
        stats["erro"] += len(pendencias_nao_processadas)

    if equipes_sem_numero:
        logs.append({"type": "warning", "message": f" Números não encontrados para: {', '.join(equipes_sem_numero)}"})

    total_equipes_previstas = len(equipes_previstas_norm)
    stats["total"] = max(stats["sucesso"] + stats["erro"], total_equipes_previstas)
    stats["equipes"] = total_equipes_previstas
    stats["pendencias"] = len(equipes_com_erro)
    stats["ignoradas_pendencia_colaborador"] = ignoradas_pendencia_colaborador
    stats["ignoradas_duplicadas"] = ignoradas_duplicadas

    if nome_relatorio_chave:
        registrar_resultado_relatorio(
            nome_relatorio_chave,
            nome_relatorio_exibicao,
            tipo_relatorio,
            stats["total"],
            stats["sucesso"],
            stats["erro"],
            equipes_com_erro,
        )

    logging.info(">>> Finalizando processamento CSV. Total de equipes: %d", stats["total"])
    return logs, stats, nome_arquivo_log
