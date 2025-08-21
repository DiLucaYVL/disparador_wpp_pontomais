export function mostrarLogs(logs) {
    const logContainer = document.getElementById('logContainer');
    logContainer.innerHTML = "";
    const icones = { success: "✅", error: "❌", warning: "⚠️", info: "ℹ️" };

    logs.forEach(entry => {
        const div = document.createElement('div');
        div.classList.add('log-entry', `log-${entry.type}`);
        div.textContent = `${icones[entry.type] || ''} ${entry.message}`;
        logContainer.appendChild(div);
    });
}

export function atualizarEstatisticas(stats) {
    document.getElementById('totalMessages').textContent = stats.total;
    document.getElementById('totalTeams').textContent = stats.equipes;
    document.getElementById('successCount').textContent = stats.sucesso;
    document.getElementById('errorCount').textContent = stats.erro;
}

export function mostrarDebug(data) {
    const debugPanel = document.getElementById('debugPanel');
    const debugContent = document.getElementById('debugContent');
    debugContent.textContent = JSON.stringify(JSON.parse(data), null, 2);
    debugPanel.style.display = "block";
}

export function atualizarBarraProgresso(percent) {
    document.getElementById("progressBar").style.display = "block";
    document.getElementById("progressFill").style.width = percent;
}

window.mostrarLogs = mostrarLogs;
