export function gerarFormData(
    file,
    ignorarSabados,
    debugMode,
    equipesSelecionadas,
    tipoRelatorio,
    forcarReenvio = false,
    apenasGestor = false,
    incluirDuplicadas = false,
    incluirFeriados = true,
) {
    const formData = new FormData();
    formData.append('csvFile', file);
    formData.append('ignorarSabados', ignorarSabados);
    formData.append('debugMode', debugMode);
    formData.append('equipesSelecionadas', JSON.stringify(equipesSelecionadas));
    formData.append('tipoRelatorio', tipoRelatorio);
    formData.append('forcarReenvio', forcarReenvio ? 'true' : 'false');
    formData.append('apenasGestor', apenasGestor ? 'true' : 'false');
    formData.append('incluirDuplicadas', incluirDuplicadas ? 'true' : 'false');
    formData.append('incluirFeriados', incluirFeriados ? 'true' : 'false');
    return formData;
}
