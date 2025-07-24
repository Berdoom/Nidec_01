document.addEventListener('DOMContentLoaded', function() {
    // Contenedor principal que tiene todos los datos del backend.
    const container = document.getElementById('reports-container');
    if (!container) return;

    // --- 1. Leer datos del backend desde los atributos data-* ---
    const weeklyData = JSON.parse(container.dataset.weeklyData);
    const monthlyData = JSON.parse(container.dataset.monthlyData);
    const areaWeeklyData = JSON.parse(container.dataset.areaWeeklyData);
    const areaMonthlyData = JSON.parse(container.dataset.areaMonthlyData);
    const rangeData = JSON.parse(container.dataset.rangeChartData);
    const comparisonData = JSON.parse(container.dataset.comparisonChartData);
    const areas = {
        IHP: JSON.parse(container.dataset.areasIhp),
        FHP: JSON.parse(container.dataset.areasFhp)
    };
    const selectedArea = container.dataset.selectedArea;

    // --- 2. Referencias a elementos del DOM ---
    const reportTypeSelect = document.getElementById('report_type');
    const groupSelect = document.getElementById('group');
    const groupSelectorContainer = document.getElementById('group_selector_container');
    const singleDayInputs = document.getElementById('single_day_inputs');
    const dateRangeInputs = document.getElementById('date_range_inputs');
    const singleDateField = document.getElementById('single_date');
    const rangeStartDateField = document.getElementById('range_start_date');
    const areaSelectorContainer = document.getElementById('area_selector_container');
    const areaSelector = document.getElementById('area_selector');

    // --- 3. Lógica para los selectores dinámicos ---
    function updateAreaSelector() {
        const selectedGroup = groupSelect.value;
        areaSelector.innerHTML = ''; // Limpiar opciones anteriores
        
        if (areas[selectedGroup]) {
            areas[selectedGroup].forEach(area => {
                const option = document.createElement('option');
                option.value = area;
                option.textContent = area;
                if (area === selectedArea) {
                    option.selected = true;
                }
                areaSelector.appendChild(option);
            });
        }
    }

    function toggleInputs() {
        const selectedType = reportTypeSelect.value;
        // Resetear visibilidad
        groupSelectorContainer.style.display = 'none';
        singleDayInputs.style.display = 'none';
        dateRangeInputs.style.display = 'none';
        areaSelectorContainer.style.display = 'none';

        if (selectedType === 'group_comparison') {
            dateRangeInputs.style.display = 'flex';
        } else if (selectedType === 'date_range') {
            groupSelectorContainer.style.display = 'block';
            dateRangeInputs.style.display = 'flex';
        } else if (selectedType === 'area_analysis') {
            groupSelectorContainer.style.display = 'block';
            singleDayInputs.style.display = 'block';
            areaSelectorContainer.style.display = 'block';
        } else { // 'single_day'
            groupSelectorContainer.style.display = 'block';
            singleDayInputs.style.display = 'block';
        }
        
        // Asignar el nombre correcto al campo de fecha para el envío del formulario
        if (selectedType === 'date_range' || selectedType === 'group_comparison') {
            rangeStartDateField.name = 'start_date';
            singleDateField.name = 'start_date_single_disabled';
        } else {
            rangeStartDateField.name = 'start_date_range_disabled';
            singleDateField.name = 'start_date';
        }
    }
    
    // Asignar eventos y ejecutar al cargar
    groupSelect.addEventListener('change', updateAreaSelector);
    reportTypeSelect.addEventListener('change', toggleInputs);
    updateAreaSelector();
    toggleInputs();

    // --- 4. Inicialización de Gráficos ---

    // Gráfico de Análisis de Día (Semanal)
    const weeklyCtx = document.getElementById('weeklyChart');
    if (weeklyData && weeklyCtx) {
        new Chart(weeklyCtx, { /* ... configuración del gráfico ... */ });
    }

    // Gráfico de Análisis de Día (Mensual)
    const monthlyCtx = document.getElementById('monthlyChart');
    if (monthlyData && monthlyCtx) {
        new Chart(monthlyCtx, { /* ... configuración del gráfico ... */ });
    }

    // Gráfico de Análisis de Área (Semanal)
    const areaWeeklyCtx = document.getElementById('areaWeeklyChart');
    if (areaWeeklyData && areaWeeklyCtx) {
        new Chart(areaWeeklyCtx, {
            type: 'bar',
            data: {
                labels: areaWeeklyData.labels,
                datasets: [
                    { label: 'Producido', data: areaWeeklyData.producido, backgroundColor: 'rgba(36, 184, 23, 0.8)', order: 2 },
                    { label: 'Pronóstico', data: areaWeeklyData.pronostico, type: 'line', borderColor: 'rgba(255, 99, 132, 1)', fill: false, order: 1 }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }
        });
    }

    // Gráfico de Análisis de Área (Mensual)
    const areaMonthlyCtx = document.getElementById('areaMonthlyChart');
    if (areaMonthlyData && areaMonthlyCtx) {
        new Chart(areaMonthlyCtx, {
            type: 'line',
            data: {
                labels: areaMonthlyData.labels,
                datasets: [
                    { label: 'Producido', data: areaMonthlyData.producido, borderColor: 'rgb(36, 184, 23)', tension: 0.1 },
                    { label: 'Pronóstico', data: areaMonthlyData.pronostico, borderColor: 'rgb(255, 99, 132)', tension: 0.1, borderDash: [5, 5] }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }
        });
    }
    
    // Gráfico de Rango de Fechas
    const rangeCtx = document.getElementById('rangeChart');
    if (rangeData && rangeCtx) {
        new Chart(rangeCtx, {
            type: 'bar',
            data: {
                labels: rangeData.labels,
                datasets: [
                    { label: 'Producido', data: rangeData.producido, backgroundColor: 'rgba(36, 184, 23, 0.8)' },
                    { label: 'Pronóstico', data: rangeData.pronostico, backgroundColor: 'rgba(201, 203, 207, 0.8)' },
                    { label: 'Eficiencia (%)', data: rangeData.eficiencia, type: 'line', borderColor: '#ffc107', yAxisID: 'y1', tension: 0.1 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    x: { stacked: false },
                    y: { type: 'linear', display: true, position: 'left', stacked: false, title: { display: true, text: 'Unidades' } },
                    y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Eficiencia (%)' }, suggestedMax: 110 }
                }
            }
        });
    }

    // Gráfico de Comparación de Grupos
    const comparisonCtx = document.getElementById('comparisonChart');
    if (comparisonData && comparisonCtx) {
        new Chart(comparisonCtx, {
            type: 'line',
            data: {
                labels: comparisonData.labels,
                datasets: [
                    { label: 'IHP', data: comparisonData.ihp_data, borderColor: '#007bff', backgroundColor: 'rgba(0, 123, 255, 0.1)', fill: true, tension: 0.1 },
                    { label: 'FHP', data: comparisonData.fhp_data, borderColor: '#28a745', backgroundColor: 'rgba(40, 167, 69, 0.1)', fill: true, tension: 0.1 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: { y: { beginAtZero: true, title: { display: true, text: 'Unidades Producidas' } } }
            }
        });
    }
});