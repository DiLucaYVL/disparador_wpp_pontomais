let graficoPorEquipe;
let dados = [];
let resumoAtual = { total: 0, sucessos: 0, erros: 0 };
let equipesDisponiveis = [];

const CHECKBOX_ALL_VALUE = '__all__';

function closeAllDropdowns(except) {
  document.querySelectorAll('.custom-dropdown.multiselect.open').forEach((dropdown) => {
    if (dropdown !== except) {
      dropdown.classList.remove('open');
      const header = dropdown.querySelector('.dropdown-header');
      if (header) {
        header.setAttribute('aria-expanded', 'false');
      }
    }
  });
}

function setupMultiselectDropdown(dropdownId) {
  const dropdown = document.getElementById(dropdownId);
  if (!dropdown || dropdown.dataset.enhanced === 'true') {
    return;
  }

  const header = dropdown.querySelector('.dropdown-header');
  if (header) {
    header.setAttribute('aria-expanded', 'false');
    header.addEventListener('click', (event) => {
      event.stopPropagation();
      const isOpen = dropdown.classList.contains('open');
      closeAllDropdowns(dropdown);
      if (isOpen) {
        dropdown.classList.remove('open');
        header.setAttribute('aria-expanded', 'false');
      } else {
        dropdown.classList.add('open');
        header.setAttribute('aria-expanded', 'true');
      }
    });
  }

  dropdown.addEventListener('click', (event) => {
    event.stopPropagation();
  });

  dropdown.dataset.enhanced = 'true';
}

function handleCheckboxGroupChange(event) {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || target.type !== 'checkbox') {
    return;
  }

  const container = target.closest('.checkbox-group');
  if (!container) {
    return;
  }

  const checkboxes = Array.from(container.querySelectorAll('input[type="checkbox"]'));
  const master = checkboxes.find((input) => input.dataset.role === 'all');

  if (target.dataset.role === 'all') {
    const shouldCheckAll = target.checked;
    checkboxes.forEach((input) => {
      if (input !== master) {
        input.checked = false;
      }
    });
    if (master) {
      master.checked = shouldCheckAll;
    }
    atualizarCheckboxLabel(container);
    return;
  }

  if (target.checked && master) {
    master.checked = false;
  } else if (master) {
    const anyChecked = checkboxes.some((input) => input !== master && input.checked);
    if (!anyChecked) {
      master.checked = true;
    }
  }

  atualizarCheckboxLabel(container);
}

function atualizarCheckboxLabel(container) {
  const labelId = container.dataset.labelTarget;
  if (!labelId) {
    return;
  }
  const label = document.getElementById(labelId);
  if (!label) {
    return;
  }

  const defaultLabel = container.dataset.defaultLabel || 'Selecionar';
  const pluralLabel = container.dataset.pluralLabel || 'selecionadas';
  const master = container.querySelector('input[data-role="all"]');
  const selecionados = obterSelecionados(container.id);
  const totalItens = master
    ? container.querySelectorAll('input[type="checkbox"]').length - 1
    : container.querySelectorAll('input[type="checkbox"]').length;

  if ((master && master.checked) || !selecionados.length) {
    label.textContent = defaultLabel;
    return;
  }

  if (totalItens > 0 && selecionados.length === totalItens) {
    label.textContent = defaultLabel;
    return;
  }

  if (selecionados.length <= 2) {
    label.textContent = selecionados.join(', ');
  } else {
    label.textContent = `${selecionados.length} ${pluralLabel}`;
  }
}

function configurarCheckboxGrupo(containerId) {
  const container = document.getElementById(containerId);
  if (!container) {
    return;
  }

  if (container.dataset.enhanced !== 'true') {
    container.addEventListener('change', handleCheckboxGroupChange);
    container.dataset.enhanced = 'true';
  }

  atualizarCheckboxLabel(container);
}

function obterSelecionados(containerId) {
  const container = document.getElementById(containerId);
  if (!container) {
    return [];
  }

  return Array.from(container.querySelectorAll('input[type="checkbox"]:checked'))
    .filter((input) => input.dataset.role !== 'all')
    .map((input) => input.value);
}

function setupCheckboxFilters() {
  configurarCheckboxGrupo('tipoCheckboxes');
  configurarCheckboxGrupo('equipeCheckboxes');
  setupMultiselectDropdown('tipoDropdown');
  setupMultiselectDropdown('equipeDropdown');

  const tipoContainer = document.getElementById('tipoCheckboxes');
  if (tipoContainer) {
    atualizarCheckboxLabel(tipoContainer);
  }
  const equipeContainer = document.getElementById('equipeCheckboxes');
  if (equipeContainer) {
    atualizarCheckboxLabel(equipeContainer);
  }
}

document.addEventListener('click', () => {
  closeAllDropdowns();
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    closeAllDropdowns();
  }
});

async function carregarDados() {
  closeAllDropdowns();
  const loadingIndicator = document.getElementById('loadingIndicator');
  if (loadingIndicator) {
    loadingIndicator.style.display = 'block';
  }

  const params = new URLSearchParams();
  const equipesSelecionadas = obterSelecionados('equipeCheckboxes');
  const tiposSelecionados = obterSelecionados('tipoCheckboxes');
  const inicio = document.getElementById('filtroInicio')?.value ?? '';
  const fim = document.getElementById('filtroFim')?.value ?? '';

  if (equipesSelecionadas.length) {
    equipesSelecionadas.forEach((valor) => params.append('equipes', valor));
  }

  if (tiposSelecionados.length) {
    tiposSelecionados.forEach((valor) => params.append('tipos', valor));
  }

  if (inicio) params.append('inicio', inicio);
  if (fim) params.append('fim', fim);

  const query = params.toString();

  try {
    const url = query ? `/historico/dados?${query}` : '/historico/dados';
    const resp = await fetch(url);
    const data = await resp.json();

    if (!resp.ok || !data.success) {
      throw new Error(data.error || 'Falha ao consultar historico.');
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
    if (loadingIndicator) {
      loadingIndicator.style.display = 'none';
    }
  }
}

function exportarHistorico() {
  closeAllDropdowns();
  const params = new URLSearchParams();
  const equipesSelecionadas = obterSelecionados('equipeCheckboxes');
  const tiposSelecionados = obterSelecionados('tipoCheckboxes');
  const inicio = document.getElementById('filtroInicio')?.value ?? '';
  const fim = document.getElementById('filtroFim')?.value ?? '';

  if (equipesSelecionadas.length) {
    equipesSelecionadas.forEach((valor) => params.append('equipes', valor));
  }

  if (tiposSelecionados.length) {
    tiposSelecionados.forEach((valor) => params.append('tipos', valor));
  }

  if (inicio) params.append('inicio', inicio);
  if (fim) params.append('fim', fim);

  const query = params.toString();
  const url = query ? `/historico/exportar?${query}` : '/historico/exportar';
  window.open(url, '_blank');
}

// Preencher tabela
function preencherTabela(registros) {
  const tbody = document.querySelector('#tabelaEnvios tbody');
  tbody.innerHTML = '';

  const matriz = agruparPorEquipeTipoMotivo(registros);

  if (!matriz.length) {
    const linhaVazia = document.createElement('tr');
    const coluna = document.createElement('td');
    coluna.colSpan = 2;
    coluna.className = 'empty-row';
    coluna.textContent = 'Nenhum envio encontrado para os filtros selecionados.';
    linhaVazia.appendChild(coluna);
    tbody.appendChild(linhaVazia);
    return;
  }

  matriz.forEach((grupo, indice) => {
    const rowId = `grupo-${indice}`;
    const detailRowId = `detail-${rowId}`;

    const tr = document.createElement('tr');
    tr.className = 'matrix-row';
    tr.dataset.rowId = rowId;

    const equipeTd = document.createElement('td');
    equipeTd.className = 'matrix-cell matrix-cell-equipe';

    const equipeWrapper = document.createElement('div');
    equipeWrapper.className = 'matrix-cell-wrapper';

    if (grupo.detalhes.length) {
      const toggleButton = criarToggleButton(detailRowId);
      toggleButton.title = 'Expandir detalhes por pessoa e motivo';
      equipeWrapper.appendChild(toggleButton);
    } else {
      const placeholder = document.createElement('span');
      placeholder.className = 'toggle-placeholder';
      equipeWrapper.appendChild(placeholder);
    }

    const equipeTexto = document.createElement('span');
    equipeTexto.className = 'matrix-text';
    equipeTexto.textContent = grupo.equipe;
    equipeWrapper.appendChild(equipeTexto);

    equipeTd.appendChild(equipeWrapper);
    tr.appendChild(equipeTd);

    const quantidadeTd = document.createElement('td');
    quantidadeTd.className = 'matrix-cell matrix-cell-qty';
    quantidadeTd.textContent = grupo.total.toLocaleString('pt-BR');
    tr.appendChild(quantidadeTd);

    tbody.appendChild(tr);

    if (grupo.detalhes.length) {
      const detailRow = criarDrilldownRow(detailRowId, grupo);
      tbody.appendChild(detailRow);
    }
  });
}

function agruparPorEquipeTipoMotivo(registros) {
  const grupos = new Map();

  registros.forEach((registro) => {
    const equipe = normalizarCampo(registro.equipe);
    const tipo = normalizarCampo(registro.tipo_relatorio || registro.tipo, 'Sem tipo');
    const motivo = normalizarCampo(registro.motivo_envio || registro.motivo, 'Sem motivo');
    const pessoa = normalizarCampo(registro.pessoa, 'Sem identificaÃ§Ã£o');

    if (!grupos.has(equipe)) {
      grupos.set(equipe, {
        equipe,
        total: 0,
        detalhes: new Map(),
      });
    }

    const grupo = grupos.get(equipe);
    grupo.total += 1;

    const chaveDetalhe = `${pessoa}|||${tipo}|||${motivo}`;
    if (!grupo.detalhes.has(chaveDetalhe)) {
      grupo.detalhes.set(chaveDetalhe, {
        pessoa,
        tipo,
        motivo,
        total: 0,
      });
    }
    grupo.detalhes.get(chaveDetalhe).total += 1;
  });

  const lista = Array.from(grupos.values()).map((grupo) => ({
    equipe: grupo.equipe,
    total: grupo.total,
    detalhes: Array.from(grupo.detalhes.values()).sort((a, b) => {
      const ordemPessoa = a.pessoa.localeCompare(b.pessoa, 'pt-BR', { sensitivity: 'base' });
      if (ordemPessoa !== 0) return ordemPessoa;
      const ordemTipo = a.tipo.localeCompare(b.tipo, 'pt-BR', { sensitivity: 'base' });
      if (ordemTipo !== 0) return ordemTipo;
      return a.motivo.localeCompare(b.motivo, 'pt-BR', { sensitivity: 'base' });
    }),
  }));

  lista.sort((a, b) =>
    a.equipe.localeCompare(b.equipe, 'pt-BR', { sensitivity: 'base' })
  );

  return lista;
}

function normalizarCampo(valor, padrao = 'Nao informado') {
  if (typeof valor === 'string') {
    const texto = valor.trim();
    return texto || padrao;
  }

  if (valor === undefined || valor === null) {
    return padrao;
  }

  return String(valor);
}

function criarToggleButton(targetId) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'toggle-button';
  button.setAttribute('aria-expanded', 'false');
  button.setAttribute('aria-controls', targetId);

  const icon = document.createElement('span');
  icon.className = 'toggle-icon';
  icon.textContent = '+';
  button.appendChild(icon);

  button.addEventListener('click', () => {
    const detailRow = document.getElementById(targetId);
    if (!detailRow) {
      return;
    }

    const expanded = button.getAttribute('aria-expanded') === 'true';
    button.setAttribute('aria-expanded', String(!expanded));
    button.classList.toggle('expanded', !expanded);
    icon.textContent = expanded ? '+' : '-';
    detailRow.classList.toggle('hidden', expanded);
  });

  return button;
}

function criarDrilldownRow(detailRowId, grupo) {
  const detailRow = document.createElement('tr');
  detailRow.className = 'detail-row hidden';
  detailRow.id = detailRowId;

  const detailTd = document.createElement('td');
  detailTd.colSpan = 2;

  const card = document.createElement('div');
  card.className = 'drilldown-card';

  const header = document.createElement('div');
  header.className = 'drilldown-header';
  header.textContent = `Detalhes por pessoa e motivo (${grupo.total.toLocaleString('pt-BR')} envios)`;
  card.appendChild(header);

  const table = document.createElement('table');
  table.className = 'drilldown-table';

  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  const pessoaTh = document.createElement('th');
  pessoaTh.textContent = 'Nome';
  const tipoTh = document.createElement('th');
  tipoTh.textContent = 'Tipo de Relatorio';
  const motivoTh = document.createElement('th');
  motivoTh.textContent = 'Motivo';
  const qtdTh = document.createElement('th');
  qtdTh.textContent = 'Quantidade';
  headerRow.appendChild(pessoaTh);
  headerRow.appendChild(tipoTh);
  headerRow.appendChild(motivoTh);
  headerRow.appendChild(qtdTh);
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const body = document.createElement('tbody');
  grupo.detalhes.forEach((detalhe) => {
    const linha = document.createElement('tr');
    const nomeTd = document.createElement('td');
    nomeTd.textContent = detalhe.pessoa;
    const tipoTd = document.createElement('td');
    tipoTd.textContent = detalhe.tipo;
    const motivoTd = document.createElement('td');
    motivoTd.textContent = detalhe.motivo;
    const quantidadeTd = document.createElement('td');
    quantidadeTd.className = 'drilldown-qty-cell';
    quantidadeTd.textContent = detalhe.total.toLocaleString('pt-BR');
    linha.appendChild(nomeTd);
    linha.appendChild(tipoTd);
    linha.appendChild(motivoTd);
    linha.appendChild(quantidadeTd);
    body.appendChild(linha);
  });
  table.appendChild(body);

  card.appendChild(table);
  detailTd.appendChild(card);
  detailRow.appendChild(detailTd);

  return detailRow;
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

// Atualizar filtro de equipes
function atualizarEquipeSelect(equipes) {
  const container = document.getElementById('equipeCheckboxes');
  if (!container) {
    return;
  }

  closeAllDropdowns();

  const previouslySelected = new Set(
    Array.from(container.querySelectorAll('input[type="checkbox"]:checked'))
      .filter((input) => input.dataset.role !== 'all')
      .map((input) => input.value)
  );
  const masterWasChecked = container.querySelector('input[data-role="all"]')?.checked ?? previouslySelected.size === 0;

  container.innerHTML = '';

  if (!equipes || !equipes.length) {
    container.innerHTML = '<span class="checkbox-placeholder">Nenhuma equipe disponivel</span>';
    configurarCheckboxGrupo('equipeCheckboxes');
    return;
  }

  const masterLabel = document.createElement('label');
  masterLabel.className = 'checkbox-item';
  const masterInput = document.createElement('input');
  masterInput.type = 'checkbox';
  masterInput.value = CHECKBOX_ALL_VALUE;
  masterInput.dataset.role = 'all';
  masterInput.checked = masterWasChecked || previouslySelected.size === 0;
  masterLabel.appendChild(masterInput);
  masterLabel.appendChild(document.createTextNode('Todas as equipes'));
  container.appendChild(masterLabel);

  equipes.forEach((equipe) => {
    if (!equipe) {
      return;
    }
    const label = document.createElement('label');
    label.className = 'checkbox-item';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.value = equipe;
    if (!masterInput.checked && previouslySelected.has(equipe)) {
      input.checked = true;
    }
    label.appendChild(input);
    label.appendChild(document.createTextNode(equipe));
    container.appendChild(label);
  });

  if (!previouslySelected.size && !masterWasChecked) {
    masterInput.checked = true;
  }

  configurarCheckboxGrupo('equipeCheckboxes');
}


// Atualizar grafico por equipes
function atualizarGraficoEquipes(dados) {
  const ctx = document.getElementById('graficoEquipes').getContext('2d');

  const equipeCounts = {};
  dados.forEach((item) => {
    const equipeNome = item.equipe || 'Nao informado';
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
  setupCheckboxFilters();
  const aplicar = document.getElementById('aplicarFiltros');
  if (aplicar) {
    aplicar.addEventListener('click', carregarDados);
  }

  const exportar = document.getElementById('exportarExcel');
  if (exportar) {
    exportar.addEventListener('click', exportarHistorico);
  }

  carregarDados();
});




