from app.processamento.csv_reader import carregar_dados
from app.whatsapp.mensagem import gerar_mensagens
from app.whatsapp.mensagem_assinaturas import gerar_mensagens_assinaturas
from app.routes import enviar_whatsapp
from app.history import (
    registrar_envio,
    registrar_resultado_relatorio,
    normalizar_nome_relatorio,
)
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.whatsapp.numeros_equipes import carregar_numeros_equipes
from app.processamento.log import configurar_log
from app.processamento.mapear_gerencia import eh_loja
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

    nome_relatorio_chave = normalizar_nome_relatorio(nome_relatorio or nome_relatorio_original)
    nome_relatorio_exibicao = (nome_relatorio_original or nome_relatorio or nome_relatorio_chave or "relatorio_sem_nome").strip()

    equipes_selecionadas_norm = None
    if equipes_selecionadas:
        equipes_selecionadas_norm = {str(eq).strip().upper() for eq in equipes_selecionadas if str(eq).strip()}

    equipes_permitidas_norm = None
    if equipes_permitidas:
        equipes_permitidas_norm = {str(eq).strip().upper() for eq in equipes_permitidas if str(eq).strip()}

    def equipe_autorizada(equipe_normalizada: str) -> bool:
        if equipes_permitidas_norm and equipe_normalizada not in equipes_permitidas_norm:
            return False
        if equipes_selecionadas_norm and equipe_normalizada not in equipes_selecionadas_norm:
            return False
        return True

    equipes_com_erro = set()
    if tipo_relatorio == "Assinaturas":
        mensagens_por_equipe = gerar_mensagens_assinaturas(df)
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
                historico_por_equipe[equipe].append((nome_formatado, motivo_texto))

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
                stats["equipes"].add(equipe)

        for future in as_completed(futures):
            titulo, equipe_nome = futures[future]
            registros = historico_por_equipe.get(equipe_nome, [])
            try:
                future.result()
                logs.append({"type": "success", "message": f" Mensagem enviada para {titulo}"})
                stats["sucesso"] += 1
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

    if equipes_sem_numero:
        logs.append({"type": "warning", "message": f" Números não encontrados para: {', '.join(equipes_sem_numero)}"})

    stats["equipes"] = len(stats["equipes"])
    stats["pendencias"] = len(equipes_com_erro)

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
