import { mostrarLogs } from './ui.js';
import { 
    obterMensagemErroDetalhada, 
    processarRespostaHTTP, 
    tratarErroCompleto,
    categorizarErro 
} from './mapear-erro.js';

/**
 * Envia CSV para processamento no servidor
 * @param {FormData} formData - Dados do formulário incluindo arquivo CSV
 * @returns {Promise<Object>} Resposta do servidor
 */
export async function enviarCSV(formData) {
    const botao = document.getElementById('sendButton');
    botao.disabled = true;

    mostrarLogs([{ type: "info", message: "🚀 Envio iniciado. Processando o arquivo..." }]);

    try {
        const res = await fetch('/enviar', {
            method: 'POST',
            body: formData
        });

        // Processa erros HTTP primeiro
        const erroHTTP = await processarRespostaHTTP(res);
        if (erroHTTP) {
            mostrarLogs([{ type: "error", message: erroHTTP }]);
            
            // Log adicional para desenvolvedores (console)
            console.error(`Erro HTTP ${res.status}:`, {
                status: res.status,
                statusText: res.statusText,
                url: res.url,
                mensagem: erroHTTP
            });
            
            throw new Error(erroHTTP);
        }

        // Se chegou até aqui, tenta parsear JSON
        const data = await res.json();
        
        // Verifica se o servidor retornou sucesso
        if (!data.success) {
            if (data.log && Array.isArray(data.log)) {
                mostrarLogs(data.log);
            } else {
                mostrarLogs([{ type: "error", message: "❌ Servidor retornou erro sem detalhes." }]);
            }
            throw new Error("Servidor retornou erro");
        }
        
        return data;
        
    } catch (error) {
        // Se ainda não foi mostrado erro, processa com o sistema de mapeamento
        if (!error.message.includes('HTTP') && !error.message.includes('Servidor retornou erro')) {
            const mensagemDetalhada = obterMensagemErroDetalhada(error);
            const categoria = categorizarErro(error);
            
            mostrarLogs([{ type: "error", message: mensagemDetalhada }]);
            
            // Log técnico para desenvolvedores
            console.error('Erro detalhado na comunicação:', {
                categoria,
                mensagem: mensagemDetalhada,
                errorOriginal: error.message,
                stack: error.stack,
                timestamp: new Date().toISOString()
            });
        }
        
        throw error;
    } finally {
        botao.disabled = false;
    }
}

/**
 * Obtém lista de equipes do CSV enviado
 * @param {FormData} formData - Dados do formulário incluindo arquivo CSV
 * @returns {Promise<Object>} Lista de equipes
 */
export async function obterEquipes(formData) {
    try {
        const res = await fetch('/equipes', { 
            method: 'POST', 
            body: formData 
        });
        
        // Verifica erros HTTP usando o sistema de mapeamento
        const erroHTTP = await processarRespostaHTTP(res);
        if (erroHTTP) {
            console.error('Erro HTTP ao obter equipes:', {
                status: res.status,
                mensagem: erroHTTP
            });
            throw new Error(erroHTTP);
        }
        
        const data = await res.json();
        
        // Verifica se a resposta foi bem-sucedida
        if (!data.success) {
            const mensagemErro = data.error || "Erro desconhecido ao processar equipes";
            throw new Error(mensagemErro);
        }
        
        return data;
        
    } catch (error) {
        const mensagemDetalhada = obterMensagemErroDetalhada(error);
        const categoria = categorizarErro(error);
        
        // Log para desenvolvedores
        console.error('Erro ao obter equipes:', {
            categoria,
            mensagem: mensagemDetalhada,
            errorOriginal: error.message,
            timestamp: new Date().toISOString()
        });
        
        throw new Error(mensagemDetalhada);
    }
}

/**
 * Função auxiliar para debugging - mostra informações detalhadas do erro
 * @param {Error|Response} errorOrResponse - Erro ou resposta para análise
 */
export async function debugError(errorOrResponse) {
    try {
        const resultado = await tratarErroCompleto(errorOrResponse);
        
        console.group('🔍 Debug de Erro Detalhado');
        console.log('📋 Mensagem:', resultado.mensagem);
        console.log('🏷️ Categoria:', resultado.categoria);
        console.log('💡 Sugestões:', resultado.sugestoes);
        console.log('⏰ Timestamp:', resultado.timestamp);
        console.groupEnd();
        
        return resultado;
    } catch (debugErr) {
        console.error('Erro no debug do erro:', debugErr);
        return null;
    }
}

// Exporta funções de erro para uso em outros módulos se necessário
export { 
    obterMensagemErroDetalhada, 
    processarRespostaHTTP, 
    tratarErroCompleto 
};