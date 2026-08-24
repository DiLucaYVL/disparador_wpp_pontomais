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
        const connected = Boolean(
            statusData.connected
            || (typeof statusData.status === 'string' && statusData.status.toLowerCase() === 'open')
            || (typeof statusData.state === 'string' && statusData.state.toLowerCase() === 'open')
        );
        const estadoAtual = (statusData.state || statusData.status || '').toLowerCase();

        if (estadoAtual && estadoAtual !== 'open') {
            console.log("📡 Status WhatsApp:", estadoAtual);
        }

        if (connected) {
            // Estado OPEN - Conectado
            try {
                const instanceRes = await createRequestWithTimeout(`${API_BASE_URL}/whatsapp/instance`);
                if (!instanceRes.ok) throw new Error("Erro ao buscar dados da instância");

                const list = await instanceRes.json();
                const rawInst = Array.isArray(list) ? list[0] : list;
                const inst = (rawInst && typeof rawInst === 'object' && rawInst.instance) ? rawInst.instance : (rawInst || {});
                
                const profileName = inst?.profileName || inst?.name || inst?.instanceName || "WhatsApp Conectado";
                const rawNumber = inst?.ownerJid || inst?.owner || inst?.number || inst?.id || '';
                const ownerNumber = rawNumber ? rawNumber.split('@')[0].replace(/\D/g, '') : '';
                const profilePictureUrl = inst?.profilePictureUrl || inst?.profilePicUrl || null;

                nomeElem.textContent = `🟢 ${profileName}`;
                numeroElem.textContent = ownerNumber ? `📞 ${ownerNumber}` : '';

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
                nomeElem.textContent = `🟢 WhatsApp Conectado`;
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
        
        // Estado CLOSE / CONNECTING - Desconectado ou aguardando QR
        if (estadoAtual === 'connecting') {
            nomeElem.textContent = "🔄 Conectando ao WhatsApp...";
            numeroElem.textContent = "Aguarde ou escaneie o QR Code abaixo.";
        } else {
            nomeElem.textContent = "📷 Escaneie o QR Code para conectar.";
            numeroElem.textContent = "";
        }

        fotoElem.src = "";
        fotoElem.style.display = "none";
        fotoElem.parentElement.querySelector('.avatar-placeholder').style.display = "flex";

        try {
            const qrRes = await createRequestWithTimeout(`${API_BASE_URL}/whatsapp/qr`);
            const qrData = await qrRes.json();

            if (qrData.qr_code) {
                let qrSrc = qrData.qr_code;
                if (typeof qrSrc === 'string' && !qrSrc.startsWith('data:image') && !qrSrc.startsWith('http')) {
                    qrSrc = `data:image/png;base64,${qrSrc}`;
                }
                qrImage.src = qrSrc;
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
        
        return estadoAtual ? estadoAtual.toUpperCase() : "CLOSE";

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
