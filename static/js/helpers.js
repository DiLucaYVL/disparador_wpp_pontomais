export function gerarFormData(file, ignorarSabados, debugMode, equipesSelecionadas, tipoRelatorio, forcarReenvio = false) {
    const formData = new FormData();
    formData.append('csvFile', file);
    formData.append('ignorarSabados', ignorarSabados);
    formData.append('debugMode', debugMode);
    formData.append('equipesSelecionadas', JSON.stringify(equipesSelecionadas));
    formData.append('tipoRelatorio', tipoRelatorio);
    formData.append('forcarReenvio', forcarReenvio ? 'true' : 'false');
    return formData;
}
