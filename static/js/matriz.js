const numberFormatter = new Intl.NumberFormat('pt-BR');

function criarCelula(conteudo, classe = '') {
    const td = document.createElement('td');
    if (classe) {
        td.className = classe;
    }
    if (conteudo instanceof Node) {
        td.appendChild(conteudo);
    } else {
        td.textContent = conteudo;
    }
    return td;
}

function criarToggleButton(drillRow) {
    const botao = document.createElement('button');
    botao.type = 'button';
    botao.className = 'matrix-toggle-btn';
    botao.setAttribute('aria-expanded', 'false');
    botao.setAttribute('title', 'Exibir detalhes por pessoa');
    botao.innerHTML = '▸';

    botao.addEventListener('click', () => {
        const estaOculto = drillRow.classList.contains('hidden');
        if (estaOculto) {
            drillRow.classList.remove('hidden');
            botao.setAttribute('aria-expanded', 'true');
            botao.innerHTML = '▾';
        } else {
            drillRow.classList.add('hidden');
            botao.setAttribute('aria-expanded', 'false');
            botao.innerHTML = '▸';
        }
    });

    return botao;
}

function criarTabelaDetalhes(item) {
    const detalhes = Array.isArray(item.detalhes) ? item.detalhes : [];
    const wrapper = document.createElement('div');
    wrapper.className = 'drilldown-wrapper';

    const titulo = document.createElement('div');
    titulo.className = 'drilldown-title';
    titulo.innerHTML = '👤 Detalhes por pessoa';
    wrapper.appendChild(titulo);

    if (!detalhes.length) {
        const vazio = document.createElement('div');
        vazio.className = 'drilldown-empty';
        vazio.textContent = 'Nenhum detalhe disponível para esta combinação.';
        wrapper.appendChild(vazio);
        return wrapper;
    }

    const tabela = document.createElement('table');
    tabela.className = 'drilldown-table';

    const thead = document.createElement('thead');
    thead.innerHTML = '<tr><th>Nome</th><th class="matrix-col-qtd">Qtd</th></tr>';
    tabela.appendChild(thead);

    const tbody = document.createElement('tbody');
    const ordenado = [...detalhes].sort((a, b) => {
        if (b.qtd === a.qtd) {
            return a.nome.localeCompare(b.nome, 'pt-BR');
        }
        return b.qtd - a.qtd;
    });

    ordenado.forEach((detalhe) => {
        const linha = document.createElement('tr');
        linha.appendChild(criarCelula(detalhe.nome));
        linha.appendChild(criarCelula(numberFormatter.format(detalhe.qtd), 'matrix-col-qtd'));
        tbody.appendChild(linha);
    });

    tabela.appendChild(tbody);
    wrapper.appendChild(tabela);
    return wrapper;
}

export function atualizarResumoMatriz(resumo) {
    const container = document.getElementById('matrixContainer');
    if (!container) {
        console.warn('Container da matriz não encontrado.');
        return;
    }

    container.innerHTML = '';

    if (!Array.isArray(resumo) || resumo.length === 0) {
        const vazio = document.createElement('div');
        vazio.className = 'matrix-empty';
        vazio.textContent = 'Nenhum dado disponível. Envie um arquivo CSV para gerar o resumo.';
        container.appendChild(vazio);
        return;
    }

    const tabela = document.createElement('table');
    tabela.className = 'matrix-table';

    const thead = document.createElement('thead');
    thead.innerHTML = `
        <tr>
            <th class="matrix-col-toggle" scope="col"></th>
            <th scope="col">Equipe</th>
            <th scope="col">Tipo de Relatório</th>
            <th scope="col">Motivo</th>
            <th class="matrix-col-qtd" scope="col">Qtd</th>
        </tr>
    `;
    tabela.appendChild(thead);

    const tbody = document.createElement('tbody');
    const dadosOrdenados = [...resumo].sort((a, b) => {
        if (a.equipe === b.equipe) {
            return a.motivo.localeCompare(b.motivo, 'pt-BR');
        }
        return a.equipe.localeCompare(b.equipe, 'pt-BR');
    });

    dadosOrdenados.forEach((item, indice) => {
        const linha = document.createElement('tr');
        linha.className = 'matrix-row';
        const chave = `${indice}-${item.equipe}-${item.tipo_relatorio}-${item.motivo}`;
        linha.dataset.key = chave;

        const drillRow = document.createElement('tr');
        drillRow.className = 'matrix-drilldown hidden';
        drillRow.dataset.parentKey = chave;

        const celulaToggle = document.createElement('td');
        celulaToggle.className = 'matrix-col-toggle';
        const possuiDetalhes = Array.isArray(item.detalhes) && item.detalhes.length > 0;
        if (possuiDetalhes) {
            const botao = criarToggleButton(drillRow);
            celulaToggle.appendChild(botao);
        } else {
            const placeholder = document.createElement('span');
            placeholder.className = 'matrix-toggle-placeholder';
            placeholder.textContent = '—';
            celulaToggle.appendChild(placeholder);
        }
        linha.appendChild(celulaToggle);

        linha.appendChild(criarCelula(item.equipe));
        linha.appendChild(criarCelula(item.tipo_relatorio));
        linha.appendChild(criarCelula(item.motivo));
        linha.appendChild(criarCelula(numberFormatter.format(item.qtd), 'matrix-col-qtd'));

        const drillCell = document.createElement('td');
        drillCell.colSpan = 5;
        drillCell.appendChild(criarTabelaDetalhes(item));
        drillRow.appendChild(drillCell);

        tbody.appendChild(linha);
        tbody.appendChild(drillRow);
    });

    tabela.appendChild(tbody);
    container.appendChild(tabela);
}
