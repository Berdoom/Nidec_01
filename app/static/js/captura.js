let PRONOSTICOS_DATA;
let HORAS_TURNO;
let NOMBRES_TURNOS;

/**
 * Inicializa la página de captura, configurando listeners y calculando totales.
 */
function initializeCapturaPage(horasTurnoData, nombresTurnosData, pronosticosData) {
    HORAS_TURNO = horasTurnoData;
    NOMBRES_TURNOS = nombresTurnosData;
    PRONOSTICOS_DATA = pronosticosData;

    let hasUnsavedChanges = false;
    const productionForm = document.getElementById('productionForm');
    if (productionForm) {
        productionForm.addEventListener('input', () => { hasUnsavedChanges = true; });
        productionForm.addEventListener('submit', () => { hasUnsavedChanges = false; });
    }
    window.addEventListener('beforeunload', (e) => {
        if (hasUnsavedChanges) { e.preventDefault(); e.returnValue = ''; }
    });

    document.querySelectorAll('[data-area-slug]').forEach(el => {
        if (el.dataset.areaSlug) {
            // Al cargar, solo calcula totales, NO actualiza colores.
            calculateAllTotalsForArea(el.dataset.areaSlug, false);
        }
    });
}

function toSlug(text) {
    if (typeof text !== 'string') return '';
    return text.replace(/ /g, '_').replace(/\./g, '').replace(/\//g, '');
}

/**
 * Se activa cuando un valor de entrada cambia.
 * Sincroniza los valores entre vistas y recalcula todo (totales y colores).
 */
function onInputChanged(inputElement) {
    const name = inputElement.name;
    const value = inputElement.value;

    document.querySelectorAll(`input[name="${name}"]`).forEach(counterpart => {
        if (counterpart !== inputElement) {
            counterpart.value = value;
        }
    });

    const areaSlug = inputElement.closest('[data-area-slug]')?.dataset.areaSlug;
    if (areaSlug) {
        // Al editar, SÍ actualiza totales y colores.
        calculateAllTotalsForArea(areaSlug, true);
    }
}


/**
 * Calcula todos los totales para un área específica y, opcionalmente, actualiza los colores de los inputs.
 * @param {string} areaSlug - El identificador del área a calcular.
 * @param {boolean} updateColors - Si es true, recalculará y aplicará las clases de color a los inputs.
 */
function calculateAllTotalsForArea(areaSlug, updateColors = false) {
    const areaContainers = document.querySelectorAll(`[data-area-slug="${areaSlug}"]`);
    if (areaContainers.length === 0) return;

    const areaName = areaContainers[0].dataset.areaName;

    NOMBRES_TURNOS.forEach(turnoName => {
        const turnoSlug = toSlug(turnoName);
        const pronosticoInputs = document.querySelectorAll(`input[name="pronostico_${areaSlug}_${turnoSlug}"]`);
        const pronosticoValor = Number(pronosticoInputs[0].value) || 0;

        let totalProduccionTurno = 0;
        const horasDelTurno = HORAS_TURNO[turnoName] || [];
        const hourlyTarget = pronosticoValor > 0 && horasDelTurno.length > 0 ? pronosticoValor / horasDelTurno.length : 0;

        horasDelTurno.forEach(hora => {
            const produccionInputs = document.querySelectorAll(`input[name="produccion_${areaSlug}_${hora}"]`);
            const valorProduccion = Number(produccionInputs[0].value) || 0;
            totalProduccionTurno += valorProduccion;

            // ==========================================================
            // ============== INICIO DE LA CORRECCIÓN CRÍTICA ===========
            // ==========================================================
            // Este bloque completo ahora SOLO se ejecuta si updateColors es true.
            if (updateColors) {
                produccionInputs.forEach(input => {
                    // La eliminación de clases ahora está DENTRO de la condición,
                    // por lo que no se ejecuta al cargar la página.
                    input.classList.remove('input-success', 'input-warning');
                    
                    if (hourlyTarget > 0 && input.value !== '') {
                        if (valorProduccion >= hourlyTarget) {
                            input.classList.add('input-success');
                        } else {
                            input.classList.add('input-warning');
                        }
                    }
                });
            }
            // ==========================================================
            // ================ FIN DE LA CORRECCIÓN CRÍTICA ============
            // ==========================================================
        });
        
        // El total del turno siempre se actualiza
        document.querySelectorAll(`#total_produccion_turno_${areaSlug}_${turnoSlug}, #mobile_total_produccion_turno_${areaSlug}_${turnoSlug}`)
            .forEach(span => span.textContent = totalProduccionTurno.toLocaleString());

        updateValidationIcon(areaSlug, turnoSlug, areaName, turnoName, totalProduccionTurno, pronosticoValor);
    });
}


/**
 * Actualiza el ícono de validación (check o advertencia) para un turno.
 */
function updateValidationIcon(areaSlug, turnoSlug, areaName, turnoName, totalProduccion, pronostico) {
    const hasExistingReason = PRONOSTICOS_DATA[areaName]?.[turnoName]?.razon_desviacion;
    let allInputsFilled = true;
    (HORAS_TURNO[turnoName] || []).forEach(hora => {
        const input = document.querySelector(`.desktop-view input[name="produccion_${areaSlug}_${hora}"]`);
        if (!input || input.value === '') {
            allInputsFilled = false;
        }
    });

    document.querySelectorAll(`#validation_icon_container_${areaSlug}_${turnoSlug}, #mobile_validation_icon_container_${areaSlug}_${turnoSlug}`)
        .forEach(container => {
            container.innerHTML = '';
            container.classList.remove('clickable-icon');
            if (hasExistingReason) {
                container.innerHTML = '<i class="fas fa-check-circle text-success" title="Razón ya enviada"></i>';
            } else if (allInputsFilled && pronostico > 0 && totalProduccion < pronostico) {
                container.innerHTML = '<i class="fas fa-exclamation-triangle text-warning" title="Justificar desviación"></i>';
                container.classList.add('clickable-icon');
            }
        });
}

/**
 * Maneja el clic en el ícono de validación.
 */
function handleValidationIconClick(container) {
    if (!container.classList.contains('clickable-icon')) return;
    document.getElementById('modalDate').value = container.dataset.date;
    document.getElementById('modalArea').value = container.dataset.areaName;
    document.getElementById('modalTurno').value = container.dataset.turnoName;
    document.getElementById('reasonText').value = '';
    $('#reasonModal').modal('show');
}

/**
 * Envía la razón de desviación al servidor.
 */
function submitReason() {
    const reasonText = document.getElementById('reasonText').value;
    if (!reasonText.trim()) { alert('La razón no puede estar vacía.'); return; }
    $('#reasonModal').modal('hide');
    
    const form = document.getElementById('productionForm');
    const areaName = document.getElementById('modalArea').value;
    const turnoName = document.getElementById('modalTurno').value;

    $.ajax({
        url: form.dataset.submitReasonUrl,
        type: "POST",
        data: {
            csrf_token: document.querySelector('input[name="csrf_token"]').value,
            date: document.getElementById('modalDate').value,
            area: areaName,
            group: form.dataset.group,
            reason: reasonText,
            turno_name: turnoName
        },
        success: function(response) {
            if (response.status === 'success') {
                if (!PRONOSTICOS_DATA[areaName]) PRONOSTICOS_DATA[areaName] = {};
                if (!PRONOSTICOS_DATA[areaName][turnoName]) PRONOSTICOS_DATA[areaName][turnoName] = {};
                PRONOSTICOS_DATA[areaName][turnoName].razon_desviacion = reasonText;
                calculateAllTotalsForArea(toSlug(areaName), true); // Recalcular y pintar
                alert(response.message);
            } else {
                alert('Error: ' + response.message);
            }
        },
        error: function() { alert('No se pudo comunicar con el servidor.'); }
    });
}