// static/js/programa_rotores.js

document.addEventListener('DOMContentLoaded', function() {
    const container = document.querySelector('.programa-rotores-container');
    if (!container) return;

    const csrfToken = container.dataset.csrfToken;
    const updateCellUrl = container.dataset.updateCellUrl;
    
    // Inicializar todas las funcionalidades de la página
    if (csrfToken && updateCellUrl) {
        initializeEditableCells(updateCellUrl, csrfToken);
        initializeContextMenu(updateCellUrl, csrfToken);
    }
    initializeActionsToggle('rotores_actions_hidden');
    initializeModalTrigger();
    initializeAjaxFormSubmit();
});

/**
 * Intercepta el envío del formulario para "Añadir Orden" y lo maneja con AJAX.
 */
function initializeAjaxFormSubmit() {
    const addRowForm = document.getElementById('addRowFormRotores');
    if (!addRowForm) return;

    addRowForm.addEventListener('submit', function(event) {
        event.preventDefault();

        const formData = new FormData(addRowForm);
        const submitButton = addRowForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';

        fetch(addRowForm.action, {
            method: 'POST',
            body: formData,
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                $('#addRowModal').modal('hide');
                Swal.fire({
                    icon: 'success',
                    title: '¡Orden Añadida!',
                    text: data.message,
                    timer: 2000,
                    showConfirmButton: false
                }).then(() => {
                    window.location.reload();
                });
            } else {
                Swal.fire({
                    icon: 'error',
                    title: 'Error al Añadir',
                    text: data.message,
                });
            }
        })
        .catch(error => {
            console.error('Error en la petición fetch:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error de Conexión',
                text: 'No se pudo comunicar con el servidor.',
            });
        })
        .finally(() => {
            submitButton.disabled = false;
            submitButton.innerHTML = 'Crear Orden';
        });
    });
}


/**
 * Función genérica para guardar los datos de una celda.
 */
function saveCellData(url, token, cell, payload) {
    const body = {
        csrf_token: token,
        orden_id: cell.dataset.ordenId,
        columna_id: cell.dataset.columnaId,
        ...payload
    };

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': token
        },
        body: JSON.stringify(body)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status !== 'success') {
            console.error('Error al guardar la celda:', data.message);
            cell.classList.add('saved-error');
            setTimeout(() => cell.classList.remove('saved-error'), 2000);
        } else {
            cell.classList.add('saved-success');
            setTimeout(() => cell.classList.remove('saved-success'), 1500);
        }
    })
    .catch(error => {
        console.error('Error de red al guardar la celda:', error);
        cell.classList.add('saved-error');
        setTimeout(() => cell.classList.remove('saved-error'), 2000);
    });
}

/**
 * Lógica para celdas editables (guardado de texto).
 */
function initializeEditableCells(url, token) {
    document.querySelectorAll('.editable-cell').forEach(cell => {
        let originalValue = cell.textContent.trim();
        cell.addEventListener('blur', () => {
            const newValue = cell.textContent.trim();
            if (newValue !== originalValue) {
                saveCellData(url, token, cell, { valor: newValue });
                originalValue = newValue;
            }
        });
        cell.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                cell.blur();
            }
        });
    });
}

/**
 * Lógica para el menú contextual (clic derecho para estilos).
 */
function initializeContextMenu(url, token) {
    const menu = document.getElementById('cell-context-menu');
    if (!menu) return;
    let activeCell = null;

    document.querySelectorAll('.programa-rotores-container .editable-cell').forEach(cell => {
        cell.addEventListener('contextmenu', e => {
            if (!cell.isContentEditable) return;
            e.preventDefault();
            activeCell = cell;
            menu.style.display = 'block';
            menu.style.left = `${e.pageX}px`;
            menu.style.top = `${e.pageY}px`;
            
            const styles = JSON.parse(cell.dataset.styles || '{}');
            const boldCheckbox = document.getElementById('bold-checkbox');
            if (boldCheckbox) {
                boldCheckbox.checked = styles.fontWeight === 'bold';
            }
        });
    });

    document.addEventListener('click', () => { if (menu.style.display === 'block') menu.style.display = 'none'; });
    menu.addEventListener('click', e => e.stopPropagation());

    // --- Lógica para tabs del menú contextual de colores ---
    if (menu) {
        const tabBtns = menu.querySelectorAll('.context-tab-btn');
        const tabPages = menu.querySelectorAll('.context-tab-page');
        tabBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                tabBtns.forEach(b => {
                    b.classList.remove('active');
                    b.style.background = '#f0f0f0';
                    b.style.color = '#555';
                });
                btn.classList.add('active');
                btn.style.background = '#218838';
                btn.style.color = '#fff';
                const tab = btn.getAttribute('data-tab');
                tabPages.forEach(page => {
                    if (page.getAttribute('data-tab-page') === tab) {
                        page.style.display = 'block';
                    } else {
                        page.style.display = 'none';
                    }
                });
            });
        });
        // Inicializa el color de la pestaña activa al cargar
        tabBtns.forEach(btn => {
            if (btn.classList.contains('active')) {
                btn.style.background = '#218838';
                btn.style.color = '#fff';
            } else {
                btn.style.background = '#f0f0f0';
                btn.style.color = '#555';
            }
        });
    }
    // --- Fin tabs ---

menu.querySelectorAll('.color-box').forEach(box => {
        box.addEventListener('click', () => {
            if (!activeCell) return;
            const property = box.dataset.property;
            const color = box.dataset.color;
            let currentStyles = JSON.parse(activeCell.dataset.styles || '{}');
             // Si el estilo actual para esa propiedad es el mismo que el color del botón, lo quitamos.
            if (currentStyles[property] === color) {
                delete currentStyles[property];
                activeCell.style[property] = '';
            } else {
            // Si es un color diferente o no existe, lo aplicamos.
                currentStyles[property] = color;
                activeCell.style[property] = color;
            }
            activeCell.dataset.styles = JSON.stringify(currentStyles);
            saveCellData(url, token, activeCell, { estilos_css: currentStyles });
        });
    });

    const formatBoldButton = document.getElementById('format-bold');
    if (formatBoldButton) {
        formatBoldButton.addEventListener('click', (e) => {
            if (!activeCell) return;
            e.stopPropagation();
            const checkbox = document.getElementById('bold-checkbox');
            const isChecked = e.target.tagName === 'LABEL' ? !checkbox.checked : checkbox.checked;
            checkbox.checked = isChecked;
            let currentStyles = JSON.parse(activeCell.dataset.styles || '{}');
            currentStyles.fontWeight = isChecked ? 'bold' : 'normal';
            activeCell.style.fontWeight = currentStyles.fontWeight;
            activeCell.dataset.styles = JSON.stringify(currentStyles);
            saveCellData(url, token, activeCell, { estilos_css: currentStyles });
        });
    }

    const resetStyleButton = document.getElementById('reset-style-btn');
    if (resetStyleButton) {
        resetStyleButton.addEventListener('click', () => {
            if (!activeCell) return;
            activeCell.style.backgroundColor = '';
            activeCell.style.color = '';
            activeCell.style.fontWeight = '';
            activeCell.dataset.styles = '{}';
            saveCellData(url, token, activeCell, { estilos_css: {} });
            menu.style.display = 'none';
        });
    }
}

/**
 * Lógica para el botón de mostrar/ocultar la columna de acciones.
 */
function initializeActionsToggle(storageKey) {
    const toggleBtn = document.getElementById('toggleActionsColBtn');
    const table = document.querySelector('.lm-table');
    if (!toggleBtn || !table) return;

    const updateButtonState = (isHidden) => {
        toggleBtn.innerHTML = isHidden ? '<i class="fas fa-eye-slash"></i>' : '<i class="fas fa-eye"></i>';
        toggleBtn.title = isHidden ? "Mostrar Acciones" : "Ocultar Acciones";
    };

    const isHidden = localStorage.getItem(storageKey) === 'true';
    if (isHidden) {
        table.classList.add('actions-hidden');
    }
    updateButtonState(isHidden);

    toggleBtn.addEventListener('click', () => {
        const currentlyHidden = table.classList.toggle('actions-hidden');
        localStorage.setItem(storageKey, currentlyHidden);
        updateButtonState(currentlyHidden);
    });
}

/**
 * Lógica para rellenar el modal de edición cuando se abre.
 */
function initializeModalTrigger() {
    $('#editRowModal').on('show.bs.modal', function (event) {
        const button = $(event.relatedTarget);
        const ordenId = button.data('orden-id');
        const item = button.data('item');
        const itemNumber = button.data('item-number');
        const cantidad = button.data('cantidad');
        const form = $('#editRowForm');
        const baseUrl = form.data('base-action-url');
        form.attr('action', baseUrl.replace('0', ordenId));
        form.find('#edit_item').val(item);
        form.find('#edit_item_number').val(itemNumber);
        form.find('#edit_cantidad').val(cantidad);
    });
}