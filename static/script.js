// Variables globales
let carpetaSeleccionada = '';
let filtroActual = 'todos';
let infoMallaLocal = {};
let edicionActual = {};
let matchesGlobal = [];

// Icono SVG reutilizable para el botón Editar
const ICON_EDIT = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>';

// Actualizar estado cada 2 segundos
setInterval(actualizarEstado, 2000);
actualizarEstado(); // Llamada inicial

async function actualizarEstado() {
    try {
        const response = await fetch('/api/estado');
        const data = await response.json();

        document.getElementById('statusText').textContent = data.mensaje;

        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        if (progressFill) progressFill.style.width = data.porcentaje + '%';
        if (progressText) progressText.textContent = data.porcentaje + '%';

        const puedeGrafo = data.malla_size > 0;
        const puedeInferencia = data.malla_size > 0 && data.estado === 'listo';
        const puedeMicro = data.enlaces_size > 0;

        const btnMacro = document.getElementById('grafoMacroBtn');
        const btnInfer = document.getElementById('inferBtn');
        const btnMicro = document.getElementById('grafoMicroBtn');
        const btnExcel = document.getElementById('downloadExcelBtn');

        if (btnMacro) {
            btnMacro.disabled = !puedeGrafo;
            puedeGrafo ? btnMacro.classList.remove('btn-disabled') : btnMacro.classList.add('btn-disabled');
        }
        if (btnInfer) {
            btnInfer.disabled = !puedeInferencia;
            puedeInferencia ? btnInfer.classList.remove('btn-disabled') : btnInfer.classList.add('btn-disabled');
        }
        if (btnMicro) {
            btnMicro.disabled = !puedeMicro;
            puedeMicro ? btnMicro.classList.remove('btn-disabled') : btnMicro.classList.add('btn-disabled');
        }
        if (btnExcel) {
            btnExcel.disabled = !puedeMicro;
            puedeMicro ? btnExcel.classList.remove('btn-disabled') : btnExcel.classList.add('btn-disabled');
        }

        const dot = document.querySelector('.status-dot');
        if (dot) {
            if (data.estado === 'listo') {
                dot.style.background = '#22c55e';
            } else if (data.estado === 'procesando' || data.estado === 'inferencia') {
                dot.style.background = '#f59e0b';
            } else if (data.estado === 'error') {
                dot.style.background = '#ef4444';
            }
        }

        const progressBar = document.getElementById('progressBar');
        if (progressBar) {
            if (data.porcentaje < 100 && (data.estado === 'procesando' || data.estado === 'inferencia')) {
                progressBar.classList.remove('hidden');
            } else {
                progressBar.classList.add('hidden');
                if (data.estado === 'listo') {
                    const mallaTable = document.getElementById('mallTableBody');
                    if (mallaTable && mallaTable.querySelector('.empty-row')) {
                        actualizarTablaMalla();
                    }
                    if (data.enlaces_size > 0) {
                        const matchesTable = document.getElementById('matchesTableBody');
                        if (matchesTable && matchesTable.querySelector('.empty-row')) {
                            actualizarTablaMatches();
                        }
                    }
                }
            }
        }
    } catch (error) {
        console.error('Error actualizando estado:', error);
    }
}

function seleccionarCarpeta() {
    const input = document.getElementById('carpetaFile');
    input.click();

    input.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            const carpeta = e.target.files[0].webkitRelativePath.split('/')[0];
            carpetaSeleccionada = carpeta;
            document.getElementById('carpetaInput').value = carpeta;
        }
    });
}

async function procesarCarpeta() {
    const input = document.getElementById('carpetaFile');
    if (!input.files || input.files.length === 0) {
        alert('Por favor selecciona una carpeta');
        return;
    }

    const carpetaCompleta = document.getElementById('carpetaInput').value;
    if (!carpetaCompleta) {
        alert('Por favor selecciona una carpeta válida');
        return;
    }

    try {
        const response = await fetch('/api/procesar-carpeta', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ carpeta: carpetaCompleta })
        });
        const data = await response.json();
        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            setTimeout(actualizarTablaMalla, 500);
        }
    } catch (error) {
        console.error('Error procesando carpeta:', error);
    }
}

async function actualizarTablaMalla() {
    try {
        const response = await fetch('/api/malla');
        const datos = await response.json();
        const tbody = document.getElementById('mallTableBody');
        tbody.innerHTML = '';
        infoMallaLocal = {};

        if (datos.length === 0) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="4">No se encontraron ramos</td></tr>';
        } else {
            datos.forEach(ramo => {
                infoMallaLocal[ramo.codigo] = {
                    nombre: ramo.nombre,
                    ras: ramo.ra_list || [],
                    // Guardamos los prerrequisitos separando el string por comas
                    prereqs: ramo.prereqs !== "Ninguno" ? ramo.prereqs.split(',').map(s => s.trim()) : []
                };
                const row = tbody.insertRow();
                row.classList.add('fila-clickeable');
                row.dataset.codigo = ramo.codigo;
                row.innerHTML = `<td>${ramo.codigo}</td><td>${ramo.nombre}</td><td>${ramo.prereqs}</td><td><span class="severity-alto">${ramo.total_ra}</span></td>`;
                row.addEventListener('click', () => toggleFilaRamo(row, ramo.codigo));
            });
        }
    } catch (error) {
        console.error('Error actualizando tabla malla:', error);
    }
}

async function generarGrafoMacro() {
    try {
        document.getElementById('grafoContainer').innerHTML = '<p class="placeholder">Generando grafo...</p>';
        const response = await fetch('/api/generar-grafo-macro');
        const data = await response.json();
        if (data.error) alert('Error: ' + data.error);
        else {
            document.getElementById('grafoContainer').innerHTML = `<iframe src="${data.grafo_url}"></iframe>`;
            switchTab('tab-grafo');
        }
    } catch (error) {
        console.error('Error generando grafo macro:', error);
    }
}

async function ejecutarInferencia() {
    try {
        const response = await fetch('/api/ejecutar-inferencia', { method: 'POST' });
        const data = await response.json();
        if (data.error) alert('Error: ' + data.error);
        else setTimeout(actualizarTablaMatches, 1000);
    } catch (error) {
        console.error('Error en inferencia:', error);
    }
}

function truncarTexto(texto, maxCaracteres = 35) {
    if (!texto) return '';
    if (texto.length <= maxCaracteres) return texto;
    return texto.substring(0, maxCaracteres) + '...';
}

async function actualizarTablaMatches() {
    try {
        if (Object.keys(infoMallaLocal).length === 0) {
            const resMalla = await fetch('/api/malla');
            const datosMalla = await resMalla.json();
            datosMalla.forEach(r => {
                infoMallaLocal[r.codigo] = { 
                    nombre: r.nombre, 
                    ras: r.ra_list || [],
                    prereqs: r.prereqs !== "Ninguno" ? r.prereqs.split(',').map(s => s.trim()) : [] 
                };
            });
        }

        const response = await fetch('/api/matches');
        const datos = await response.json();
        matchesGlobal = datos;
        const tbody = document.getElementById('matchesTableBody');
        tbody.innerHTML = '';

        if (datos.length === 0) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="6">No hay matches</td></tr>';
        } else {
            datos.forEach(match => {
                const severidadClass = `severity-${match.severidad}`;
                const nombreRamoAct = infoMallaLocal[match.ramo_act] ? infoMallaLocal[match.ramo_act].nombre : match.ramo_act;
                const nombreRamoPre = infoMallaLocal[match.ramo_pre] ? infoMallaLocal[match.ramo_pre].nombre : match.ramo_pre;

                const vistaRamoAct = truncarTexto(`[${match.ramo_act}] ${nombreRamoAct}`, 30);
                const vistaRAAct   = truncarTexto(match.ra_act, 45);
                const vistaRamoPre = truncarTexto(`[${match.ramo_pre}] ${nombreRamoPre}`, 30);
                const vistaRAPre   = truncarTexto(match.ra_pre, 45);

                // Encriptamos los textos para que comillas o saltos de línea no rompan el botón
                const safeRamoAct = encodeURIComponent(match.ramo_act);
                const safeRaAct = encodeURIComponent(match.ra_act);
                const safeRamoPre = encodeURIComponent(match.ramo_pre);
                const safeRaPre = encodeURIComponent(match.ra_pre);
                const safeSev = encodeURIComponent(match.severidad);

                const row = tbody.insertRow();
                row.classList.add('fila-clickeable');
                row.dataset.ramoAct = match.ramo_act;
                row.dataset.raAct = match.ra_act;
                row.dataset.ramoPre = match.ramo_pre;
                row.dataset.raPre = match.ra_pre;
                row.innerHTML = `
                    <td title="[${match.ramo_act}] ${nombreRamoAct}">${vistaRamoAct}</td>
                    <td title="${match.ra_act}">${vistaRAAct}</td>
                    <td title="[${match.ramo_pre}] ${nombreRamoPre}">${vistaRamoPre}</td>
                    <td title="${match.ra_pre}">${vistaRAPre}</td>
                    <td><span class="${severidadClass}">${match.score.toFixed(1)}%</span></td>
                    <td>
                        <button class="btn-editar" onclick="event.stopPropagation(); abrirModal('${safeRamoAct}', '${safeRaAct}', '${safeRamoPre}', '${safeRaPre}', '${safeSev}')">
                            ${ICON_EDIT} Editar
                        </button>
                    </td>
                `;
                row.addEventListener('click', () => toggleFilaMatch(row, match));
            });
        }
        filtrarMatches(filtroActual);
    } catch (error) {
        console.error('Error actualizando matches:', error);
    }
}

function filtrarMatches(severidad) {
    filtroActual = severidad; // Guardamos el estado del filtro
    const severidadClase = severidad === 'no_match' ? 'sin_match' : severidad;
    const filas = document.getElementById('matchesTableBody').querySelectorAll('tr');

    filas.forEach(fila => {
        if (fila.classList.contains('fila-detalle-expandida')) return; // se ajusta después, según su fila padre
        let visible = true;
        if (severidad !== 'todos') {
            const scoreCell = fila.querySelector('td:nth-child(5)');
            visible = !!(scoreCell && scoreCell.querySelector('span') && scoreCell.querySelector('span').className.includes(`severity-${severidadClase}`));
        }
        fila.style.display = visible ? '' : 'none';

        // Si la fila tiene un detalle expandido justo debajo, lo sincronizamos
        const siguiente = fila.nextElementSibling;
        if (siguiente && siguiente.classList.contains('fila-detalle-expandida')) {
            siguiente.style.display = visible ? '' : 'none';
        }
    });
}

async function generarGrafoMicro() {
    try {
        document.getElementById('grafoContainer').innerHTML = '<p class="placeholder">Generando grafo detallado...</p>';
        const response = await fetch('/api/generar-grafo-micro');
        const data = await response.json();
        if (data.error) alert('Error: ' + data.error);
        else {
            document.getElementById('grafoContainer').innerHTML = `<iframe src="${data.grafo_url}"></iframe>`;
            switchTab('tab-grafo');
        }
    } catch (error) {
        console.error('Error generando grafo micro:', error);
    }
}

function switchTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
        tab.style.display = 'none';
    });
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));

    const targetTab = document.getElementById(tabName);
    if (targetTab) {
        targetTab.classList.add('active');
        targetTab.style.display = 'block';
    }
    const targetBtn = Array.from(document.querySelectorAll('.tab-btn')).find(btn => btn.getAttribute('onclick').includes(tabName));
    if (targetBtn) targetBtn.classList.add('active');
}

// Lógica de Edición y Modal
function abrirModal(encRamoAct, encRaAct, encRamoPre, encRaPre, encSev) {
    // Desencriptamos los textos
    const ramoAct = decodeURIComponent(encRamoAct);
    const raAct = decodeURIComponent(encRaAct);
    const ramoPre = decodeURIComponent(encRamoPre);
    const raPreActual = decodeURIComponent(encRaPre);
    const severidadActual = decodeURIComponent(encSev);

    edicionActual = { ramo_act: ramoAct, ra_act: raAct, ramo_pre: ramoPre };

    document.getElementById('modalRamoAct').innerText = ramoAct;
    document.getElementById('modalRAActual').innerText = raAct;
    document.getElementById('modalRamoPre').innerText = ramoPre;

    fetch('/api/malla')
        .then(res => res.json())
        .then(malla => {
            const ramoPreData = malla.find(r => r.codigo === ramoPre);
            const listContainer = document.getElementById('modalRAList');
            listContainer.innerHTML = '';

            if (ramoPreData && ramoPreData.ra_list) {
                ramoPreData.ra_list.forEach((ra, index) => {
                    const idRadio = `ra_opcion_${index}`;
                    const isChecked = (ra === raPreActual) ? 'checked' : '';

                    listContainer.innerHTML += `
                        <div class="ra-item" onclick="document.getElementById('${idRadio}').checked = true">
                            <input type="radio" id="${idRadio}" name="modalRASeleccionado" value="${ra}" ${isChecked}>
                            <label for="${idRadio}">${ra}</label>
                        </div>
                    `;
                });
            }

            const radiosSev = document.getElementsByName('modalSeveridad');
            radiosSev.forEach(radio => {
                radio.checked = (radio.value === severidadActual);
            });

            document.getElementById('modalCorreccion').classList.remove('hidden');
        });
}

function guardarCorreccion() {
    const raSeleccionado = document.querySelector('input[name="modalRASeleccionado"]:checked');
    const severidadSeleccionada = document.querySelector('input[name="modalSeveridad"]:checked');

    if (!raSeleccionado) {
        alert("Por favor, selecciona un RA de la lista.");
        return;
    }
    if (!severidadSeleccionada) {
        alert("Por favor, selecciona un nivel de vinculación.");
        return;
    }

    const payload = {
        ramo_act: edicionActual.ramo_act,
        ra_act: edicionActual.ra_act,
        ramo_pre: edicionActual.ramo_pre,
        nuevo_ra_pre: raSeleccionado.value,
        nueva_severidad: severidadSeleccionada.value
    };

    enviarEdicionBackend(payload);
}

function eliminarLink() {
    if (!confirm("¿Estás seguro de que quieres desvincular este RA? Pasará a estado 'Sin Match'.")) return;

    const payload = {
        ramo_act: edicionActual.ramo_act,
        ra_act: edicionActual.ra_act,
        ramo_pre: edicionActual.ramo_pre,
        nuevo_ra_pre: "Sin conexión semántica detectada en este prerrequisito.",
        nueva_severidad: "sin_match"
    };

    enviarEdicionBackend(payload);
}

function enviarEdicionBackend(payload) {
    fetch('/api/corregir-match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        if (data.exito) {
            cerrarModal();
            actualizarTablaMatches(); // Ahora esto repintará la tabla correctamente
        } else {
            alert("Error del servidor: " + data.error);
        }
    });
}

function cerrarModal() {
    document.getElementById('modalCorreccion').classList.add('hidden');
}

function descargarReporteExcel() {
    window.location.href = '/api/exportar-excel';
}


// ==================== LÓGICA CREAR ENLACE MANUAL ====================

function abrirModalCrear() {
    if (Object.keys(infoMallaLocal).length === 0) {
        alert("Primero debes cargar una malla para poder crear enlaces.");
        return;
    }

    const selAct = document.getElementById('nuevoRamoAct');
    const selPre = document.getElementById('nuevoRamoPre');
    
    // El ramo actual carga todos
    selAct.innerHTML = '<option value="">Seleccione Ramo Actual...</option>';
    
    // El prerrequisito parte deshabilitado hasta que elijas un ramo actual
    selPre.innerHTML = '<option value="">Primero seleccione Ramo Actual...</option>';
    selPre.disabled = true;

    // Poblar el selector destino con todos los ramos que tengan RAs
    Object.keys(infoMallaLocal).forEach(codigo => {
        const ramo = infoMallaLocal[codigo];
        if(ramo.ras && ramo.ras.length > 0) {
            selAct.innerHTML += `<option value="${codigo}">[${codigo}] ${ramo.nombre}</option>`;
        }
    });

    // Limpiar listas y modal
    document.getElementById('listaNuevosRaAct').innerHTML = '';
    document.getElementById('listaNuevosRaPre').innerHTML = '';
    document.querySelectorAll('input[name="nuevoSeveridad"]').forEach(r => r.checked = false);

    document.getElementById('modalCrearLink').classList.remove('hidden');
}

function cargarRAsParaSelect(tipo) {
    const codigo = document.getElementById(tipo === 'act' ? 'nuevoRamoAct' : 'nuevoRamoPre').value;
    const listContainer = document.getElementById(tipo === 'act' ? 'listaNuevosRaAct' : 'listaNuevosRaPre');
    const nameRadio = tipo === 'act' ? 'radioNuevoRaAct' : 'radioNuevoRaPre';

    listContainer.innerHTML = '';

    // --- LÓGICA DE FILTRADO DE PRERREQUISITOS ---
    if (tipo === 'act') {
        const selPre = document.getElementById('nuevoRamoPre');
        document.getElementById('listaNuevosRaPre').innerHTML = ''; // Limpiar RAs del prereq anterior
        
        if (codigo && infoMallaLocal[codigo]) {
            const prereqsOficiales = infoMallaLocal[codigo].prereqs || [];
            
            if (prereqsOficiales.length > 0) {
                selPre.disabled = false;
                selPre.innerHTML = '<option value="">Seleccione Prerrequisito...</option>';
                
                // Solo insertamos los ramos que estén en la lista de prerrequisitos de este ramo
                prereqsOficiales.forEach(preCod => {
                    // Validamos que el prerrequisito exista en la malla y tenga RAs definidos
                    if (infoMallaLocal[preCod] && infoMallaLocal[preCod].ras.length > 0) {
                        selPre.innerHTML += `<option value="${preCod}">[${preCod}] ${infoMallaLocal[preCod].nombre}</option>`;
                    }
                });

                // Si no se insertó nada válido
                if (selPre.options.length === 1) {
                    selPre.innerHTML = '<option value="">Los prerrequisitos de este ramo no tienen RAs</option>';
                    selPre.disabled = true;
                }
            } else {
                selPre.innerHTML = '<option value="">Este ramo no tiene prerrequisitos oficiales</option>';
                selPre.disabled = true;
            }
        } else {
            selPre.innerHTML = '<option value="">Primero seleccione Ramo Actual...</option>';
            selPre.disabled = true;
        }
    }

    // --- RENDERIZADO DE LAS TARJETAS DE RAs ---
    if (!codigo || !infoMallaLocal[codigo]) return;

    infoMallaLocal[codigo].ras.forEach((ra, i) => {
        const idRadio = `nra_${tipo}_${i}`;
        const safeRa = ra.replace(/"/g, '&quot;'); 
        
        listContainer.innerHTML += `
            <div class="ra-item" onclick="document.getElementById('${idRadio}').checked = true">
                <input type="radio" id="${idRadio}" name="${nameRadio}" value="${safeRa}">
                <label for="${idRadio}">${ra}</label>
            </div>
        `;
    });
}

function guardarEnlaceNuevo() {
    const ramoAct = document.getElementById('nuevoRamoAct').value;
    const ramoPre = document.getElementById('nuevoRamoPre').value;
    
    const raActNode = document.querySelector('input[name="radioNuevoRaAct"]:checked');
    const raPreNode = document.querySelector('input[name="radioNuevoRaPre"]:checked');
    const sevNode = document.querySelector('input[name="nuevoSeveridad"]:checked');

    if (!ramoAct || !ramoPre) {
        alert("Debes seleccionar ambos ramos."); return;
    }
    if (!raActNode || !raPreNode) {
        alert("Debes seleccionar un RA de origen y uno de destino."); return;
    }
    if (!sevNode) {
        alert("Debes seleccionar un nivel de vinculación."); return;
    }

    const payload = {
        ramo_act: ramoAct,
        ra_act: raActNode.value,
        ramo_pre: ramoPre,
        ra_pre: raPreNode.value,
        severidad: sevNode.value
    };

    fetch('/api/crear-match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        if(data.exito) {
            cerrarModalCrear();
            actualizarTablaMatches(); // Repintamos la tabla con el nuevo enlace
        } else {
            alert("Error del servidor: " + data.error);
        }
    });
}

function cerrarModalCrear() {
    document.getElementById('modalCrearLink').classList.add('hidden');
}

// ==================== CARGAR INFERENCIA DESDE EXCEL ====================

async function cargarInferenciaDesdeExcel(event) {
    const archivo = event.target.files[0];
    if (!archivo) return;

    // Reset para permitir resubir el mismo archivo
    event.target.value = '';

    const btn = document.getElementById('cargarInferenciaBtn');
    const textoOriginal = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4m11.4-11.4 1.4-1.4"/><circle cx="12" cy="12" r="4"/></svg> Cargando...`;

    try {
        const formData = new FormData();
        formData.append('archivo', archivo);

        const response = await fetch('/api/cargar-inferencia', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.error) {
            alert('Error al cargar la inferencia:\n' + data.error);
        } else {
            // Actualizar tablas con los datos restaurados
            await actualizarTablaMalla();
            await actualizarTablaMatches();

            const formato = data.formato_detectado === 'basico' ? 'Reporte básico' : 'Reporte dashboard';
            alert(
                `✅ Inferencia cargada correctamente\n\n` +
                `Formato detectado: ${formato}\n` +
                `${data.enlaces_cargados} enlaces restaurados\n` +
                `${data.ramos_reconstruidos} ramos reconstruidos`
            );

            // Ir a la pestaña de matches para ver los resultados
            switchTab('tab-matches');
        }
    } catch (error) {
        console.error('Error cargando inferencia:', error);
        alert('Error de red al cargar la inferencia.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = textoOriginal;
    }
}

// ==================== DETALLE EN ACORDEÓN (filas de tabla) ====================
// ==================== + PANEL INFERIOR (clicks desde el grafo) ====================

function cerrarPanelDetalle() {
    document.getElementById('panelDetalle').classList.add('hidden');
}

function abrirPanelDetalle(titulo, htmlBody) {
    document.getElementById('panelDetalleTitulo').innerText = titulo;
    document.getElementById('panelDetalleBody').innerHTML = htmlBody;
    document.getElementById('panelDetalle').classList.remove('hidden');
    document.getElementById('panelDetalleToggle').open = true;
    document.getElementById('panelDetalle').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function construirBodyEnlace(match) {
    const nombreRamoAct = infoMallaLocal[match.ramo_act] ? infoMallaLocal[match.ramo_act].nombre : match.ramo_act;
    const nombreRamoPre = infoMallaLocal[match.ramo_pre] ? infoMallaLocal[match.ramo_pre].nombre : match.ramo_pre;

    return `
        <div class="detalle-enlace">
            <div class="detalle-nodo origen">
                <div class="ramo-label">RA DE INICIO (prerrequisito)</div>
                <div class="ramo-codigo">[${match.ramo_pre}] ${nombreRamoPre}</div>
                <div class="ra-texto">${match.ra_pre}</div>
            </div>
            <div>
                <div class="detalle-flecha">➜</div>
                <div class="detalle-score"><b>${match.score.toFixed(1)}%</b><br>${match.severidad.toUpperCase()}</div>
            </div>
            <div class="detalle-nodo destino">
                <div class="ramo-label">RA DE LLEGADA (ramo actual)</div>
                <div class="ramo-codigo">[${match.ramo_act}] ${nombreRamoAct}</div>
                <div class="ra-texto">${match.ra_act}</div>
            </div>
        </div>
        <div class="panel-detalle-actions">
            <button class="btn btn-info btn-sm" onclick="window._enlaceParaGrafo = {fromId: '${match.nodo_origen_id}', toId: '${match.nodo_destino_id}'}; mostrarEnlaceEnGrafo();">
                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="5" r="3"/><circle cx="6" cy="19" r="3"/><circle cx="18" cy="19" r="3"/><path d="M12 8v3m0 0-5 5m5-5 5 5"/></svg>
                Mostrar en grafo
            </button>
        </div>
    `;
}

function construirBodyRamo(codigo) {
    const ramo = infoMallaLocal[codigo];
    if (!ramo) return '';

    const prereqsHtml = (ramo.prereqs && ramo.prereqs.length > 0)
        ? ramo.prereqs.map(p => `<span class="prereq-tag">${p}</span>`).join('')
        : '<span style="color:#888;">Sin prerrequisitos</span>';

    const rasHtml = (ramo.ras && ramo.ras.length > 0)
        ? ramo.ras.map(ra => `<div style="margin:6px 0; padding:8px; background:#2a2a40; border-radius:6px; font-size:13px;">${ra}</div>`).join('')
        : '<span style="color:#888;">Sin RAs detectados</span>';

    return `
        <div class="detalle-ramo-info">
            <p><strong>Código:</strong> ${codigo}</p>
            <p><strong>Nombre:</strong> ${ramo.nombre}</p>
            <p><strong>Prerrequisitos:</strong><br>${prereqsHtml}</p>
            <p style="margin-top:10px;"><strong>Resultados de Aprendizaje (${ramo.ras ? ramo.ras.length : 0}):</strong></p>
            <div style="max-height:240px; overflow-y:auto;">${rasHtml}</div>
        </div>
        <div class="panel-detalle-actions">
            <button class="btn btn-info btn-sm" onclick="window._ramoParaGrafo = '${codigo}'; mostrarRamoEnGrafo();">
                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="5" r="3"/><circle cx="6" cy="19" r="3"/><circle cx="18" cy="19" r="3"/><path d="M12 8v3m0 0-5 5m5-5 5 5"/></svg>
                Mostrar en grafo
            </button>
        </div>
    `;
}

// Usadas cuando el detalle viene de un click DENTRO del grafo embebido
// (no hay fila visible para expandir, así que cae al panel del fondo).
function mostrarDetalleEnlace(match) {
    window._enlaceParaGrafo = { fromId: match.nodo_origen_id, toId: match.nodo_destino_id };
    abrirPanelDetalle(`Enlace Semántico: ${match.ramo_pre} → ${match.ramo_act}`, construirBodyEnlace(match));
}

function mostrarDetalleRamo(codigo) {
    if (!infoMallaLocal[codigo]) return;
    window._ramoParaGrafo = codigo;
    abrirPanelDetalle(`Ramo: [${codigo}] ${infoMallaLocal[codigo].nombre}`, construirBodyRamo(codigo));
}

// ── Acordeón: expande/colapsa una fila de detalle justo debajo de la fila clickeada ──

function cerrarFilaExpandidaEn(tbody) {
    const existente = tbody.querySelector('tr.fila-detalle-expandida');
    if (existente) existente.remove();
    tbody.querySelectorAll('tr.fila-activa').forEach(f => f.classList.remove('fila-activa'));
}

function toggleFilaMatch(row, match) {
    const tbody = row.parentElement;
    const yaAbierta = row.nextElementSibling && row.nextElementSibling.classList.contains('fila-detalle-expandida') && row.classList.contains('fila-activa');

    cerrarFilaExpandidaEn(tbody);
    if (yaAbierta) return; // click en la misma fila → solo cerrar

    row.classList.add('fila-activa');
    const indiceEnTbody = Array.prototype.indexOf.call(tbody.rows, row);
    const filaDetalle = tbody.insertRow(indiceEnTbody + 1);
    filaDetalle.className = 'fila-detalle-expandida';
    const celda = filaDetalle.insertCell();
    celda.colSpan = 6;
    celda.innerHTML = construirBodyEnlace(match);
}

function toggleFilaRamo(row, codigo) {
    const tbody = row.parentElement;
    const yaAbierta = row.nextElementSibling && row.nextElementSibling.classList.contains('fila-detalle-expandida') && row.classList.contains('fila-activa');

    cerrarFilaExpandidaEn(tbody);
    if (yaAbierta) return;

    row.classList.add('fila-activa');
    const indiceEnTbody = Array.prototype.indexOf.call(tbody.rows, row);
    const filaDetalle = tbody.insertRow(indiceEnTbody + 1);
    filaDetalle.className = 'fila-detalle-expandida';
    const celda = filaDetalle.insertCell();
    celda.colSpan = 4;
    celda.innerHTML = construirBodyRamo(codigo);
}

function filtrarTablaMalla(termino) {
    const term = termino.toLowerCase().trim();
    const filas = document.getElementById('mallTableBody').querySelectorAll('tr');
    filas.forEach(fila => {
        if (fila.classList.contains('empty-row') || fila.classList.contains('fila-detalle-expandida')) return;
        const texto = fila.innerText.toLowerCase();
        fila.style.display = (!term || texto.includes(term)) ? '' : 'none';
    });
}

// ── Comunicación con el iframe del grafo embebido ──────────────────────────

function obtenerIframeGrafo() {
    const contenedor = document.getElementById('grafoContainer');
    return contenedor ? contenedor.querySelector('iframe') : null;
}

function enviarComandoAGrafo(payload) {
    const iframe = obtenerIframeGrafo();
    if (!iframe || !iframe.contentWindow) {
        alert('Primero genera el "Grafo Micro" en la pestaña Visualización para poder destacarlo ahí.');
        switchTab('tab-grafo');
        return;
    }
    switchTab('tab-grafo');
    // Pequeño delay por si el iframe necesita reflow al cambiar de pestaña
    setTimeout(() => {
        iframe.contentWindow.postMessage(payload, '*');
    }, 150);
}

function mostrarEnlaceEnGrafo() {
    if (!window._enlaceParaGrafo) return;
    enviarComandoAGrafo({
        action: 'focusEdge',
        fromId: window._enlaceParaGrafo.fromId,
        toId: window._enlaceParaGrafo.toId
    });
}

function mostrarRamoEnGrafo() {
    if (!window._ramoParaGrafo) return;
    enviarComandoAGrafo({
        action: 'focusNode',
        nodeId: window._ramoParaGrafo
    });
}

// ── Recibir clicks hechos DENTRO del grafo embebido (nodo o arista) ────────

function extraerCodigoDeNodoId(nodeId) {
    // Los ids de RA tienen forma "{codigo}_{hash}"; los de ramo son solo "{codigo}"
    return String(nodeId).split('_')[0];
}

function resaltarFilaTemporal(fila) {
    if (!fila) return;
    document.querySelectorAll('tr.fila-resaltada').forEach(f => f.classList.remove('fila-resaltada'));
    fila.classList.add('fila-resaltada');
    fila.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(() => fila.classList.remove('fila-resaltada'), 2500);
}

window.addEventListener('message', function(event) {
    const msg = event.data;
    if (!msg || typeof msg !== 'object') return;

    if (msg.event === 'edgeClicked' && msg.fromId && msg.toId) {
        // Buscamos el match cuyo enlace coincide con los nodos clickeados en el grafo
        const match = matchesGlobal.find(m =>
            (m.nodo_origen_id === msg.fromId && m.nodo_destino_id === msg.toId) ||
            (m.nodo_origen_id === msg.toId && m.nodo_destino_id === msg.fromId)
        );
        if (match) {
            // Mostramos el resumen abajo del grafo, sin cambiar de pestaña
            mostrarDetalleEnlace(match);
        }
    } else if (msg.event === 'nodeClicked' && msg.nodeId) {
        const codigo = extraerCodigoDeNodoId(msg.nodeId);
        if (infoMallaLocal[codigo]) {
            // Mostramos el resumen abajo del grafo, sin cambiar de pestaña
            mostrarDetalleRamo(codigo);
        }
    }
});