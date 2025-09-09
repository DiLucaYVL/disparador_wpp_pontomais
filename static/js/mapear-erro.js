// static/js/mapear-erro.js
// Módulo responsável pelo mapeamento e tratamento de erros da aplicação

/**
 * Mapeia diferentes tipos de erros JavaScript para mensagens user-friendly
 * @param {Error} error - Objeto de erro capturado
 * @returns {string} Mensagem de erro formatada para o usuário
 */
export function obterMensagemErroDetalhada(error) {
    // 1. Erro de rede/conectividade
    if (error.name === 'TypeError' && (error.message.includes('fetch') || error.message.includes('Failed to fetch'))) {
        return " Erro de conexão: Verifique se o servidor está rodando e sua internet está funcionando.";
    }
    
    // 2. Timeout/AbortError
    if (error.name === 'AbortError' || error.message.includes('timeout') || error.message.includes('aborted')) {
        return " Timeout: O servidor demorou muito para responder. Tente novamente em alguns segundos.";
    }
    
    // 3. Erro de CORS
    if (error.message.includes('CORS') || 
        error.message.includes('cross-origin') || 
        error.message.includes('Access-Control-Allow-Origin')) {
        return " Erro CORS: Problema de configuração de segurança. Contate o administrador.";
    }
    
    // 4. Erro de rede geral
    if (error.name === 'NetworkError' || error.message.includes('NetworkError')) {
        return " Erro de rede: Verifique sua conexão com a internet e tente novamente.";
    }
    
    // 5. Erro de parsing JSON
    if (error.name === 'SyntaxError' && error.message.includes('JSON')) {
        return " Resposta inválida do servidor: Dados corrompidos recebidos.";
    }
    
    // 6. Erro de arquivo não encontrado
    if (error.message.includes('404') || error.message.includes('Not Found')) {
        return " Servidor não encontrado: Verifique se a aplicação está rodando na porta correta.";
    }
    
    // 7. Erro de SSL/TLS
    if (error.message.includes('SSL') || error.message.includes('certificate') || error.message.includes('TLS')) {
        return " Erro de segurança SSL: Problema com certificados de segurança.";
    }
    
    // 8. Erro de referência (código JavaScript)
    if (error.name === 'ReferenceError') {
        return ` Erro interno da aplicação: ${error.message}. Recarregue a página.`;
    }
    
    // 9. Erro de tipo (código JavaScript)
    if (error.name === 'TypeError' && !error.message.includes('fetch')) {
        return ` Erro de tipo: ${error.message}. Recarregue a página e tente novamente.`;
    }
    
    // 10. Quota exceeded (localStorage, etc)
    if (error.name === 'QuotaExceededError') {
        return " Espaço insuficiente: Limpe o cache do navegador e tente novamente.";
    }
    
    // 11. Erro genérico com detalhes técnicos (fallback)
    const mensagemTecnica = error.message || 'Erro desconhecido';
    return ` Erro de comunicação: ${mensagemTecnica}`;
}

/**
 * Mapeia códigos de status HTTP para mensagens específicas
 * @param {number} status - Código de status HTTP
 * @param {string} statusText - Texto do status HTTP
 * @returns {string} Mensagem de erro formatada
 */
export function obterMensagemHTTP(status, statusText = '') {
    const mensagens = {
        // 4xx - Erros do cliente
        400: " Dados inválidos: Verifique o arquivo CSV e as configurações enviadas.",
        401: " Não autorizado: Problema de autenticação com o servidor.",
        403: " Acesso negado: Sem permissão para realizar esta operação.",
        404: " Página não encontrada: Endpoint não existe no servidor.",
        405: " Método não permitido: Operação não suportada pelo servidor.",
        408: " Timeout da requisição: Servidor não respondeu a tempo.",
        409: " Conflito: Operação conflita com o estado atual do servidor.",
        413: " Arquivo muito grande: Reduza o tamanho do arquivo CSV enviado.",
        415: " Tipo de arquivo não suportado: Envie apenas arquivos CSV.",
        429: " Muitas requisições: Aguarde alguns segundos antes de tentar novamente.",
        
        // 5xx - Erros do servidor
        500: " Erro interno do servidor: Problema no processamento. Verifique os logs.",
        501: " Não implementado: Funcionalidade não disponível no servidor.",
        502: " Bad Gateway: Servidor indisponível ou com problemas de comunicação.",
        503: " Serviço indisponível: Servidor temporariamente fora do ar.",
        504: " Gateway timeout: Operação demorou muito para ser processada.",
        505: " Versão HTTP não suportada: Problema de compatibilidade."
    };
    
    const mensagemPadrao = mensagens[status];
    
    if (mensagemPadrao) {
        return mensagemPadrao;
    }
    
    // Fallback com informações técnicas
    return ` Erro HTTP ${status}: ${statusText || 'Status desconhecido'}`;
}

/**
 * Processa resposta HTTP e extrai mensagem de erro específica
 * @param {Response} response - Objeto Response do fetch
 * @returns {Promise<string|null>} Mensagem de erro ou null se não houver erro
 */
export async function processarRespostaHTTP(response) {
    if (response.ok) {
        return null; // Sem erro
    }
    
    // Obtém mensagem base do status HTTP
    let mensagem = obterMensagemHTTP(response.status, response.statusText);
    
    // Tenta extrair detalhes específicos do servidor
    try {
        const contentType = response.headers.get('content-type');
        
        if (contentType && contentType.includes('application/json')) {
            const errorData = await response.json();
            
            // Prioriza mensagens do log do servidor (Flask)
            if (errorData.log && Array.isArray(errorData.log) && errorData.log.length > 0) {
                const mensagensServidor = errorData.log
                    .map(entry => {
                        if (typeof entry === 'string') {
                            return entry.replace(/^❌\s*/, '');
                        }
                        if (entry.type === 'error') {
                            return entry.message.replace(/^❌\s*/, '');
                        }
                        return null;
                    })
                    .filter(Boolean)
                    .join(', ');

                if (mensagensServidor) {
                    return `${mensagensServidor}`;
                }
            }
            
            // Fallback para campo 'error'
            if (errorData.error) {
                return `${mensagem} Detalhes: ${errorData.error}`;
            }
            
            // Fallback para campo 'message'
            if (errorData.message) {
                return `${mensagem} Detalhes: ${errorData.message}`;
            }
        }
    } catch (parseError) {
        // Se não conseguir parsear JSON, usa mensagem HTTP padrão
        console.warn('Não foi possível parsear resposta de erro:', parseError);
    }
    
    return mensagem;
}

/**
 * Categoriza tipos de erro para logging/analytics
 * @param {Error|string} error - Erro ou mensagem de erro
 * @returns {string} Categoria do erro
 */
export function categorizarErro(error) {
    const mensagem = typeof error === 'string' ? error : error.message;
    const nome = typeof error === 'object' ? error.name : '';
    
    if (mensagem.includes('fetch') || mensagem.includes('NetworkError')) {
        return 'NETWORK';
    }
    
    if (mensagem.includes('timeout') || nome === 'AbortError') {
        return 'TIMEOUT';
    }
    
    if (mensagem.includes('CORS') || mensagem.includes('cross-origin')) {
        return 'CORS';
    }
    
    if (mensagem.includes('JSON') && nome === 'SyntaxError') {
        return 'PARSE_ERROR';
    }
    
    if (mensagem.includes('HTTP') || /\d{3}/.test(mensagem)) {
        return 'HTTP_ERROR';
    }
    
    if (nome === 'ReferenceError' || nome === 'TypeError') {
        return 'JAVASCRIPT_ERROR';
    }
    
    return 'UNKNOWN';
}

/**
 * Gera sugestões de solução baseadas no tipo de erro
 * @param {string} categoria - Categoria do erro
 * @returns {Array<string>} Lista de sugestões
 */
export function obterSugestoesSolucao(categoria) {
    const sugestoes = {
        NETWORK: [
            "Verifique sua conexão com a internet",
            "Confirme se o servidor está rodando",
            "Tente recarregar a página"
        ],
        TIMEOUT: [
            "Aguarde alguns segundos e tente novamente",
            "Verifique se o arquivo CSV não é muito grande",
            "Confirme se o servidor não está sobrecarregado"
        ],
        CORS: [
            "Contate o administrador do sistema",
            "Verifique se está acessando pelo domínio correto"
        ],
        PARSE_ERROR: [
            "Recarregue a página",
            "Limpe o cache do navegador",
            "Contate o suporte técnico"
        ],
        HTTP_ERROR: [
            "Verifique os dados enviados",
            "Confirme se o arquivo CSV está no formato correto",
            "Consulte os logs do sistema"
        ],
        JAVASCRIPT_ERROR: [
            "Recarregue a página",
            "Limpe o cache do navegador",
            "Tente usar um navegador diferente"
        ],
        UNKNOWN: [
            "Recarregue a página",
            "Tente novamente em alguns minutos",
            "Contate o suporte técnico se persistir"
        ]
    };
    
    return sugestoes[categoria] || sugestoes.UNKNOWN;
}

/**
 * Função principal para tratamento completo de erros
 * @param {Error|Response} errorOrResponse - Erro ou resposta HTTP
 * @returns {Promise<Object>} Objeto com mensagem, categoria e sugestões
 */
export async function tratarErroCompleto(errorOrResponse) {
    let mensagem, categoria;
    
    // Se for uma Response HTTP
    if (errorOrResponse instanceof Response) {
        mensagem = await processarRespostaHTTP(errorOrResponse);
        categoria = mensagem ? 'HTTP_ERROR' : null;
    }
    // Se for um Error JavaScript
    else if (errorOrResponse instanceof Error) {
        mensagem = obterMensagemErroDetalhada(errorOrResponse);
        categoria = categorizarErro(errorOrResponse);
    }
    // Se for uma string
    else {
        mensagem = String(errorOrResponse);
        categoria = categorizarErro(mensagem);
    }
    
    const sugestoes = categoria ? obterSugestoesSolucao(categoria) : [];
    
    return {
        mensagem,
        categoria,
        sugestoes,
        timestamp: new Date().toISOString()
    };
}