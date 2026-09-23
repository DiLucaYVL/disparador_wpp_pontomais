import unicodedata
from typing import List, Optional

import pandas as pd

from app.processamento.ocorrencias_processor import processar_ocorrencias, gerar_linha_ocorrencia
from app.processamento.motivos_ocorrencias import validar_motivo
from app.types import MensagemDetalhada

# === Templates para relatório de Auditoria ===
TEMPLATES = {
    #REMOVER: "Menos de 1 hora de intervalo": "*{nome}* teve menos de 1 hora de intervalo. _Intervalo registrado_: *{valor}*. Qual o motivo de não ter feito a pausa completa?",
    #REMOVER: "Mais de 10 horas de jornada": "*{nome}* trabalhou mais de 10 horas. _Total acumulado_: *{valor}*. Isso está previsto na escala?",
    "Mais de 6 dias de trabalho consecutivos": "*{nome}* está com mais de 6 dias consecutivos de trabalho. O colaborador deve *pegar folga* na semana seguinte.",
    "Mais de duas horas extras": "*{nome}* fez mais de duas horas extras. _Total_: *{horas_extras}*. Por favor *ajustar*.",
    "Falta": "*{nome}* _faltou_. Por favor *justificar*.",
    "Horas Faltantes": "*{nome}* ficou devendo *{horas}*. Por favor *justificar*.",
    "Interjornada insuficiente": "*{nome}* teve interjornada (período mínimo de descanso entre um expediente e outro) menor que 11h. _Tempo registrado_: *{horas}*.",
    "Menos de 11:00 horas interjornada": "*{nome}* teve interjornada (período mínimo de descanso entre um expediente e outro) menor que 11h. _Tempo registrado_: *{horas}*.",
    "Intrajornada insuficiente": "*{nome}* teve pausa de almoço menor que 1h. _Tempo registrado_: *{horas}*.",
    "Horas extras": "*{nome}* fez *{horas_extras} extras*. Por favor *ajustar*.",
    "Mais de 2 horas de intervalo": "*{nome}* teve mais de 2 horas de intervalo. _Intervalo registrado_: *{intervalo}*. Por favor *verificar*."
}

# === Funções auxiliares ===

def validar_ocorrencia(ocorrencia):
    if not isinstance(ocorrencia, str):
        return False
    ocorr_limpa = ocorrencia.strip()
    return ocorr_limpa in TEMPLATES or "interjornada" in ocorr_limpa.lower()

def converter_horas_para_minutos(valor_horas):
    try:
        if not isinstance(valor_horas, str) or ":" not in valor_horas:
            return 0
        horas, minutos = valor_horas.strip().split(":")
        return int(horas) * 60 + int(minutos)
    except:
        return 0

def formatar_horas(valor):
    if not isinstance(valor, str) or ":" not in valor:
        return valor
    horas, minutos = valor.strip().split(":")
    h, m = int(horas), int(minutos)
    if h == 0 and m == 0:
        return "00:00"
    if h == 0:
        return f"{horas}:{minutos} minutos"
    if m == 0:
        return f"{horas}:{minutos} horas"
    return f"{horas}:{minutos} horas"

def formatar_horas_extras(valor):
    """Formata minutos extras em texto dinâmico, com singular/plural correto.

    Exemplos: "00:37" -> "37 minutos"; "02:00" -> "2 horas";
    "02:15" -> "2 horas e 15 minutos"; "01:00" -> "1 hora".
    """
    if not isinstance(valor, str) or ":" not in valor:
        return valor
    try:
        horas_str, minutos_str = valor.strip().split(":")
        h, m = int(horas_str), int(minutos_str)
    except ValueError:
        return valor

    partes = []
    if h > 0:
        partes.append(f"{h} hora" + ("s" if h != 1 else ""))
    if m > 0:
        partes.append(f"{m} minuto" + ("s" if m != 1 else ""))

    return " e ".join(partes) if partes else "0 minutos"

def normalizar(texto):
    if not isinstance(texto, str):
        return ""
    return unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode().strip().lower()

# === Geração de mensagem individual por grupo (Nome + Data) ===


def gerar_mensagem(grupo) -> Optional[MensagemDetalhada]:
    nome = grupo["Nome"].iloc[0]
    data = grupo["Data"].iloc[0]

    falta_justificada_ou_abonada = False
    if "FaltaAbonadaJustificada" in grupo.columns:
        falta_justificada_ou_abonada = bool(grupo["FaltaAbonadaJustificada"].any())

    ocorrencias_dict = {}
    if "Ocorrência" in grupo.columns and "Valor" in grupo.columns:
        for _, r in grupo.iterrows():
            k = str(r["Ocorrência"]).strip()
            v = str(r["Valor"]).strip()
            if k and k not in {"nan", "None", ""}:
                ocorrencias_dict[k] = v

    ocorrencias_norm = {normalizar(k): normalizar(v) for k, v in ocorrencias_dict.items()}

    tem_ambas_horas_extras = (
        "horas extras" in ocorrencias_norm
        and "mais de duas horas extras" in ocorrencias_norm
        and ocorrencias_dict.get("Horas extras") == ocorrencias_dict.get("Mais de duas horas extras")
    )

    tem_falta = "falta" in ocorrencias_norm and not falta_justificada_ou_abonada
    tem_horas_faltantes = "horas faltantes" in ocorrencias_norm and not falta_justificada_ou_abonada

    msgs: List[str] = []
    mensagens_set = set()
    motivos_utilizados: List[str] = []

    # 1. Combinação especial: falta + horas faltantes não justificadas
    if tem_falta and tem_horas_faltantes:
        valor_faltante = ocorrencias_dict.get("Horas Faltantes") or ocorrencias_dict.get("horas faltantes") or ""
        msg_combinada = f"*{nome}* _faltou_ e _ficou devendo_ *{formatar_horas(valor_faltante)}*. Por favor *ajustar*."
        msgs.append(msg_combinada)
        mensagens_set.add(msg_combinada)
        for m in ["Falta", "Horas Faltantes"]:
            if m not in motivos_utilizados:
                motivos_utilizados.append(m)

    # 2. Itera sobre todas as linhas do grupo para processar Auditoria e/ou Ocorrências
    for _, row in grupo.iterrows():
        ocorr = row.get("Ocorrência")
        valor = row.get("Valor")
        motivo = row.get("Motivo")

        # Processamento Auditoria
        if isinstance(ocorr, str) and ocorr.strip() and ocorr.strip() not in {"nan", "None"}:
            ocorr_limpo = ocorr.strip()
            if "interjornada" in ocorr_limpo.lower():
                ocorr_limpo = "Interjornada insuficiente"
            ocorr_norm = normalizar(ocorr_limpo)
            valor_str = str(valor).strip() if valor is not None and str(valor).strip() not in {"nan", "None"} else ""

            # Se já combinou falta + horas faltantes, ignora individualmente
            if tem_falta and tem_horas_faltantes and ocorr_norm in {"falta", "horas faltantes"}:
                pass
            elif ocorr_norm == "horas faltantes" and falta_justificada_ou_abonada:
                pass
            elif ocorr_norm == "falta" and row.get("FaltaAbonadaJustificada", False):
                pass
            elif tem_ambas_horas_extras and ocorr_norm == "mais de duas horas extras":
                pass
            elif ocorr_norm == "horas faltantes" and converter_horas_para_minutos(valor_str) < 60:
                pass
            elif ocorr_norm == "horas extras":
                try:
                    h, m = map(int, valor_str.split(":"))
                    if h * 60 + m >= 120:
                        tpl = TEMPLATES.get(ocorr_limpo)
                        if tpl:
                            horas_fmt = formatar_horas_extras(valor_str)
                            msg = tpl.format(
                                nome=nome,
                                data=data,
                                valor=valor_str,
                                horas=formatar_horas(valor_str),
                                horas_extras=horas_fmt,
                                horas_minutos=horas_fmt,
                                intervalo=horas_fmt,
                            ).strip()
                            if msg and msg not in mensagens_set:
                                msgs.append(msg)
                                mensagens_set.add(msg)
                                if ocorr_limpo not in motivos_utilizados:
                                    motivos_utilizados.append(ocorr_limpo)
                except Exception:
                    pass
            else:
                tpl = TEMPLATES.get(ocorr_limpo)
                if tpl:
                    horas_fmt = formatar_horas_extras(valor_str)
                    msg = tpl.format(
                        nome=nome,
                        data=data,
                        valor=valor_str,
                        horas=formatar_horas(valor_str),
                        horas_extras=horas_fmt,
                        horas_minutos=horas_fmt,
                        intervalo=horas_fmt,
                    ).strip()
                    if msg and msg not in mensagens_set:
                        msgs.append(msg)
                        mensagens_set.add(msg)
                        if ocorr_limpo not in motivos_utilizados:
                            motivos_utilizados.append(ocorr_limpo)

        # Processamento Ocorrências (seja na coluna 'Motivo' ou 'Ocorrência')
        motivo_oco = motivo if (isinstance(motivo, str) and motivo.strip() and motivo.strip() not in {"nan", "None"}) else None
        if not motivo_oco and isinstance(ocorr, str) and validar_motivo(ocorr.strip()):
            motivo_oco = ocorr.strip()

        if motivo_oco and validar_motivo(motivo_oco):
            msg_oco = gerar_linha_ocorrencia(row)
            if msg_oco and msg_oco not in mensagens_set:
                msgs.append(msg_oco)
                mensagens_set.add(msg_oco)
                if motivo_oco not in motivos_utilizados:
                    motivos_utilizados.append(motivo_oco)

    if not msgs:
        return None

    return MensagemDetalhada(texto="\n".join(msgs), motivos=[m for m in motivos_utilizados if m])


# === Gera todas as mensagens agrupadas por Nome + Data ===

def gerar_mensagens(df, tipo_relatorio):
    tipo_normalizado = tipo_relatorio.strip().lower()

    if tipo_normalizado not in {"auditoria", "ocorrencias", "ocorrências"}:
        raise ValueError(f"Tipo de relatório inválido: {tipo_relatorio!r}")

    if "FaltaAbonadaJustificada" not in df.columns:
        df["FaltaAbonadaJustificada"] = False

    indices = []
    valores = []
    for (nome_grupo, data_grupo), grupo in df.groupby(["Nome", "Data"], sort=False):
        resultado = gerar_mensagem(grupo)
        if resultado is not None:
            indices.append((nome_grupo, data_grupo))
            valores.append(resultado)

    if not valores:
        return pd.Series(dtype=object)

    mensagens = pd.Series(
        valores,
        index=pd.MultiIndex.from_tuples(indices, names=["Nome", "Data"]),
    )

    return mensagens.dropna()
