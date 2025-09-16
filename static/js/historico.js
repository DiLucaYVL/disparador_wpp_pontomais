let graficoPorEquipe;
let dados = [];
let resumoAtual = { total: 0, sucessos: 0, erros: 0 };
let equipesDisponiveis = [];

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

    if (!resp.ok || !data.success) {
      throw new Error(data.error || 'Falha ao consultar histórico.');
    }

    dados = Array.isArray(data.dados) ? data.dados : [];
    resumoAtual = data.resumo || {
      total: dados.length,
      sucessos: dados.filter((d) => (d.status || '').toLowerCase() === 'sucesso').length,
      erros: dados.filter((d) => (d.status || '').toLowerCase() === 'erro').length,
    };
    equipesDisponiveis = Array.isArray(data.equipes) ? data.equipes : [];

    preencherTabela(dados);
    atualizarEquipeSelect(equipesDisponiveis);
    atualizarContadores(resumoAtual);
    atualizarGraficoEquipes(dados);
  } catch (error) {
    console.error('Erro ao carregar dados:', error);
    dados = [];
    resumoAtual = { total: 0, sucessos: 0, erros: 0 };
    preencherTabela([]);
    atualizarContadores(resumoAtual);
    atualizarGraficoEquipes([]);
  } finally {
    loadingIndicator.style.display = 'none';
  }
}

// Preencher tabela
function preencherTabela(dados) {
  const tbody = document.querySelector('#tabelaEnvios tbody');
  tbody.innerHTML = '';

  if (!dados.length) {
    const linhaVazia = document.createElement('tr');
    const coluna = document.createElement('td');
    coluna.colSpan = 6;
    coluna.className = 'empty-row';
    coluna.textContent = 'Nenhum envio encontrado para os filtros selecionados.';
    linhaVazia.appendChild(coluna);
    tbody.appendChild(linhaVazia);
    return;
  }

  dados.forEach((row) => {
    const tr = document.createElement('tr');

    const dataTd = document.createElement('td');
    dataTd.textContent = formatarData(row.data_envio);
    tr.appendChild(dataTd);

    const equipeTd = document.createElement('td');
    equipeTd.textContent = row.equipe || 'N/A';
    tr.appendChild(equipeTd);

    const tipoTd = document.createElement('td');
    tipoTd.textContent = row.tipo_relatorio || 'N/A';
    tr.appendChild(tipoTd);

    const pessoaTd = document.createElement('td');
    pessoaTd.textContent = row.pessoa || 'N/A';
    tr.appendChild(pessoaTd);

    const motivoTd = document.createElement('td');
    motivoTd.textContent = row.motivo_envio || 'N/A';
    tr.appendChild(motivoTd);

    const statusTd = document.createElement('td');
    const statusBadge = document.createElement('span');
    const statusNormalizado = (row.status || '').toLowerCase();
    const statusClass = statusNormalizado === 'sucesso' ? 'status-success' : 'status-error';
    const statusTexto = statusNormalizado === 'sucesso' ? 'sucesso' : (row.status || 'indefinido');
    const statusIcon = statusNormalizado === 'sucesso' ? '✅' : '⚠️';
    statusBadge.className = `status-badge ${statusClass}`;
    statusBadge.textContent = `${statusIcon} ${statusTexto}`;
    statusTd.appendChild(statusBadge);
    tr.appendChild(statusTd);

    tbody.appendChild(tr);
  });
}

function formatarData(dataTexto) {
  if (!dataTexto) {
    return 'N/A';
  }

  // Tenta interpretar ISO ou formato americano
  const tentativaIso = new Date(dataTexto);
  if (!Number.isNaN(tentativaIso.getTime())) {
    return tentativaIso.toLocaleString('pt-BR', {
      dateStyle: 'short',
      timeStyle: 'short',
    });
  }

  const partes = dataTexto.split(' ');
  if (partes.length >= 2) {
    const [dataParte, horaParte] = partes;
    const [dia, mes, ano] = dataParte.split('/');
    if (dia && mes && ano) {
      return `${dia.padStart(2, '0')}/${mes.padStart(2, '0')}/${ano} ${horaParte || ''}`.trim();
    }
  }

  return dataTexto;
}

// Atualizar contadores
function atualizarContadores(resumo) {
  const total = resumo?.total ?? 0;
  const sucessos = resumo?.sucessos ?? 0;
  const erros = resumo?.erros ?? 0;

  document.getElementById('totalCounter').textContent = total;
  document.getElementById('successTotal').textContent = sucessos;
  document.getElementById('errorTotal').textContent = erros;
}

// Atualizar dropdown de equipes
function atualizarEquipeSelect(equipes) {
  const equipeContent = document.getElementById('equipeDropdownContent');
  const selectedValue = document.getElementById('filtroEquipe').value;
  let selectedLabel = 'Todas as equipes';
  let selecionadoExiste = false;

  equipeContent.innerHTML = '';

  const criarItem = (valor, texto) => {
    const item = document.createElement('div');
    item.className = 'dropdown-item';
    item.dataset.value = valor;
    item.textContent = texto;
    if (valor === selectedValue) {
      item.classList.add('selected');
      selectedLabel = texto;
      selecionadoExiste = true;
    }
    equipeContent.appendChild(item);
  };

  criarItem('', 'Todas as equipes');
  (equipes || []).forEach((equipe) => {
    if (!equipe) {
      return;
    }
    criarItem(equipe, equipe);
  });

  if (!selecionadoExiste) {
    document.getElementById('filtroEquipe').value = '';
    selectedLabel = 'Todas as equipes';
    equipeContent.firstChild.classList.add('selected');
  }

  document.getElementById('equipeSelectedText').textContent = selectedLabel;
}

// Atualizar gráfico por equipes
function atualizarGraficoEquipes(dados) {
  const ctx = document.getElementById('graficoEquipes').getContext('2d');

  const equipeCounts = {};
  dados.forEach((item) => {
    const equipeNome = item.equipe || 'Não informado';
    const status = (item.status || '').toLowerCase();
    if (!equipeCounts[equipeNome]) {
      equipeCounts[equipeNome] = { sucesso: 0, erro: 0 };
    }
    if (status === 'sucesso') {
      equipeCounts[equipeNome].sucesso += 1;
    } else if (status === 'erro') {
      equipeCounts[equipeNome].erro += 1;
    }
  });

  const equipes = Object.keys(equipeCounts).sort();
  const sucessos = equipes.map((eq) => equipeCounts[eq].sucesso || 0);
  const erros = equipes.map((eq) => equipeCounts[eq].erro || 0);

  if (graficoPorEquipe) {
    graficoPorEquipe.destroy();
    graficoPorEquipe = null;
  }

  if (!equipes.length) {
    return;
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

