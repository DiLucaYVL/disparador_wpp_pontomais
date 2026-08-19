import re
import logging

# === Mapeamento de equipe ===
def mapear_equipe(txt):
    txt = str(txt).lower()

    # Correção para erros como "Loja l 66"
    txt = txt.replace("loja l ", "loja ")
    txt = txt.replace("loja  l ", "loja ")
    txt = txt.replace("loja  ", "loja ")

    if "departamento pessoal" in txt: return "DP"
    if any(x in txt for x in ["cd10", "cd 10", "cd-10"]): return "CD10"
    if any(x in txt for x in ["cd20", "cd 20", "cd-20"]): return "CD20"
    if any(x in txt for x in ["cd30", "cd 30", "cd-30", "cd - 30"]): return "CD30"

    # Captura códigos como 75, A1, B4 — mesmo com "Loja Nova", "LojaNova", "Filial Nova", etc.
    match = re.search(r"\b(?:loja|filial)[^\da-zA-Z]*(?:nova)?\s*([a-z]?\d{1,3}[a-z]?)\b", txt, re.IGNORECASE)
    if match:
        loja_codigo = match.group(1).upper()
        return loja_codigo  # Apenas o código: ex. "75", "B2", "A1"

    if "comercial" in txt or "expansão" in txt: return "Comercial"
    if "visual merchandising" in txt: return "VM"
    if any(x in txt for x in ["crédito e cobrança", "credito e cobrança", "credito e cobranca"]): return "Fintech"
    if "compras" in txt: return "Compras"
    if "contábil" in txt or "contabilidade" in txt: return "Contábil"
    if "controladoria" in txt: return "Controladoria"
    
    if "financeiro" in txt:
        if "equipe 01" in txt: return "Financeiro 01"
        if "equipe 02" in txt: return "Financeiro 02"
        if "equipe 03" in txt: return "Financeiro 03"
        return "Outro"
    
    if "gente e gestão" in txt: return "RH"
    if "logística" in txt or "logistica" in txt: return "Produtos"
    if "marketing" in txt: return "Marketing"
    if "obras" in txt: return "Obras"
    if "transporte" in txt: return "Transporte"
    if any(x in txt for x in ["t.i", " ti ", "tech", "tecnologia", "tecnologia da informação"]): return "Tech"
    if re.search(r"\bti\b", txt): return "Tech"
    if any(x in txt for x in ["processos", "recepção", "serviços gerais"]): return "OPS"

    return "Outro"

def eh_loja(txt):
    txt = str(txt).lower()
    txt = txt.replace("loja l ", "loja ")
    txt = txt.replace("loja  l ", "loja ")
    txt = txt.replace("loja  ", "loja ")
    return bool(re.search(r"\b(?:loja|filial)[^\da-zA-Z]*(?:nova)?\s*([a-z]?\d{1,3}[a-z]?)\b", txt, re.IGNORECASE))

