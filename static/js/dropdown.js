export function carregarDropdownEquipes(equipes) {
    const dropdownList = document.getElementById('dropdownList');
    const selectedCount = document.getElementById('selectedCount');
    const selectAllCheckbox = document.getElementById('selectAllLojas');
    const searchInput = document.getElementById('searchLojas');
    const dropdownHeader = document.getElementById('dropdownHeader');
    const dropdownContent = document.getElementById('dropdownContent');

    if (!dropdownList || !selectedCount || !selectAllCheckbox || !searchInput || !dropdownHeader || !dropdownContent) {
        console.error("Um ou mais elementos do dropdown não foram encontrados.");
        return;
    }

    // 1. Remove listeners antigos usando uma propriedade customizada
    if (selectAllCheckbox._boundHandler) {
        selectAllCheckbox.removeEventListener('change', selectAllCheckbox._boundHandler);
    }
    if (searchInput._boundHandler) {
        searchInput.removeEventListener('input', searchInput._boundHandler);
    }
    if (dropdownHeader._boundHandler) {
        dropdownHeader.removeEventListener('click', dropdownHeader._boundHandler);
    }

    // 2. Limpa a lista de equipes para evitar duplicatas
    dropdownList.innerHTML = '';

    // 3. Popula a lista com as novas equipes
    equipes.forEach(equipe => {
        const dropdownItem = document.createElement('div');
        dropdownItem.className = 'dropdown-item';
        dropdownItem.innerHTML = `
            <input type="checkbox" name="equipes" value="${equipe}" checked />
            <label>${equipe}</label>
        `;
        dropdownList.appendChild(dropdownItem);
    });

    const allCheckboxes = dropdownList.querySelectorAll('input[type="checkbox"]');
    const allDropdownItems = dropdownList.querySelectorAll('.dropdown-item');

    // 4. Função centralizada para atualizar tudo (contador e checkbox "Selecionar Todos")
    function atualizarStatus() {
        const visiveis = Array.from(allCheckboxes).filter(cb => {
            return !cb.closest('.dropdown-item').classList.contains('hidden');
        });

        const selecionadasVisiveis = visiveis.filter(cb => cb.checked).length;
        const totalVisiveis = visiveis.length;

        // Atualiza o texto do contador
        if (totalVisiveis > 0 && selecionadasVisiveis === totalVisiveis) {
            selectedCount.textContent = `Todas as lojas (${totalVisiveis})`;
        } else if (selecionadasVisiveis === 0) {
            selectedCount.textContent = 'Nenhuma loja selecionada';
        } else {
            selectedCount.textContent = `${selecionadasVisiveis} de ${totalVisiveis} lojas`;
        }

        // Atualiza o estado do checkbox "Selecionar Todos"
        if (totalVisiveis > 0 && selecionadasVisiveis === totalVisiveis) {
            selectAllCheckbox.checked = true;
            selectAllCheckbox.indeterminate = false;
        } else if (selecionadasVisiveis > 0) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = true;
        } else {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
        }
    }

    // 5. Configura os eventos com referências corretas

    // Evento para "Selecionar Todos"
    const selectAllHandler = () => {
        const visiveis = Array.from(allCheckboxes).filter(cb => {
            return !cb.closest('.dropdown-item').classList.contains('hidden');
        });
        visiveis.forEach(cb => cb.checked = selectAllCheckbox.checked);
        atualizarStatus();
    };
    selectAllCheckbox._boundHandler = selectAllHandler;
    selectAllCheckbox.addEventListener('change', selectAllHandler);

    // Evento para cada checkbox de loja
    allCheckboxes.forEach(cb => {
        cb.addEventListener('change', atualizarStatus);
    });

    // Permitir clique na linha inteira para selecionar a loja
    allDropdownItems.forEach(item => {
        item.addEventListener('click', (e) => {
            if (e.target.tagName === 'INPUT') {
                return;
            }
            const checkbox = item.querySelector('input[type="checkbox"]');
            checkbox.checked = !checkbox.checked;
            atualizarStatus();
        });
    });

    // Evento para a busca
    const searchHandler = function () {
        const termo = this.value.toLowerCase();
        allCheckboxes.forEach(cb => {
            const item = cb.closest('.dropdown-item');
            const label = item.querySelector('label').textContent.toLowerCase();
            item.classList.toggle('hidden', !label.includes(termo));
        });
        atualizarStatus(); // Essencial para recalcular após o filtro
    };
    searchInput._boundHandler = searchHandler;
    searchInput.addEventListener('input', searchHandler);

    // Evento para abrir/fechar o dropdown
    const dropdownHandler = () => {
        dropdownHeader.classList.toggle('active');
        dropdownContent.classList.toggle('show');
    };
    dropdownHeader._boundHandler = dropdownHandler;
    dropdownHeader.addEventListener('click', dropdownHandler);

    // Evento para fechar o dropdown ao clicar fora
    document.addEventListener('click', (e) => {
        if (!dropdownHeader.contains(e.target) && !dropdownContent.contains(e.target)) {
            dropdownHeader.classList.remove('active');
            dropdownContent.classList.remove('show');
        }
    });

    // 6. Estado inicial
    atualizarStatus();
}