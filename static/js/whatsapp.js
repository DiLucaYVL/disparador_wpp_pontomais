// IMPORTAÇÃO ATUALIZADA
import { carregarConfig } from './config.js';
// Controle de timeout para requisições
const REQUEST_TIMEOUT = 10000; // 10 segundos

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

function _getHeaders(token) {
    return {
        'Content-Type': 'application/json',
        'apiKey': token
    };
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

    // 🟢 CARREGANDO CONFIG
    const { api_url, instance, token } = await carregarConfig();

    try {
        // Consulta o status da conexão
        const statusRes = await createRequestWithTimeout(`${api_url}/instance/connectionState/${instance}`, {
            headers: _getHeaders(token)
        });
        
        if (!statusRes.ok) {
            throw new Error(`Erro na consulta de status: ${statusRes.status}`);
        }
        
        const statusData = await statusRes.json();
        const state = statusData.instance?.state?.toUpperCase();

        if (state !="OPEN" && state !="CONNECTING") {
            console.log("📡 Status Evolution:", state);
            console.log("📋 Status completo:", statusData);
        }
        
       /* if (state === "CLOSE" || !state) {
            nomeElem.textContent = "🔴 WhatsApp desconectado";
            numeroElem.textContent = "Escaneie o QR Code para conectar";
            fotoElem.src = "";
            fotoElem.style.display = "none";
            fotoElem.parentElement.querySelector('.avatar-placeholder').style.display = "flex";
            qrContainer.style.display = "none";

            mainContent.classList.add('hidden');
            connectionMessage.classList.remove('hidden');
            logoutSection.classList.add('hidden');

            // NÃO fazer reconexão automática - deixar manual
            return "CLOSE";
        }*/

        if (state === "CONNECTING" || state === "CLOSE" ) {
            nomeElem.textContent = "📷 Escaneie o QR Code para conectar.";
            numeroElem.textContent = "";
            fotoElem.src = "";

            // Para Evolution API, o QR code é obtido via endpoint específico
            try {
                const qrRes = await createRequestWithTimeout(`${api_url}/instance/connect/${instance}`, {
                    headers: _getHeaders(token)
                });
                const qrData = await qrRes.json();
                
                if (qrData.base64) {
                    qrImage.src = qrData.base64;
                    qrImage.style.display = "block";
                    qrContainer.style.display = "block";
                } else {
                    console.warn("QR Code não encontrado na resposta.", qrData);
                }
                
            } catch (qrError) {
                console.error("Erro ao obter QR Code:", qrError);
            }

            mainContent.classList.add('hidden');
            connectionMessage.classList.remove('hidden');
            logoutSection.classList.add('hidden');

            // console.log("🟢 QR Code solicitado");
            return "CONNECTING";
        }

        if (state === "OPEN") {
            try {
                // Busca dados completos da instância
                const instanceRes = await createRequestWithTimeout(`${api_url}/instance/fetchInstances?instanceName=${instance}`, {
                    headers: _getHeaders(token)
                });

                if (!instanceRes.ok) throw new Error("Erro ao buscar dados da instância");

                const list = await instanceRes.json();
                const inst = Array.isArray(list) ? list[0] : list;

                // Extrai dados
                const profileName = inst?.profileName || 'Usuário';
                const ownerNumber = (inst?.ownerJid || '').split('@')[0] || instance;
                const profilePictureUrl = inst?.profilePicUrl || null;

                // Preenche na interface
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
                numeroElem.textContent = `📞 ${instance}`;
                fotoElem.src = "";
                fotoElem.style.display = "none";
                fotoElem.parentElement.querySelector('.avatar-placeholder').style.display = "flex";
            }

            qrContainer.style.display = "none";
            mainContent.classList.remove('hidden');
            connectionMessage.classList.add('hidden');
            logoutSection.classList.remove('hidden');
            return "OPEN";
        }

        // Estado desconhecido - apenas se não for nenhum dos estados conhecidos
        if (state !== "CLOSE" && state !== "CONNECTING" && state !== "OPEN") {
            nomeElem.textContent = "⚠️ Instância em estado indefinido.";
            numeroElem.textContent = `Status: ${state}`;
            fotoElem.src = "";
            fotoElem.style.display = "none";
            fotoElem.parentElement.querySelector('.avatar-placeholder').style.display = "flex";
            qrContainer.style.display = "none";

            mainContent.classList.add('hidden');
            connectionMessage.classList.remove('hidden');
            logoutSection.classList.add('hidden');

            return "ESTADO DESCONHECIDO: " +state;
        }

    } catch (err) {
        console.error("❌ Erro ao consultar status do WhatsApp:", err);
        nomeElem.textContent = "❌ Erro de conexão com Evolution API.";
        numeroElem.textContent = "";
        fotoElem.src = "";
        fotoElem.style.display = "none";
        fotoElem.parentElement.querySelector('.avatar-placeholder').style.display = "flex";
        qrContainer.style.display = "none";

        mainContent.classList.add('hidden');
        connectionMessage.classList.remove('hidden');
        logoutSection.classList.add('hidden');

        return "ERROR";
    }
}

export async function fazerLogoutWhatsapp() {
    const logoutButton = document.getElementById('logoutButton');

    try {
        const { api_url, instance, token } = await carregarConfig();

        logoutButton.disabled = true;
        logoutButton.innerHTML = '<span class="logout-icon">⏳</span><span class="logout-text">Desconectando...</span>';

        const response = await createRequestWithTimeout(`${api_url}/instance/logout/${instance}`, {
            method: "DELETE",
            headers: _getHeaders(token)
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