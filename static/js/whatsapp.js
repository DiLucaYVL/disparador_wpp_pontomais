// Controle de timeout para requisições
const REQUEST_TIMEOUT = 10000; // 10 segundos

const API_BASE_URL = window.location.origin;

function createRequestWithTimeout(url, options = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
    
    return fetch(url, {
        ...options,
        signal: controller.signal
    }).finally(() => {
        clearTimeout(timeoutId);
    });
}

export async function verificarStatusWhatsapp() {
    const nomeElem = document.getElementById('whatsappNome');
    const numeroElem = document.getElementById('whatsappNumero');
    const fotoElem = document.getElementById('whatsappFoto');
    const qrImage = document.getElementById('qrImage');
    const qrContainer = document.getElementById('qrContainer');
    const mainContent = document.getElementById('mainContent');
    const connectionMessage = document.getElementById('connectionMessage');
    const logoutSection = document.getElementById('logoutSection');
    const historySection = document.getElementById('historySection');

    try {
        const statusRes = await createRequestWithTimeout(`${API_BASE_URL}/whatsapp/status`);
        if (!statusRes.ok) {
            throw new Error(`Erro na consulta de status: ${statusRes.status}`);
        }
        
        const statusData = await statusRes.json();
        const { connected, status } = statusData;

        if (status && status.toUpperCase() !== 'OPEN') {
            console.log("📡 Status WhatsApp:", status);
        }

        if (connected) {
            // Estado OPEN - Conectado
            try {
                const instanceRes = await createRequestWithTimeout(`${API_BASE_URL}/whatsapp/instance`);
                if (!instanceRes.ok) throw new Error("Erro ao buscar dados da instância");

                const list = await instanceRes.json();
                const inst = Array.isArray(list) ? list[0] : list;
                
                const profileName = inst?.profileName || "Ponto | DP";
                const ownerNumber = (inst?.ownerJid || '').split('@')[0] || '';
                const profilePictureUrl = inst?.profilePicUrl || null;

                nomeElem.textContent = `🟢 ${profileName}`;
                numeroElem.textContent = `📞 ${ownerNumber}`;

                if (profilePictureUrl) {
                    fotoElem.src = profilePictureUrl;
                    fotoElem.style.display = "block";
                    fotoElem.parentElement.querySelector('.avatar-placeholder').style.display = "none";
                } else {
                    fotoElem.src = "";
                    fotoElem.style.display = "none";
                    fotoElem.parentElement.querySelector('.avatar-placeholder').style.display = "flex";
                }

            } catch (profileError) {
                console.warn("Erro ao obter dados da instância:", profileError);
                nomeElem.textContent = `🟢 Conectado`;
                numeroElem.textContent = '';
                fotoElem.src = "";
                fotoElem.style.display = "none";
                fotoElem.parentElement.querySelector('.avatar-placeholder').style.display = "flex";
            }

            qrContainer.style.display = "none";
            mainContent.classList.remove('hidden');
            connectionMessage.classList.add('hidden');
            logoutSection.classList.remove('hidden');
            historySection.classList.remove('hidden');
            return "OPEN";
        }
        
        // Estado CLOSE/CONNECTING - Desconectado ou aguardando QR
        nomeElem.textContent = "📷 Escaneie o QR Code para conectar.";
        numeroElem.textContent = "";
        fotoElem.src = "";
        fotoElem.style.display = "none";
        fotoElem.parentElement.querySelector('.avatar-placeholder').style.display = "flex";

        try {
            const qrRes = await createRequestWithTimeout(`${API_BASE_URL}/whatsapp/qr`);
            const qrData = await qrRes.json();

            if (qrData.qr_code) {
                qrImage.src = qrData.qr_code;
                qrImage.style.display = "block";
                qrContainer.style.display = "block";
            } else {
                console.warn("QR Code não encontrado na resposta.", qrData);
                qrContainer.style.display = "none";
            }
        } catch (qrError) {
            console.error("Erro ao obter QR Code:", qrError);
            qrContainer.style.display = "none";
        }

        mainContent.classList.add('hidden');
        connectionMessage.classList.remove('hidden');
        logoutSection.classList.add('hidden');
        historySection.classList.add('hidden');
        
        return "CLOSE";

    } catch (err) {
        console.error("❌ Erro ao consultar status do WhatsApp:", err);
        nomeElem.textContent = "❌ Erro de conexão com a API.";
        numeroElem.textContent = "Verifique o console para mais detalhes.";
        fotoElem.src = "";
        fotoElem.style.display = "none";
        fotoElem.parentElement.querySelector('.avatar-placeholder').style.display = "flex";
        qrContainer.style.display = "none";

        mainContent.classList.add('hidden');
        connectionMessage.classList.remove('hidden');
        logoutSection.classList.add('hidden');
        historySection.classList.add('hidden');

        return "ERROR";
    }
}


export async function fazerLogoutWhatsapp() {
    const logoutButton = document.getElementById('logoutButton');

    try {
        logoutButton.disabled = true;
        logoutButton.innerHTML = '<span class="logout-icon">⏳</span><span class="logout-text">Desconectando...</span>';

        const response = await createRequestWithTimeout(`${API_BASE_URL}/whatsapp/logout`, {
            method: "DELETE"
        });

        if (response.ok) {
            console.log("Logout realizado com sucesso");
            window.location.reload();
        } else {
            throw new Error(`Erro no logout: ${response.status}`);
        }

    } catch (error) {
        console.error("Erro ao fazer logout:", error);
        logoutButton.disabled = false;
        logoutButton.innerHTML = '<span class="logout-icon">🚪</span><span class="logout-text">Desconectar WhatsApp</span>';
        alert("Erro ao desconectar do WhatsApp. Tente novamente.");
    }
}
