async function carregarDados() {
  const params = new URLSearchParams();
  const equipe = document.getElementById('filtroEquipe').value;
  const tipo = document.getElementById('filtroTipo').value;
  const inicio = document.getElementById('filtroInicio').value;
  const fim = document.getElementById('filtroFim').value;
  if (equipe) params.append('equipe', equipe);
  if (tipo) params.append('tipo', tipo);
  if (inicio) params.append('inicio', inicio);
  if (fim) params.append('fim', fim);
  const resp = await fetch(`/historico/dados?${params.toString()}`);
  const data = await resp.json();
  if (!data.success) return;
  preencherTabela(data.dados);
  atualizarEquipeSelect(data.dados);
  atualizarGrafico(data.dados);
}

function preencherTabela(dados) {
  const tbody = document.querySelector('#tabelaEnvios tbody');
  tbody.innerHTML = '';
  for (const row of dados) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${row.data_envio}</td><td>${row.equipe}</td><td>${row.tipo_relatorio}</td><td>${row.status}</td>`;
    tbody.appendChild(tr);
  }
}

let grafico;
function atualizarGrafico(dados) {
  const ctx = document.getElementById('graficoStatus').getContext('2d');
  const contagem = dados.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1;
    return acc;
  }, {});
  const labels = Object.keys(contagem);
  const valores = Object.values(contagem);
  if (grafico) grafico.destroy();
  grafico = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Envios',
        data: valores,
        backgroundColor: '#4CAF50'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false
    }
  });
}

function atualizarEquipeSelect(dados) {
  const select = document.getElementById('filtroEquipe');
  const equipes = [...new Set(dados.map((d) => d.equipe))].sort();
  const atual = select.value;
  select.innerHTML = '<option value="">Todas</option>';
  for (const eq of equipes) {
    const opt = document.createElement('option');
    opt.value = eq;
    opt.textContent = eq;
    if (eq === atual) opt.selected = true;
    select.appendChild(opt);
  }
}

document.getElementById('aplicarFiltros').addEventListener('click', carregarDados);
window.addEventListener('load', carregarDados);
