// ==================== DASHBOARD ====================

let rasSinConectarData = [];
let filtroRazonActual = 'todos';

const RAZON_LABELS = {
    sin_prerrequisitos: "Sin prerrequisitos",
    prereq_no_encontrado: "Prereq. no en malla",
    score_bajo: "Score bajo (≤40%)",
    sin_evaluar: "Sin evaluar"
};

// Estado vacío "todo correcto" con icono SVG (reemplaza emojis)
const ICON_CHECK = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>';
function estadoOk(mensaje) {
    return `<span class="empty-state">${ICON_CHECK}${mensaje}</span>`;
}

cargarDashboard();

async function cargarDashboard() {
    try {
        const response = await fetch('/api/dashboard-stats');
        const data = await response.json();

        if (data.error) {
            alert('Error cargando dashboard: ' + data.error);
            return;
        }

        // --- OVERVIEW (hero + stats) ---
        // Hero: cobertura
        document.getElementById('kpiCobertura').textContent = data.porcentaje_cobertura + '%';
        document.getElementById('kpiCoberturaFoot').textContent =
            `${data.total_ras_conectados} de ${data.total_ras} RAs conectados`;
        const coberturaFill = document.getElementById('coberturaFill');
        if (coberturaFill) coberturaFill.style.width = data.porcentaje_cobertura + '%';

        // Supporting stats
        document.getElementById('kpiRamos').textContent = data.total_ramos;
        document.getElementById('kpiRamosFoot').textContent =
            `${data.ramos_con_ra} con RA definidos`;

        document.getElementById('kpiRasTotal').textContent = data.total_ras;
        document.getElementById('kpiRasTotalFoot').textContent =
            `${data.total_ras_conectados} conectados`;

        document.getElementById('kpiEnlaces').textContent = data.total_enlaces;
        document.getElementById('kpiEnlacesFoot').textContent =
            `score promedio ${data.score_promedio}%`;

        // --- Severidad de enlaces ---
        const sev = data.conteo_severidad;
        const maxSev = Math.max(sev.alto, sev.medio, sev.bajo, sev.sin_match, 1);

        setBar('barAlto', 'countAlto', sev.alto, maxSev);
        setBar('barMedio', 'countMedio', sev.medio, maxSev);
        setBar('barBajo', 'countBajo', sev.bajo, maxSev);
        setBar('barSinMatch', 'countSinMatch', sev.sin_match, maxSev);

        document.getElementById('totalEnlacesLabel').textContent =
            `${data.total_enlaces} enlaces · prom. ${data.score_promedio}%`;

        // --- Razones de RAs sin conectar ---
        const razones = data.conteo_razones_sin_conectar || {
            sin_prerrequisitos: 0, prereq_no_encontrado: 0, score_bajo: 0, sin_evaluar: 0
        };
        const maxRazon = Math.max(
            razones.sin_prerrequisitos, razones.prereq_no_encontrado,
            razones.score_bajo, razones.sin_evaluar, 1
        );

        setBar('barSinPrereq', 'countSinPrereq', razones.sin_prerrequisitos, maxRazon);
        setBar('barPrereqNF', 'countPrereqNF', razones.prereq_no_encontrado, maxRazon);
        setBar('barScoreBajo', 'countScoreBajo', razones.score_bajo, maxRazon);
        setBar('barSinEvaluar', 'countSinEvaluar', razones.sin_evaluar, maxRazon);

        document.getElementById('totalRasSinLabel').textContent =
            `${data.total_ras_sin_conectar} sin conectar`;
        document.getElementById('ramosSinInline').textContent = data.ramos_sin_conexion_count;

        // --- Contadores de las pestañas (navegación) ---
        document.getElementById('pillRamosSin').textContent = data.ramos_sin_conexion_count;
        document.getElementById('pillRasSin').textContent = data.total_ras_sin_conectar;
        document.getElementById('pillEnlacesDebiles').textContent =
            data.enlaces_debiles ? data.enlaces_debiles.length : 0;

        // --- Tablas (drill-down) ---
        renderRamosSinConexion(data.ramos_sin_conexion);
        rasSinConectarData = data.ras_sin_conectar || [];
        renderRasSinConectar();
        renderTopPrereqs(data.top_prereqs);
        renderEnlacesDebiles(data.enlaces_debiles || []);
        cargarTodosLosRamos(data);

    } catch (error) {
        console.error('Error cargando dashboard:', error);
    }
}

function setBar(barId, countId, valor, max) {
    const pct = max > 0 ? (valor / max) * 100 : 0;
    document.getElementById(barId).style.width = pct + '%';
    document.getElementById(countId).textContent = valor;
}

function renderRamosSinConexion(lista) {
    const tbody = document.getElementById('tablaRamosSin');
    tbody.innerHTML = '';

    if (!lista || lista.length === 0) {
        tbody.innerHTML = `<tr class="empty-row"><td colspan="4">${estadoOk('Todos los ramos con RA tienen al menos una conexión')}</td></tr>`;
        return;
    }

    lista.forEach(ramo => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td>${ramo.codigo}</td>
            <td>${ramo.nombre}</td>
            <td><span class="severity-bajo">${ramo.total_ra}</span></td>
            <td>${ramo.tiene_prereqs ? 'Sí' : 'No'}</td>
        `;
    });
}

function renderRasSinConectar() {
    const tbody = document.getElementById('tablaRasSin');
    tbody.innerHTML = '';

    const lista = filtroRazonActual === 'todos'
        ? rasSinConectarData
        : rasSinConectarData.filter(ra => ra.razon === filtroRazonActual);

    if (!lista || lista.length === 0) {
        const msg = rasSinConectarData.length === 0
            ? estadoOk('Todos los RAs quedaron conectados')
            : 'No hay RAs con esta razón';
        tbody.innerHTML = `<tr class="empty-row"><td colspan="6">${msg}</td></tr>`;
        return;
    }

    lista.forEach(ra => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td>${ra.codigo_ramo}</td>
            <td>${ra.nombre_ramo}</td>
            <td>${ra.ra_id}</td>
            <td title="${ra.descripcion}">${truncar(ra.descripcion, 90)}</td>
            <td><span class="${claseRazon(ra.razon)}">${RAZON_LABELS[ra.razon] || ra.razon}</span></td>
            <td>${ra.mejor_score}%</td>
        `;
    });
}

function claseRazon(razon) {
    switch (razon) {
        case 'sin_prerrequisitos': return 'sev-razon-sinprereq';
        case 'prereq_no_encontrado': return 'sev-razon-prereqnf';
        case 'score_bajo': return 'sev-razon-scorebajo';
        default: return 'sev-razon-sinevaluar';
    }
}

function filtrarRazon(razon, btn) {
    filtroRazonActual = razon;
    document.querySelectorAll('.razon-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderRasSinConectar();
}

function renderTopPrereqs(lista) {
    const tbody = document.getElementById('tablaTopPrereq');
    tbody.innerHTML = '';

    if (!lista || lista.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="4">Aún no hay enlaces semánticos calculados</td></tr>';
        return;
    }

    lista.forEach((item, idx) => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td>${idx + 1}</td>
            <td>${item.codigo}</td>
            <td>${item.nombre}</td>
            <td><span class="severity-alto">${item.conexiones}</span></td>
        `;
    });
}

async function cargarTodosLosRamos(statsData) {
    try {
        const response = await fetch('/api/malla');
        const ramos = await response.json();
        const tbody = document.getElementById('tablaRamosTodos');
        tbody.innerHTML = '';

        if (!ramos || ramos.length === 0) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="6">No hay ramos procesados todavía</td></tr>';
            return;
        }

        // Set de RAs sin conectar por código de ramo, para calcular conectados/sin conectar
        const sinConectarPorRamo = {};
        (statsData.ras_sin_conectar || []).forEach(ra => {
            sinConectarPorRamo[ra.codigo_ramo] = (sinConectarPorRamo[ra.codigo_ramo] || 0) + 1;
        });

        ramos.forEach(ramo => {
            const sinConectar = sinConectarPorRamo[ramo.codigo] || 0;
            const conectados = Math.max(ramo.total_ra - sinConectar, 0);

            const row = tbody.insertRow();
            row.innerHTML = `
                <td>${ramo.codigo}</td>
                <td>${ramo.nombre}</td>
                <td>${ramo.prereqs}</td>
                <td>${ramo.total_ra}</td>
                <td><span class="severity-alto">${conectados}</span></td>
                <td>${sinConectar > 0 ? `<span class="severity-bajo">${sinConectar}</span>` : '0'}</td>
            `;
        });
    } catch (error) {
        console.error('Error cargando tabla de ramos:', error);
    }
}

function truncar(texto, max = 90) {
    if (!texto) return '';
    if (texto.length <= max) return texto;
    return texto.substring(0, max) + '...';
}

function switchDashTab(tabId) {
    document.querySelectorAll('.dash-tab-content').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.dash-tab-btn').forEach(btn => btn.classList.remove('active'));

    document.getElementById(tabId).classList.add('active');
    const btn = Array.from(document.querySelectorAll('.dash-tab-btn'))
        .find(b => b.getAttribute('onclick').includes(tabId));
    if (btn) btn.classList.add('active');
}

function exportarDashboardExcel() {
    window.location.href = '/api/exportar-dashboard-excel';
}

function renderEnlacesDebiles(lista) {
    const tbody = document.getElementById('tablaEnlacesDebiles');
    tbody.innerHTML = '';

    if (!lista || lista.length === 0) {
        tbody.innerHTML = `<tr class="empty-row"><td colspan="5">${estadoOk('No hay enlaces con score bajo')}</td></tr>`;
        return;
    }

    lista.forEach(link => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td title="[${link.ramo_act}] ${link.nombre_act}">${link.ramo_act}</td>
            <td title="${link.ra_act}">${truncar(link.ra_act, 45)}</td>
            <td title="[${link.ramo_pre}] ${link.nombre_pre}">${link.ramo_pre}</td>
            <td title="${link.ra_pre}">${truncar(link.ra_pre, 45)}</td>
            <td><span class="severity-bajo">${link.score}%</span></td>
        `;
    });
}
