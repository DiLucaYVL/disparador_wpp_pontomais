import { gerarFormData } from './helpers.js';
import { enviarCSV, obterStatus } from './api.js';
import { mostrarLogs, atualizarEstatisticas, mostrarDebug, atualizarBarraProgresso } from './ui.js';
import { carregarDropdownEquipes } from './dropdown.js';

// URL base da API definida globalmente
const API_BASE_URL = window.API_BASE_URL;

let arquivoInput = document.getElementById('csvFile');
let arquivoSelecionado = null;  // Arquivo mantido em memória

export function configurarEventos() {
    // Quando o usuário seleciona um arquivo
    arquivoInput.addEventListener('change', async () => {
        arquivoSelecionado = arquivoInput.files[0];  // Armazena o arquivo selecionado
        if (!arquivoSelecionado) return;

        document.getElementById('sendButton').disabled = false;
        document.getElementById('fileName').textContent = `Arquivo selecionado: ${arquivoSelecionado.name}`;
        document.getElementById('fileName').style.display = "block";

        const formData = new FormData();
        formData.append('csvFile', arquivoSelecionado);
        formData.append('ignorarSabados', document.getElementById('ignorarSabados').checked);
        formData.append('tipoRelatorio', document.getElementById('tipoRelatorio').value);

        try {
            const tipoRelatorioAtual = document.getElementById('tipoRelatorio').value;
            const response = await fetch(`${API_BASE_URL}/equipes`, { method: 'POST', body: formData });

            if (!response.ok) {
                const texto = await response.text();  // Evita erro de JSON inválido
                console.warn("Resposta erro (texto):", texto);

                let msgErro = "Erro ao processar o arquivo CSV.";
                if (tipoRelatorioAtual === "Ocorrências") {
                    msgErro = "❌ O tipo de relatório selecionado foi 'Ocorrências', mas o arquivo não contém as colunas esperadas ('Motivo', 'Ação pendente', etc).";
                } else if (tipoRelatorioAtual === "Auditoria") {
                    msgErro = "❌ O tipo de relatório selecionado foi 'Auditoria', mas o arquivo está em formato incorreto.";
                } else if (tipoRelatorioAtual === "Assinaturas") {
                    msgErro = "❌ O tipo de relatório selecionado foi 'Assinaturas', mas o arquivo está em formato incorreto.";
                }

                throw new Error(msgErro);
            }

            const data = await response.json();

            if (data.success && Array.isArray(data.equipes)) {
                carregarDropdownEquipes(data.equipes);
            } else {
                alert("Erro desconhecido ao processar o CSV.");
            }

        } catch (err) {
            console.error("Erro ao carregar equipes:", err);
            alert(err.message || "Erro inesperado ao tentar ler o CSV.");
        }

    });

    // Quando clica no botão Enviar
    document.getElementById('sendButton').addEventListener('click', async () => {
        const fileAtual = arquivoInput.files?.[0] || arquivoSelecionado;

        if (!fileAtual) {
            alert("Selecione um arquivo CSV.");
            return;
        }

        const botao = document.getElementById('sendButton');
        botao.disabled = true;

        arquivoSelecionado = fileAtual; // Atualiza para manter válido
        const ignorarSabados = document.getElementById('ignorarSabados').checked;
        const debugMode = document.getElementById('debugMode')?.checked || false;
        const tipoRelatorio = document.getElementById('tipoRelatorio').value;

        const equipesSelecionadas = Array.from(document.querySelectorAll('input[name="equipes"]:checked'))
            .map(e => e.value);

        const formData = gerarFormData(fileAtual, ignorarSabados, debugMode, equipesSelecionadas, tipoRelatorio);

        atualizarBarraProgresso("25%");
        console.info("📦 Enviando arquivo:", arquivoSelecionado);

        try {
            const taskId = await enviarCSV(formData);
            mostrarLogs([{ type: "info", message: "📨 Processamento agendado. Aguardando resultado..." }]);

            const resultado = await acompanharTarefa(taskId);

            mostrarLogs(resultado.log);
            atualizarEstatisticas(resultado.stats);
            atualizarBarraProgresso("100%");

            if (debugMode && resultado.debug) {
                mostrarDebug(resultado.debug);
            }

            document.getElementById('fileName').textContent = `Arquivo mantido: ${arquivoSelecionado.name}`;
            document.getElementById('fileName').style.display = "block";

        } catch (error) {
            console.error("❌ Erro durante envio ou processamento:", error);
            alert(error.message || "Erro de rede ou servidor.");
        } finally {
            botao.disabled = false;
        }
    });
}

// ✅ Evento global fora das funções
//document.addEventListener("DOMContentLoaded", async () => {
//    configurarEventos();            // ativa os listeners de arquivo e botão
//});

async function acompanharTarefa(taskId) {
    while (true) {
        const data = await obterStatus(taskId);
        if (data.status === 'done') {
            return data;
        }
        if (data.status === 'error') {
            throw new Error(data.error || 'Erro no processamento');
        }
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
}
