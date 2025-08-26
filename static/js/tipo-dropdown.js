// JavaScript para o dropdown customizado de tipo de relatório
document.addEventListener('DOMContentLoaded', function() {
    const tipoDropdownHeader = document.getElementById('tipoDropdownHeader');
    const tipoDropdownContent = document.getElementById('tipoDropdownContent');
    const tipoSelectedText = document.getElementById('tipoSelectedText');
    const tipoRelatorioInput = document.getElementById('tipoRelatorio');
    const tipoDropdownItems = document.querySelectorAll('.tipo-dropdown-item');
    const ignorarSabadosCheckbox = document.getElementById('ignorarSabados');
    const ignorarSabadosLabel = document.querySelector('label[for="ignorarSabados"]');

    // Toggle dropdown
    tipoDropdownHeader.addEventListener('click', function() {
        tipoDropdownHeader.classList.toggle('active');
        tipoDropdownContent.classList.toggle('show');
    });

    // 🔒 Travar upload até selecionar tipo
    const csvFileInput = document.getElementById('csvFile');
    const csvFileLabel = document.querySelector('label[for="csvFile"]');

    function atualizarStatusUpload() {
        const liberado = tipoRelatorioInput.value !== "";

        csvFileInput.disabled = !liberado;

        if (liberado) {
            csvFileLabel.classList.remove('upload-disabled');
        } else {
            csvFileLabel.classList.add('upload-disabled');
        }
    }

    // Inicialmente desativa o input
    atualizarStatusUpload();

    // Selecionar item
    tipoDropdownItems.forEach(item => {
        item.addEventListener('click', function() {
            const value = this.getAttribute('data-value');
            const icon = this.querySelector('.tipo-icon').textContent;
            const text = this.querySelector('.tipo-text').textContent;

            // Atualizar texto selecionado
            tipoSelectedText.textContent = `${icon} ${text}`;
            tipoSelectedText.classList.remove('placeholder-text');

            // Atualizar input hidden
            tipoRelatorioInput.value = value;

            // Remover classe selected de todos os itens
            tipoDropdownItems.forEach(i => i.classList.remove('selected'));

            // Adicionar classe selected ao item clicado
            this.classList.add('selected');

            // Fechar dropdown
            tipoDropdownHeader.classList.remove('active');
            tipoDropdownContent.classList.remove('show');

            // Habilitar upload
            atualizarStatusUpload();

            // Desabilitar checkbox de sábados para Assinaturas
            if (value === 'Assinaturas') {
                ignorarSabadosCheckbox.disabled = true;
                ignorarSabadosLabel.classList.add('upload-disabled');
            } else {
                ignorarSabadosCheckbox.disabled = false;
                ignorarSabadosLabel.classList.remove('upload-disabled');
            }
        });
    });

    // Fechar dropdown ao clicar fora
    document.addEventListener('click', function(event) {
        if (!event.target.closest('.tipo-dropdown-container')) {
            tipoDropdownHeader.classList.remove('active');
            tipoDropdownContent.classList.remove('show');
        }
    });

    // ✅ Inicialmente não selecionar nada
    tipoDropdownItems.forEach(i => i.classList.remove('selected'));
    tipoRelatorioInput.value = '';
    tipoSelectedText.classList.add('placeholder-text');
});
