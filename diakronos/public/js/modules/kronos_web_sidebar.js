/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS SIDEBAR MODULE
 * ═══════════════════════════════════════════════════════════════
 * 
 * Handles all Sidebar-related functionality:
 * - Navigation items rendering
 * - Event delegation
 * - Active state management
 * - Responsive behavior
 * - FullCalendar Integration (resize handling)
 * 
 * Naming: sidebar_manage_navigation
 * Version: 1.0.2
 * 
 * Dependencies:
 * - element_extract_id.js (ElementExtractId class)
 * - kronos_web.js (KronosApp for coordination)
 * - fullcalendar.min.js (FullCalendar v6.1.16)
 */

class KronosSidebar {
    
    constructor() {
        this.config = {
            sidebarId: 'sidebar-wrapper',
            navId: 'sidebar-nav',
            menuToggleId: 'menu-toggle',
            wrapperId: 'wrapper',
            pageContentWrapperId: 'page-content-wrapper',  // ← NEU: Für Grid-Toggle
            darkmodeCheckboxId: 'darkmode-checkbox'
        };
        
        this.elements = {};
        this.state = {
            isOpen: false,
            currentActive: null
        };
        
        this.version = '1.0.2';
        console.log(`🎯 KronosSidebar v${this.version} - Konstruktor aufgerufen`);
    }



    /**
     * INIT: Starte Sidebar-Funktionalität
     */
    init() {
        try {
            console.log('📍 KronosSidebar.init() aufgerufen');
            
            this.cacheElements();
            this.setupNavigationItems();
            this.setupEventDelegation();
            this.restoreState();
            
            console.log('✅ KronosSidebar initialisiert');
        } catch (e) {
            console.error('❌ KronosSidebar.init() Error:', e);
        }
    }



    /**
     * Cache DOM Elements für Performance
     */
    cacheElements() {
        try {
            this.elements = {
                sidebar: document.getElementById(this.config.sidebarId),
                nav: document.getElementById(this.config.navId),
                menuToggle: document.getElementById(this.config.menuToggleId),
                wrapper: document.getElementById(this.config.wrapperId),
                pageContentWrapper: document.getElementById(this.config.pageContentWrapperId),  // ← NEU
                darkmodeCheckbox: document.getElementById(this.config.darkmodeCheckboxId)
            };
            
            // Validiere dass alle kritischen Elemente existieren
            const critical = ['sidebar', 'nav', 'menuToggle', 'wrapper', 'pageContentWrapper'];
            for (const el of critical) {
                if (!this.elements[el]) {
                    console.warn(`⚠️ Element ${el} nicht gefunden`);
                }
            }
            
            console.log('✅ DOM Elements gecacht');
        } catch (e) {
            console.error('❌ cacheElements Error:', e);
        }
    }



    /**
     * Setup Navigation Items
     * Füge Active-State-Handling hinzu
     */
    setupNavigationItems() {
        try {
            if (!this.elements.nav) {
                console.warn('⚠️ Nav Element nicht vorhanden, überspringe Navigation Setup');
                return;
            }
            
            const links = this.elements.nav.querySelectorAll('a');
            
            links.forEach((link, index) => {
                // ✅ Daten-Attribute für Identifikation
                link.setAttribute('data-nav-index', index);
                link.classList.add('nav-link');
                
                // ✅ Click Handler
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.setActiveNavItem(index);
                    
                    const href = link.getAttribute('href');
                    if (href && href !== '#') {
                        // Navigiere nach kurzer Delay für Animation
                        setTimeout(() => {
                            window.location.href = href;
                        }, 150);
                    }
                });
            });
            
            console.log(`✅ ${links.length} Navigation Items setup`);
        } catch (e) {
            console.error('❌ setupNavigationItems Error:', e);
        }
    }



    /**
     * Setup Event Delegation
     * Zentrale Event-Handler für Sidebar + FullCalendar Integration
     */
    setupEventDelegation() {
        try {
            const self = this;
            
            // 🎯 1. Menu Toggle - MIT FULLCALENDAR RESIZE!
            if (this.elements.menuToggle) {
                this.elements.menuToggle.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();  // ← Verhindere doppelte Events
                    
                    console.log('🔘 Menu Toggle geklickt');
                    
                    // Toggle das Sidebar Menu
                    this.toggleMenu();
                    
                    // 🔥 WICHTIG: Nach CSS-Transition das Calendar resizen!
                    // Die Grid ändert sich von "0 1fr" zu "250px 1fr"
                    // FullCalendar merkt das NICHT automatisch
                    setTimeout(() => {
                        if (window.kronosCalendar && window.kronosCalendar.calendar) {
                            console.log('🔄 FullCalendar updateSize() wird aufgerufen...');
                            window.kronosCalendar.calendar.updateSize();
                            console.log('✅ Calendar Size updated!');
                        }
                    }, 420);  // Warte bis CSS-Transition fertig (0.4s)
                });
            }
            
            // 🎯 2. Close on Link Click (mobile responsiveness)
            if (this.elements.nav) {
                this.elements.nav.addEventListener('click', () => {
                    // Schließe Menu auf mobil (wenn width < 768px)
                    if (window.innerWidth < 768) {
                        this.closeMenu();
                    }
                });
            }
            
            // 🎯 3. Close on Escape Key
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.state.isOpen) {
                    this.closeMenu();
                }
            });
            
            // 🎯 4. Close on Click außerhalb
            document.addEventListener('click', (e) => {
                const isClickInSidebar = this.elements.sidebar?.contains(e.target);
                const isClickOnToggle = this.elements.menuToggle?.contains(e.target);
                
                if (!isClickInSidebar && !isClickOnToggle && this.state.isOpen) {
                    this.closeMenu();
                }
            });
            
            console.log('✅ Event Delegation setup fertig (WITH FullCalendar Integration)');
        } catch (e) {
            console.error('❌ setupEventDelegation Error:', e);
        }
    }




    /**
     * TOGGLE MENU: Open/Close Sidebar
     */
    toggleMenu() {
        try {
            if (this.state.isOpen) {
                this.closeMenu();
            } else {
                this.openMenu();
            }
        } catch (e) {
            console.error('❌ toggleMenu Error:', e);
        }
    }



    /**
     * OPEN MENU
     */
    openMenu() {
        try {
            if (!this.elements.wrapper) return;
            
            this.elements.wrapper.classList.add('menuDisplayed');
            this.state.isOpen = true;
            
            // Speichere State
            localStorage.setItem('kronos-sidebar-open', 'true');
            
            console.log('📂 Sidebar OPENED');
        } catch (e) {
            console.error('❌ openMenu Error:', e);
        }
    }



    /**
     * CLOSE MENU
     */
    closeMenu() {
        try {
            if (!this.elements.wrapper) return;
            
            this.elements.wrapper.classList.remove('menuDisplayed');
            this.state.isOpen = false;
            
            // Speichere State
            localStorage.setItem('kronos-sidebar-open', 'false');
            
            console.log('📁 Sidebar CLOSED');
        } catch (e) {
            console.error('❌ closeMenu Error:', e);
        }
    }



    /**
     * SET ACTIVE NAV ITEM
     */
    setActiveNavItem(index) {
        try {
            if (!this.elements.nav) return;
            
            // Entferne alte Active-Klasse
            const activeLinks = this.elements.nav.querySelectorAll('a.active');
            activeLinks.forEach(link => {
                link.classList.remove('active');
            });
            
            // Setze neue Active-Klasse
            const link = this.elements.nav.querySelector(`a[data-nav-index="${index}"]`);
            if (link) {
                link.classList.add('active');
                this.state.currentActive = index;
                
                // Speichere State
                localStorage.setItem('kronos-sidebar-active', index);
                
                console.log(`✅ Active Nav Item: ${index}`);
            }
        } catch (e) {
            console.error('❌ setActiveNavItem Error:', e);
        }
    }



    /**
     * RESTORE STATE: Stelle gespeicherte Zustände wieder her
     */
    restoreState() {
        try {
            // ✅ 1. Restore Open/Close State
            const wasSidebarOpen = localStorage.getItem('kronos-sidebar-open');
            if (wasSidebarOpen === 'true') {
                this.openMenu();
            } else {
                this.closeMenu();
            }
            
            // ✅ 2. Restore Active Navigation Item
            const activeIndex = localStorage.getItem('kronos-sidebar-active');
            if (activeIndex !== null) {
                this.setActiveNavItem(parseInt(activeIndex));
            }
            
            console.log('✅ State restored');
        } catch (e) {
            console.error('❌ restoreState Error:', e);
        }
    }



    /**
     * GET SIDEBAR STATE
     * Öffentliche Methode zum Abfragen des States
     */
    getState() {
        return {
            isOpen: this.state.isOpen,
            currentActive: this.state.currentActive
        };
    }



    /**
     * UPDATE NAV ITEMS
     * Dynamisch neue Navigation Items hinzufügen
     */
    updateNavItems(items) {
        try {
            if (!this.elements.nav) {
                console.warn('⚠️ Nav Element nicht vorhanden');
                return;
            }
            
            // Leere existierende Items
            this.elements.nav.innerHTML = '';
            
            // Füge neue Items hinzu
            items.forEach((item, index) => {
                const li = document.createElement('li');
                const a = document.createElement('a');
                
                a.href = item.href || '#';
                a.textContent = item.label || 'Item';
                a.setAttribute('data-nav-index', index);
                a.classList.add('nav-link');
                
                // Click Handler
                a.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.setActiveNavItem(index);
                    
                    if (item.href && item.href !== '#') {
                        setTimeout(() => {
                            window.location.href = item.href;
                        }, 150);
                    }
                });
                
                li.appendChild(a);
                this.elements.nav.appendChild(li);
            });
            
            console.log(`✅ Navigation Items aktualisiert (${items.length} Items)`);
        } catch (e) {
            console.error('❌ updateNavItems Error:', e);
        }
    }



    /**
     * GET ACTIVE NAV ITEM
     */
    getActiveNavItem() {
        try {
            if (!this.elements.nav) return null;
            
            const activeLink = this.elements.nav.querySelector('a.active');
            if (!activeLink) return null;
            
            return {
                index: parseInt(activeLink.getAttribute('data-nav-index')),
                label: activeLink.textContent,
                href: activeLink.getAttribute('href')
            };
        } catch (e) {
            console.error('❌ getActiveNavItem Error:', e);
            return null;
        }
    }



    /**
     * HIGHLIGHT NAV ITEM
     * Für externe Calls (z.B. aus KronosCalendar)
     */
    highlightNavItem(label) {
        try {
            if (!this.elements.nav) return false;
            
            const links = this.elements.nav.querySelectorAll('a');
            for (let i = 0; i < links.length; i++) {
                if (links[i].textContent.toLowerCase().includes(label.toLowerCase())) {
                    this.setActiveNavItem(i);
                    return true;
                }
            }
            
            console.warn(`⚠️ Nav Item mit Label "${label}" nicht gefunden`);
            return false;
        } catch (e) {
            console.error('❌ highlightNavItem Error:', e);
            return false;
        }
    }



    /**
     * RESPONSIVE HANDLER
     * Schließe Menu bei responsive (z.B. auf mobile)
     */
    handleResponsive() {
        try {
            const isMobile = window.innerWidth < 768;
            
            if (isMobile && this.state.isOpen) {
                // Schließe auf Mobile
                this.closeMenu();
            }
            
            console.log(`📱 Responsive Handler: ${isMobile ? 'Mobile' : 'Desktop'}`);
        } catch (e) {
            console.error('❌ handleResponsive Error:', e);
        }
    }



    /**
     * CLEANUP: Entferne alle Event Listener
     * Wird von KronosApp.cleanup() aufgerufen
     */
    cleanup() {
        try {
            console.log('🧹 KronosSidebar cleanup...');
            
            // ✅ Entferne Event Listener von Links
            if (this.elements.nav) {
                const links = this.elements.nav.querySelectorAll('a');
                links.forEach(link => {
                    // Klone und ersetze um alle Listener zu entfernen
                    const newLink = link.cloneNode(true);
                    link.parentNode.replaceChild(newLink, link);
                });
            }
            
            // ✅ Entferne Menu Toggle Listener
            // (Wird automatisch durch Event Listener Referenzen entfernt)
            
            // ✅ Lösche State
            this.state = {
                isOpen: false,
                currentActive: null
            };
            
            // ✅ Lösche Elemente
            this.elements = {};
            
            console.log('✅ KronosSidebar cleanup fertig');
        } catch (e) {
            console.error('❌ cleanup Error:', e);
        }
    }



    /**
     * GET VERSION
     */
    getVersion() {
        return this.version;
    }
}



/**
 * Export für globale Nutzung
 */
window.KronosSidebar = KronosSidebar;
console.log('✅ Sidebar Module geladen');
