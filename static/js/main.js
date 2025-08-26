// static/js/main.js
import { configurarEventos } from './eventos.js';
import { verificarStatusWhatsapp, fazerLogoutWhatsapp } from './whatsapp.js';
import { configurarDragAndDrop } from './dragdrop.js';
let intervalId = null;
let isConnected = false;
let isChecking = false; // Adicionar debouncing

async function verificarStatusComIntervalo() {
    // Debouncing - evita múltiplas verificações simultâneas
    if (isChecking) {
        console.log('⏭️ Verificação já em andamento, pulando...');
        return isConnected ? 'OPEN' : 'CLOSE';
    }
    
    isChecking = true;
    
    try {
        const status = await verificarStatusWhatsapp();
        
        // Apenas atualiza o estado, sem mudar intervalos
        const wasConnected = isConnected;
        isConnected = (status === 'OPEN');
        
        // Log apenas quando o estado muda
        if (wasConnected !== isConnected) {
            console.log(`📡 Estado mudou: ${wasConnected ? 'CONECTADO' : 'DESCONECTADO'} → ${isConnected ? 'CONECTADO' : 'DESCONECTADO'}`);
        }
        
        return status;
    } catch (error) {
        console.error('❌ Erro na verificação:', error);
        return 'ERROR';
    } finally {
        isChecking = false;
    }
}
window.addEventListener('DOMContentLoaded', async () => {
    configurarEventos();
    configurarDragAndDrop();
    
    // Primeira verificação
    await verificarStatusComIntervalo();
    
    // Inicia com verificação a cada 5 segundos
    intervalId = setInterval(verificarStatusComIntervalo, 5000);
    console.log('🔄 Monitoramento iniciado com intervalo fixo de 5 segundos');

    const logoutButton = document.getElementById('logoutButton');
    if (logoutButton) {
        logoutButton.addEventListener('click', async () => {
            await fazerLogoutWhatsapp();
            // Após logout, volta para verificação rápida
            isConnected = false;
            if (intervalId) {
                clearInterval(intervalId);
            }
            intervalId = setInterval(verificarStatusComIntervalo, 1000);
        });
    }
});

// Limpa o intervalo quando a página for fechada
window.addEventListener('beforeunload', () => {
    if (intervalId) {
        clearInterval(intervalId);
    }
});