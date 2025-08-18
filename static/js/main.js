// static/js/main.js
import { configurarEventos } from './eventos.js';
import { verificarStatusWhatsapp, fazerLogoutWhatsapp } from './whatsapp.js';
import { configurarDragAndDrop } from './dragdrop.js';
import { carregarConfig } from './config.js';

let intervalId = null;
let isConnected = false;

async function verificarStatusComIntervalo() {
    const status = await verificarStatusWhatsapp();
    
    // Se o status mudou de desconectado para conectado
    if (!isConnected && status === 'OPEN') {
        isConnected = true;
        // Para o intervalo atual e reinicia com 5 segundos
        if (intervalId) {
            clearInterval(intervalId);
        }
        intervalId = setInterval(verificarStatusComIntervalo, 5000);
        console.log('🟢 WhatsApp conectado - Mudando verificação para 5 segundos');
    }
    // Se o status mudou de conectado para desconectado
    else if (isConnected && status !== 'OPEN') {
        isConnected = false;
        // Para o intervalo atual e reinicia com 1 segundo
        if (intervalId) {
            clearInterval(intervalId);
        }
        intervalId = setInterval(verificarStatusComIntervalo, 1000);
        console.log('🔄 WhatsApp desconectado - Mudando verificação para 1 segundo');
    }
    
    return status;
}

window.addEventListener('DOMContentLoaded', async () => {
    await carregarConfig();
    
    configurarEventos();
    configurarDragAndDrop();
    
    // Primeira verificação
    await verificarStatusComIntervalo();
    
    // Inicia com verificação a cada 1 segundo
    intervalId = setInterval(verificarStatusComIntervalo, 1000);
    
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