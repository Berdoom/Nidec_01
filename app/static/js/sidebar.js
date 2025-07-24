/**
 * Sidebar functionality for Nidec Production System
 * Handles sidebar toggle, responsive behavior, and menu interactions
 */

class SidebarManager {
    constructor() {
        // --- Referencias a elementos existentes del DOM ---
        this.sidebar = document.getElementById('sidebar');
        this.sidebarToggle = document.getElementById('sidebarToggle');
        this.sidebarClose = document.getElementById('sidebarClose');
        this.sidebarOverlay = document.getElementById('sidebarOverlay');
        this.mainContent = document.getElementById('mainContent');
        this.body = document.body;
        
        /* ================================================================ */
        /* ======== INICIO DEL CAMBIO: Propiedades para el scroll ========= */
        /* ================================================================ */

        // NOTA: Guardamos una referencia al encabezado para manipularlo.
        this.header = document.querySelector('.top-header');
        
        // NOTA: Esta variable funciona como nuestra "memoria" para saber dónde estábamos.
        this.lastScrollTop = 0;
        
        // NOTA: Evita que el encabezado se oculte con scrolls muy pequeños (ej. al inicio).
        // Debe desplazarse al menos 100px hacia abajo para que se active.
        this.scrollThreshold = 100;
        
        /* ================================================================ */
        /* ================= FIN DEL CAMBIO EN EL CONSTRUCTOR ============= */
        /* ================================================================ */
        
        this.isOpen = false;
        this.isDesktop = window.innerWidth >= 992;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.setupResponsive();
        this.setupMenuDropdowns();
        
        // --- CAMBIO: Se llama a la nueva función que activa la escucha del scroll ---
        this.setupScrollListener();
    }
    
    bindEvents() {
        // ... (resto de eventos sin cambios) ...
        if (this.sidebarToggle) { this.sidebarToggle.addEventListener('click', (e) => { e.preventDefault(); this.toggleSidebar(); }); }
        if (this.sidebarClose) { this.sidebarClose.addEventListener('click', (e) => { e.preventDefault(); this.closeSidebar(); }); }
        if (this.sidebarOverlay) { this.sidebarOverlay.addEventListener('click', () => { this.closeSidebar(); }); }
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && this.isOpen && !this.isDesktop) { this.closeSidebar(); } });
        window.addEventListener('resize', () => { this.handleResize(); });
    }

    /* ================================================================ */
    /* ======== INICIO DEL CAMBIO: Nuevas funciones para scroll ======= */
    /* ================================================================ */
    
    /**
     * NOTA: Esta función configura el listener para el evento de scroll.
     * Utiliza un 'setTimeout' para "ahogar" (throttle) el evento, lo que significa
     * que la lógica de scroll no se ejecuta en cada píxel de movimiento, sino
     * cada 100ms, mejorando enormemente el rendimiento.
     */
    setupScrollListener() {
        let scrollTimeout;
        window.addEventListener('scroll', () => {
            if (!scrollTimeout) {
                scrollTimeout = setTimeout(() => {
                    this.handleScroll();
                    scrollTimeout = null;
                }, 100); // Ejecuta la lógica como máximo 10 veces por segundo
            }
        });
    }

    /**
     * NOTA: Esta es la lógica principal. Se ejecuta cada vez que el scroll es detectado.
     * Aquí es donde la "magia" ocurre.
     */
    handleScroll() {
        // Si por alguna razón no hay encabezado en la página, no hacemos nada.
        if (!this.header) return;

        // Obtenemos la posición vertical actual del scroll.
        let st = window.pageYOffset || document.documentElement.scrollTop;

        // Condición principal:
        // 1. ¿La posición actual (st) es MAYOR que la anterior (this.lastScrollTop)? -> (Vamos hacia abajo)
        // 2. ¿Hemos bajado más allá del umbral (this.scrollThreshold)? -> (Evita ocultarse al inicio)
        if (st > this.lastScrollTop && st > this.scrollThreshold) {
            // Si vamos hacia ABAJO, añadimos la clase que lo oculta.
            this.header.classList.add('header-hidden');
        } else {
            // Si vamos hacia ARRIBA, quitamos la clase para que vuelva a aparecer.
            this.header.classList.remove('header-hidden');
        }

        // Finalmente, actualizamos nuestra "memoria" con la posición actual para la
        // próxima vez que se ejecute la función.
        this.lastScrollTop = st <= 0 ? 0 : st;
    }
    
    /* ================================================================ */
    /* ================== FIN DE LAS NUEVAS FUNCIONES ================= */
    /* ================================================================ */

    setupResponsive() {
        if (!this.isDesktop) { this.closeSidebar(); }
    }
    
    setupMenuDropdowns() {
        const dropdownItems = document.querySelectorAll('.menu-dropdown');
        dropdownItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleSubmenu(item);
            });
        });
    }
    
    toggleSubmenu(item) {
        const target = item.getAttribute('data-target');
        const submenu = document.querySelector(target);
        const icon = item.querySelector('.dropdown-icon');
        if (submenu) {
            submenu.classList.toggle('show');
            if (icon) { icon.classList.toggle('rotated'); }
        }
    }
    
    toggleSidebar() {
        if (this.isOpen) { this.closeSidebar(); } else { this.openSidebar(); }
    }
    
    openSidebar() {
        if (this.sidebar) { this.sidebar.classList.add('active'); }
        if (this.sidebarOverlay) { this.sidebarOverlay.classList.add('active'); }
        this.body.classList.add('sidebar-open');
        if (this.isDesktop && this.mainContent) { this.mainContent.classList.add('sidebar-open'); }
        this.isOpen = true;
    }
    
    closeSidebar() {
        if (this.sidebar) { this.sidebar.classList.remove('active'); }
        if (this.sidebarOverlay) { this.sidebarOverlay.classList.remove('active'); }
        this.body.classList.remove('sidebar-open');
        if (this.isDesktop && this.mainContent) { this.mainContent.classList.remove('sidebar-open'); }
        this.isOpen = false;
    }
    
    handleResize() {
        const wasDesktop = this.isDesktop;
        this.isDesktop = window.innerWidth >= 992;
        if (wasDesktop !== this.isDesktop) {
            if (!this.isDesktop) { this.closeSidebar(); }
        }
    }
    
    isSidebarOpen() { return this.isOpen; }
}

// Inicializa la clase cuando el documento está listo.
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('sidebar')) {
        window.sidebarManager = new SidebarManager();
    }
});

// Exporta la clase.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SidebarManager;
}