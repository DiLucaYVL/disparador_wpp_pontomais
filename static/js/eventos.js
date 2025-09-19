import { gerarFormData } from './helpers.js';
import { enviarCSV, obterStatus, consultarStatusRelatorio } from './api.js';
import { mostrarLogs, atualizarEstatisticas, mostrarDebug, atualizarBarraProgresso } from './ui.js';
import { carregarDropdownEquipes } from './dropdown.js';

const API_BASE_URL = window.location.origin;

const arquivoInput = document.getElementById('csvFile');
const sendButton = document.getElementById('sendButton');
const fileNameLabel = document.getElementById('fileName');
const relatorioStatusBox = document.getElementById('relatorioStatus');
const modalOverlay = document.getElementById('modalOverlay');
const modalReenvio = document.getElementById('confirmReenvioModal');
const modalConfirmarBtn = document.getElementById('confirmReenvioConfirmar');
const modalCancelarBtn = document.getElementById('confirmReenvioCancelar');

const RELATORIO_STATUS = {
    NOVO: 'novo',
    SUCESSO_TOTAL: 'sucesso_total',
    PARCIAL: 'parcial',
};

let arquivoSelecionado = null;
let statusRelatorioAtual = RELATORIO_STATUS.NOVO;
let pendenciasRelatorio = [];
let reenvioConfirmado = false;
let nomeRelatorioAtual = '';

export function configurarEventos() {
    if (!arquivoInput || !sendButton) {
        return;
    }

    if (modalConfirmarBtn) {
        modalConfirmarBtn.addEventListener('click', confirmarReenvio);
    }
    if (modalCancelarBtn) {
        modalCancelarBtn.addEventListener('click', fecharModalReenvio);
    }
    if (modalOverlay) {
        modalOverlay.addEventListener('click', fecharModalReenvio);
    }

    arquivoInput.addEventListener('change', async () => {
        await tratarArquivoSelecionado();
    });

    sendButton.addEventListener('click', async () => {
        await enviarRelatorio();
    });
}

async function tratarArquivoSelecionado() {
    arquivoSelecionado = arquivoInput.files?.[0] ?? null;
    statusRelatorioAtual = RELATORIO_STATUS.NOVO;
    pendenciasRelatorio = [];
    reenvioConfirmado = false;
    nomeRelatorioAtual = arquivoSelecionado ? arquivoSelecionado.name : '';

    if (fileNameLabel) {
        if (arquivoSelecionado) {
            fileNameLabel.textContent = `Arquivo selecionado: ${arquivoSelecionado.name}`;
            fileNameLabel.style.display = 'block';
        } else {
            fileNameLabel.textContent = '';
            fileNameLabel.style.display = 'none';
        }
    }

    limparAlertaRelatorio();

    if (!arquivoSelecionado) {
        if (sendButton) {
            sendButton.disabled = true;
        }
        return;
    }

    let bloquearEnvio = false;

    try {
        const statusInfo = await consultarStatusRelatorio(arquivoSelecionado.name);
        if (statusInfo?.success) {
            statusRelatorioAtual = statusInfo.status || RELATORIO_STATUS.NOVO;
            const detalhes = statusInfo.relatorio || {};
            pendenciasRelatorio = Array.isArray(detalhes.pendencias) ? detalhes.pendencias : [];
            const nomeExibicao = detalhes.nome_original || arquivoSelecionado.name;
            bloquearEnvio = atualizarAlertaRelatorio(
                statusRelatorioAtual,
                pendenciasRelatorio,
                nomeExibicao,
                reenvioConfirmado,
            );
        }
    } catch (error) {
        console.error('Erro ao verificar status do relatório:', error);
        bloquearEnvio = false;
        limparAlertaRelatorio();
    }

    const formData = new FormData();
    formData.append('csvFile', arquivoSelecionado);
    formData.append('ignorarSabados', document.getElementById('ignorarSabados').checked);
    formData.append('tipoRelatorio', document.getElementById('tipoRelatorio').value);

    try {
        const tipoRelatorioAtual = document.getElementById('tipoRelatorio').value;
        const response = await fetch(`${API_BASE_URL}/equipes`, { method: 'POST', body: formData });

        if (!response.ok) {
            const texto = await response.text();
            console.warn('Resposta erro (texto):', texto);

            let msgErro = 'Erro ao processar o arquivo CSV.';
            if (tipoRelatorioAtual === 'Ocorrências') {
                msgErro = "⚠️ O tipo de relatório selecionado foi 'Ocorrências', mas o arquivo não contém as colunas esperadas ('Motivo', 'Ação pendente', etc).";
            } else if (tipoRelatorioAtual === 'Auditoria') {
                msgErro = "⚠️ O tipo de relatório selecionado foi 'Auditoria', mas o arquivo está em formato incorreto.";
            } else if (tipoRelatorioAtual === 'Assinaturas') {
                msgErro = "⚠️ O tipo de relatório selecionado foi 'Assinaturas', mas o arquivo está em formato incorreto.";
            }

            throw new Error(msgErro);
        }

        const data = await response.json();

        if (data.success && Array.isArray(data.equipes)) {
            carregarDropdownEquipes(data.equipes);
        } else {
            alert('Erro desconhecido ao processar o CSV.');
        }
    } catch (err) {
        console.error('Erro ao carregar equipes:', err);
        alert(err.message || 'Erro inesperado ao tentar ler o CSV.');
        bloquearEnvio = true;
    }

    if (sendButton) {
        sendButton.disabled = bloquearEnvio;
    }
}

async function enviarRelatorio() {
    const fileAtual = arquivoInput.files?.[0] || arquivoSelecionado;

    if (!fileAtual) {
        alert('Selecione um arquivo CSV.');
        return;
    }

    if (statusRelatorioAtual === RELATORIO_STATUS.SUCESSO_TOTAL && !reenvioConfirmado) {
        alert('Confirme o reenvio antes de enviar novamente.');
        return;
    }

    if (sendButton) {
        sendButton.disabled = true;
    }

    arquivoSelecionado = fileAtual;
    const ignorarSabados = document.getElementById('ignorarSabados').checked;
    const debugMode = document.getElementById('debugMode')?.checked || false;
    const tipoRelatorio = document.getElementById('tipoRelatorio').value;

    const equipesSelecionadas = Array.from(
        document.querySelectorAll('input[name="equipes"]:checked')
    ).map((elemento) => elemento.value);

    const forcarReenvio = statusRelatorioAtual === RELATORIO_STATUS.SUCESSO_TOTAL && reenvioConfirmado;
    const formData = gerarFormData(
        fileAtual,
        ignorarSabados,
        debugMode,
        equipesSelecionadas,
        tipoRelatorio,
        forcarReenvio,
    );

    atualizarBarraProgresso('25%');
    console.info('📦 Enviando arquivo:', arquivoSelecionado);

    try {
        const taskId = await enviarCSV(formData);
        mostrarLogs([{ type: 'info', message: '📦 Processamento agendado. Aguardando resultado...' }]);

        const resultado = await acompanharTarefa(taskId);

        mostrarLogs(resultado.log);
        atualizarEstatisticas(resultado.stats);
        atualizarBarraProgresso('100%');

        if (debugMode && resultado.debug) {
            mostrarDebug(resultado.debug);
        }

        if (fileNameLabel && arquivoSelecionado) {
            fileNameLabel.textContent = `Arquivo mantido: ${arquivoSelecionado.name}`;
            fileNameLabel.style.display = 'block';
        }
    } catch (error) {
        console.error('⚠️ Erro durante envio ou processamento:', error);
        alert(error.message || 'Erro de rede ou servidor.');
    } finally {
        if (sendButton) {
            sendButton.disabled = false;
        }
    }
}

function atualizarAlertaRelatorio(status, pendencias, nome, reenvioAtivo) {
    if (!relatorioStatusBox) {
        return false;
    }

    relatorioStatusBox.classList.add('hidden');
    relatorioStatusBox.classList.remove('report-alert--warning', 'report-alert--info');
    relatorioStatusBox.innerHTML = '';

    if (!status || status === RELATORIO_STATUS.NOVO) {
        return false;
    }

    relatorioStatusBox.classList.remove('hidden');

    if (status === RELATORIO_STATUS.SUCESSO_TOTAL) {
        relatorioStatusBox.classList.add('report-alert--warning');
        if (reenvioAtivo) {
            relatorioStatusBox.innerHTML = `<p>Reenvio liberado para <strong>${nome}</strong>. As mensagens já enviadas poderão ser reenviadas.</p>`;
            return false;
        }
        relatorioStatusBox.innerHTML = `
            <p>Esse relatório já foi enviado anteriormente. Se você refizer o envio, poderá enviar mensagens que já foram enviadas antes.</p>
            <button type="button" id="liberarReenvioBtn" class="report-alert__action">Quero reenviar mesmo assim</button>
        `;
        const botao = document.getElementById('liberarReenvioBtn');
        if (botao) {
            botao.addEventListener('click', abrirModalReenvio, { once: true });
        }
        return true;
    }

    if (status === RELATORIO_STATUS.PARCIAL) {
        relatorioStatusBox.classList.add('report-alert--info');
        const lista = Array.isArray(pendencias) && pendencias.length
            ? `<ul>${pendencias.map((item) => `<li>${item}</li>`).join('')}</ul>`
            : '<p>As pendências foram resolvidas.</p>';
        relatorioStatusBox.innerHTML = `
            <p>Parte desse relatório já foi enviada. Serão enviadas apenas as mensagens que ainda não foram registradas, para as equipes abaixo:</p>
            ${lista}
        `;
        return false;
    }

    return false;
}

function limparAlertaRelatorio() {
    if (!relatorioStatusBox) {
        return;
    }
    relatorioStatusBox.classList.add('hidden');
    relatorioStatusBox.classList.remove('report-alert--warning', 'report-alert--info');
    relatorioStatusBox.innerHTML = '';
}

function abrirModalReenvio() {
    if (!modalOverlay || !modalReenvio) {
        return;
    }
    modalOverlay.classList.remove('hidden');
    modalReenvio.classList.remove('hidden');
}

function fecharModalReenvio() {
    if (!modalOverlay || !modalReenvio) {
        return;
    }
    modalOverlay.classList.add('hidden');
    modalReenvio.classList.add('hidden');
}

function confirmarReenvio() {
    reenvioConfirmado = true;
    fecharModalReenvio();
    const bloquear = atualizarAlertaRelatorio(
        statusRelatorioAtual,
        pendenciasRelatorio,
        nomeRelatorioAtual || (arquivoSelecionado?.name ?? ''),
        true,
    );
    if (sendButton && !bloquear) {
        sendButton.disabled = false;
    }
}

async function acompanharTarefa(taskId) {
    while (true) {
        const data = await obterStatus(taskId);
        if (data.status === 'done') {
            return data;
        }
        if (data.status === 'error') {
            throw new Error(data.error || 'Erro no processamento');
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
    }
}
