let graficoPorEquipe;
let dados = [];

// Configurar dropdowns
function setupDropdowns() {
  // Dropdown de Equipe
  const equipeHeader = document.getElementById('equipeDropdownHeader');
  const equipeContent = document.getElementById('equipeDropdownContent');
  const equipeSelected = document.getElementById('equipeSelectedText');
  const equipeInput = document.getElementById('filtroEquipe');

  equipeHeader.addEventListener('click', () => {
    equipeHeader.classList.toggle('active');
    equipeContent.classList.toggle('show');
  });

  equipeContent.addEventListener('click', (e) => {
    if (e.target.classList.contains('dropdown-item')) {
      document
        .querySelectorAll('#equipeDropdownContent .dropdown-item')
        .forEach((item) => {
          item.classList.remove('selected');
        });
      e.target.classList.add('selected');
      equipeSelected.textContent = e.target.textContent;
      equipeInput.value = e.target.getAttribute('data-value');
      equipeHeader.classList.remove('active');
      equipeContent.classList.remove('show');
    }
  });

  // Dropdown de Tipo
  const tipoHeader = document.getElementById('tipoDropdownHeader');
  const tipoContent = document.getElementById('tipoDropdownContent');
  const tipoSelected = document.getElementById('tipoSelectedText');
  const tipoInput = document.getElementById('filtroTipo');

  tipoHeader.addEventListener('click', () => {
    tipoHeader.classList.toggle('active');
    tipoContent.classList.toggle('show');
  });

  tipoContent.addEventListener('click', (e) => {
    if (e.target.classList.contains('dropdown-item')) {
      document
        .querySelectorAll('#tipoDropdownContent .dropdown-item')
        .forEach((item) => {
          item.classList.remove('selected');
        });
      e.target.classList.add('selected');
      tipoSelected.textContent = e.target.textContent;
      tipoInput.value = e.target.getAttribute('data-value');
      tipoHeader.classList.remove('active');
      tipoContent.classList.remove('show');
    }
  });

  // Fechar dropdowns ao clicar fora
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.custom-dropdown')) {
      document.querySelectorAll('.dropdown-header').forEach((header) => {
        header.classList.remove('active');
      });
      document.querySelectorAll('.dropdown-content').forEach((content) => {
        content.classList.remove('show');
      });
    }
  });
}

// Carregar dados
async function carregarDados() {
  const loadingIndicator = document.getElementById('loadingIndicator');
  loadingIndicator.style.display = 'block';

  const params = new URLSearchParams();
  const equipe = document.getElementById('filtroEquipe').value;
  const tipo = document.getElementById('filtroTipo').value;
  const inicio = document.getElementById('filtroInicio').value;
  const fim = document.getElementById('filtroFim').value;

  if (equipe) params.append('equipe', equipe);
  if (tipo) params.append('tipo', tipo);
  if (inicio) params.append('inicio', inicio);
  if (fim) params.append('fim', fim);

  try {
    const resp = await fetch(`/historico/dados?${params.toString()}`);
    const data = await resp.json();
    if (data.success) {
      dados = data.dados;
      preencherTabela(dados);
      atualizarEquipeSelect(dados);
      atualizarContadores(dados);
      atualizarGraficoEquipes(dados);
    }
  } catch (error) {
    console.error('Erro ao carregar dados:', error);
  } finally {
    loadingIndicator.style.display = 'none';
  }
}

// Preencher tabela
function preencherTabela(dados) {
  const tbody = document.querySelector('#tabelaEnvios tbody');
  tbody.innerHTML = '';

  dados.forEach((row) => {
    const tr = document.createElement('tr');
    const dataFormatada = new Date(row.data_envio).toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
    const statusClass = row.status === 'sucesso' ? 'status-success' : 'status-error';
    const statusIcon = row.status === 'sucesso' ? '✅' : '❌';
    tr.innerHTML = `
      <td>${dataFormatada}</td>
      <td>${row.equipe}</td>
      <td>${row.tipo_relatorio}</td>
      <td><span class="status-badge ${statusClass}">${statusIcon} ${row.status}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// Atualizar contadores
function atualizarContadores(dados) {

  const total = dados.length;
  const sucessos = dados.filter((d) => d.status === 'sucesso').length;
  const erros = dados.filter((d) => d.status === 'erro').length;

  document.getElementById('totalCounter').textContent = total;
  document.getElementById('successTotal').textContent = sucessos;
  document.getElementById('errorTotal').textContent = erros;
}

// Atualizar dropdown de equipes
function atualizarEquipeSelect(dados) {
  const equipes = [...new Set(dados.map((d) => d.equipe))].sort();
  const equipeContent = document.getElementById('equipeDropdownContent');
  const currentValue = document.getElementById('filtroEquipe').value;

  // Manter opção "Todas"
  equipeContent.innerHTML = '<div class="dropdown-item selected" data-value="">Todas as equipes</div>';

  equipes.forEach((equipe) => {
    const item = document.createElement('div');
    item.className = 'dropdown-item';
    item.setAttribute('data-value', equipe);
    item.textContent = equipe;
    if (equipe === currentValue) {
      item.classList.add('selected');
      document.getElementById('equipeSelectedText').textContent = equipe;
    }
    equipeContent.appendChild(item);
  });
}

// Atualizar gráfico por equipes
function atualizarGraficoEquipes(dados) {
  const ctx = document.getElementById('graficoEquipes').getContext('2d');

  const equipeCounts = {};
  dados.forEach((item) => {
    if (!equipeCounts[item.equipe]) {
      equipeCounts[item.equipe] = { sucesso: 0, erro: 0 };
    }
    equipeCounts[item.equipe][item.status]++;
  });

  const equipes = Object.keys(equipeCounts).sort();
  const sucessos = equipes.map((eq) => equipeCounts[eq].sucesso || 0);
  const erros = equipes.map((eq) => equipeCounts[eq].erro || 0);

  if (graficoPorEquipe) {
    graficoPorEquipe.destroy();
  }

  graficoPorEquipe = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: equipes,
      datasets: [
        {
          label: 'Sucessos',
          data: sucessos,
          backgroundColor: 'rgba(46, 204, 113, 0.8)',
          borderColor: 'rgba(46, 204, 113, 1)',
          borderWidth: 2,
          borderRadius: 8,
        },
        {
          label: 'Falhas',
          data: erros,
          backgroundColor: 'rgba(231, 76, 60, 0.8)',
          borderColor: 'rgba(231, 76, 60, 1)',
          borderWidth: 2,
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: 'Envios por Equipe (Sucessos vs Falhas)',
          font: { size: 16, weight: 'bold' },
        },
        legend: {
          position: 'top',
          labels: {
            usePointStyle: true,
            font: { size: 12, weight: '600' },
          },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { stepSize: 1 },
          grid: { color: 'rgba(0, 0, 0, 0.1)' },
        },
        x: {
          grid: { display: false },
          ticks: { maxRotation: 45 },
        },
      },
      interaction: { intersect: false, mode: 'index' },
      animation: { duration: 1000, easing: 'easeOutQuart' },
    },
  });
}

// Inicializar
document.addEventListener('DOMContentLoaded', () => {
  setupDropdowns();
  document
    .getElementById('aplicarFiltros')
    .addEventListener('click', carregarDados);
  carregarDados();
});

