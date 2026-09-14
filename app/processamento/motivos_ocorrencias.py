# Mapeamento dos tipos de motivos para o relatório de ocorrências
MOTIVOS_OCORRENCIAS = {
    "Número de pontos menor que o previsto": "Número de pontos menor que o previsto",
    "Possui pontos durante exceção": "Possui pontos durante exceção",
    "Número errado de pontos": "Número errado de pontos",
}

# Mapeamento dos tipos de ações pendentes para o relatório de ocorrências
ACOES_PENDENTES = {
    "Colaborador solicitar ajuste": "Colaborador solicitar ajuste",
    "Gestor aprovar solicitação de ajuste": "Gestor aprovar solicitação de ajuste",
    "Gestor corrigir lançamento de exceção": "Gestor corrigir lançamento de exceção"
}

# Única ação pendente considerada "pendência do gestor" para fins de envio
# filtrado (checkbox "Enviar apenas pendências do gestor" no frontend).
ACAO_PENDENTE_GESTOR = "Gestor aprovar solicitação de ajuste"

def validar_motivo(motivo):
    """Valida se o motivo está na lista de motivos válidos"""
    return motivo in MOTIVOS_OCORRENCIAS

def validar_acao_pendente(acao):
    """Valida se a ação pendente está na lista de ações válidas"""
    return acao in ACOES_PENDENTES

def eh_pendencia_gestor(acao):
    """Indica se a ação pendente informada depende de aprovação do gestor"""
    return str(acao).strip() == ACAO_PENDENTE_GESTOR

def obter_motivos_validos():
    """Retorna a lista de motivos válidos"""
    return list(MOTIVOS_OCORRENCIAS.keys())

def obter_acoes_validas():
    """Retorna a lista de ações pendentes válidas"""
    return list(ACOES_PENDENTES.keys())

