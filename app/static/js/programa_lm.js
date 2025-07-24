document.addEventListener('DOMContentLoaded', function() {
    const container = document.querySelector('.programa-lm-container');
    if (!container) return;

    const csrfToken = container.dataset.csrfToken;
    const updateCellUrl = container.dataset.updateCellUrl;
    const reorderUrl = container.dataset.reorderColumnsUrl;
    
    // Inicializa las funcionalidades principales de la tabla
    if (csrfToken && updateCellUrl) {
        initializeEditableCells(updateCellUrl, csrfToken);
        initializeContextMenu(updateCellUrl, csrfToken);
    }
    if (csrfToken && reorderUrl) {
        initializeAdminControls(reorderUrl, csrfToken);
    }
    initializeModalTrigger();
    initializeActionsToggle('lm_actions_hidden');
    initializeAjaxAddRowForm();

    // --- Lógica para tabs del menú contextual de colores ---
    const menu = document.getElementById('cell-context-menu');
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
});


/**
 * NUEVA FUNCIÓN: Inicializa el botón para ocultar/mostrar la columna de acciones.
 * @param {string} storageKey - La clave para usar en localStorage y guardar el estado.
 */
function initializeActionsToggle(storageKey) {
    const toggleBtn = document.getElementById('toggleActionsColBtn');
    const table = document.querySelector('.lm-table');

    if (!toggleBtn || !table) {
        return;
    }

    // Función para actualizar el estado visual del botón
    const updateButtonState = (isHidden) => {
        if (isHidden) {
            toggleBtn.innerHTML = '<i class="fas fa-eye-slash"></i>';
            toggleBtn.title = "Mostrar Acciones";
        } else {
            toggleBtn.innerHTML = '<i class="fas fa-eye"></i>';
            toggleBtn.title = "Ocultar Acciones";
        }
    };

    // 1. Aplicar estado guardado al cargar la página
    const isHidden = localStorage.getItem(storageKey) === 'true';
    if (isHidden) {
        table.classList.add('actions-hidden');
    }
    updateButtonState(isHidden);

    // 2. Añadir el evento click al botón
    toggleBtn.addEventListener('click', () => {
        const currentlyHidden = table.classList.toggle('actions-hidden');
        
        // 3. Guardar el nuevo estado en localStorage
        localStorage.setItem(storageKey, currentlyHidden);
        
        // 4. Actualizar el ícono y el tooltip del botón
        updateButtonState(currentlyHidden);
    });
}

function initializeAjaxAddRowForm() {
    const addRowForm = document.getElementById('addRowFormLM');
    if (!addRowForm) return;

    addRowForm.addEventListener('submit', function(event) {
        event.preventDefault(); // Previene el envío tradicional del formulario

        const formData = new FormData(addRowForm);
        const submitButton = addRowForm.querySelector('button[type="submit"]');
        submitButton.disabled = true; // Deshabilita el botón para evitar doble clic
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
                    window.location.reload(); // Recarga la página para ver el nuevo dato
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
            // Vuelve a habilitar el botón
            submitButton.disabled = false;
            submitButton.innerHTML = 'Crear Orden';
        });
    });
}
/**
 * Muestra una notificación toast de Bootstrap.
 */
function showToast(message, type = 'success') {
    const toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) return;
    const toastHTML = `
        <div class="toast" role="alert" data-delay="3000">
            <div class="toast-header bg-${type} text-white">
                <strong class="mr-auto">Programa LM</strong>
                <button type="button" class="ml-2 mb-1 close" data-dismiss="toast"><span aria-hidden="true">×</span></button>
            </div>
            <div class="toast-body bg-white">${message}</div>
        </div>`;
    toastContainer.insertAdjacentHTML('beforeend', toastHTML);
    const newToast = toastContainer.lastElementChild;
    $(newToast).toast('show');
    $(newToast).on('hidden.bs.toast', () => newToast.remove());
}

/**
 * Función central para guardar los datos de una celda.
 */
function saveCellData(url, token, cell, payload) {
    cell.classList.remove('saved-success', 'saved-error');
    cell.classList.add('saving');
    
    const body = {
        csrf_token: token,
        orden_id: cell.dataset.ordenId,
        columna_id: cell.dataset.columnaId,
        ...payload
    };

    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    })
    .then(response => {
        if (!response.ok) return response.json().then(err => Promise.reject(err));
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            cell.classList.add('saved-success');
            setTimeout(() => cell.classList.remove('saved-success'), 1500);
        }
    })
    .catch(error => {
        console.error('Error al guardar:', error);
        cell.classList.add('saved-error');
        showToast(`Error al guardar: ${error.message || 'Error de red'}`, 'danger');
    })
    .finally(() => {
        cell.classList.remove('saving');
    });
}

/**
 * Lógica para las celdas editables.
 */
function initializeEditableCells(url, token) {
    document.querySelectorAll('.lm-table .editable-cell').forEach(cell => {
        let originalValue = cell.textContent.trim();
        cell.addEventListener('focus', () => {
            originalValue = cell.textContent.trim();
        });
        cell.addEventListener('blur', (e) => {
            const newValue = e.target.textContent.trim();
            if (newValue !== originalValue) {
                saveCellData(url, token, cell, { valor: newValue });
            }
        });
    });
}

/**
 * Lógica para el menú contextual.
 */
function initializeContextMenu(url, token) {
    const menu = document.getElementById('cell-context-menu');
    let activeCell = null;

    document.querySelectorAll('.lm-table .editable-cell').forEach(cell => {
        cell.addEventListener('contextmenu', e => {
            e.preventDefault();
            activeCell = cell;

            // Hace el menú visible pero fuera de la vista para medir sus dimensiones
            menu.style.visibility = 'hidden';
            menu.style.display = 'block';

            const { offsetWidth: menuWidth, offsetHeight: menuHeight } = menu;
            const { innerWidth: viewportWidth, innerHeight: viewportHeight } = window;
            
            let left = e.clientX;
            let top = e.clientY;

            // Ajusta la posición horizontal si se desborda
            if (left + menuWidth > viewportWidth) {
                left = viewportWidth - menuWidth - 5; // Añade un margen de 5px
            }

            // Ajusta la posición vertical si se desborda
            if (top + menuHeight > viewportHeight) {
                top = viewportHeight - menuHeight - 5; // Añade un margen de 5px
            }

            // Aplica las posiciones calculadas y hace visible el menú
            menu.style.left = `${left}px`;
            menu.style.top = `${top}px`;
            menu.style.visibility = 'visible';
            
            const styles = JSON.parse(cell.dataset.styles || '{}');
            document.getElementById('bold-checkbox').checked = styles.fontWeight === 'bold';
        });
    });

    document.addEventListener('click', () => { if (menu.style.display === 'block') { menu.style.display = 'none'; } });
    menu.addEventListener('click', e => e.stopPropagation());

    menu.querySelectorAll('.color-box').forEach(box => {
        box.addEventListener('click', () => {
            if (!activeCell) return;
            
            const property = box.dataset.property; // Esto será 'backgroundColor' o 'color'
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

    document.getElementById('format-bold').addEventListener('click', (e) => {
        if (!activeCell) return;
        const checkbox = document.getElementById('bold-checkbox');
        const isChecked = e.target.tagName === 'LABEL' ? !checkbox.checked : checkbox.checked;
        let currentStyles = JSON.parse(activeCell.dataset.styles || '{}');
        currentStyles.fontWeight = isChecked ? 'bold' : 'normal';
        activeCell.style.fontWeight = currentStyles.fontWeight;
        activeCell.dataset.styles = JSON.stringify(currentStyles);
        saveCellData(url, token, activeCell, { estilos_css: currentStyles });
    });

    document.getElementById('reset-style-btn').addEventListener('click', () => {
        if (!activeCell) return;
        activeCell.style.backgroundColor = '';
        activeCell.style.color = '';
        activeCell.style.fontWeight = '';
        activeCell.dataset.styles = '{}';
        saveCellData(url, token, activeCell, { estilos_css: {}, valor: activeCell.textContent.trim() });
        menu.style.display = 'none';
    });
}

/**
 * Lógica para reordenar columnas.
 */
function initializeAdminControls(reorderUrl, token) {
    const headerRow = document.getElementById('lm-table-header-row');
    const reorderBtn = document.getElementById('reorderBtn');
    let sortable = null;

    if (reorderBtn) {
        reorderBtn.addEventListener('click', () => {
            if (sortable) {
                const orderedIds = sortable.toArray();
                sortable.destroy();
                sortable = null;
                reorderBtn.classList.remove('btn-success');
                reorderBtn.innerHTML = '<i class="fas fa-sort mr-1"></i> Ordenar';
                
                fetch(reorderUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ csrf_token: token, ordered_ids: orderedIds })
                })
                .then(res => res.json())
                .then(data => showToast(data.message, data.status === 'success' ? 'success' : 'danger'))
                .catch(() => showToast('Error al guardar el orden.', 'danger'));

            } else {
                reorderBtn.classList.add('btn-success');
                reorderBtn.innerHTML = '<i class="fas fa-save mr-1"></i> Guardar Orden';
                sortable = new Sortable(headerRow, {
                    animation: 150,
                    filter: '.non-draggable',
                    preventOnFilter: true,
                    dataIdAttr: 'data-col-id'
                });
            }
        });
    }
}

/**
 * Lógica para rellenar el modal de edición.
 */
function initializeModalTrigger() {
    $('#editRowModal').on('show.bs.modal', function (event) {
        const button = $(event.relatedTarget);
        const ordenId = button.data('orden-id');
        const wipOrder = button.data('wip-order');
        const item = button.data('item');
        const qty = button.data('qty');
        
        const form = $('#editRowForm');
        const baseUrl = form.data('base-action-url');
        form.attr('action', baseUrl.replace('0', ordenId));
        
        form.find('#edit_wip_order').val(wipOrder);
        form.find('#edit_item').val(item);
        form.find('#edit_qty').val(qty);
    });
}