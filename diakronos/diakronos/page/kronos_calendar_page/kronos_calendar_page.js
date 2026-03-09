frappe.pages['kronos_calendar_page'].on_page_load = function(wrapper) {
    console.log('🚀 kronos-calendar_page.on_page_load: START');

    // =========================================================================
    // Sequential Load der Builder-Dateien (als globale Funktionen)
    // =========================================================================
    const scriptUrls = [
        '/assets/diakronos/js/builder/cleanup_dom_structure.js',
        '/assets/diakronos/js/builder/overlay_fix_msgprint.js',
        '/assets/diakronos/js/builder/header_build_elements.js',
        '/assets/diakronos/js/builder/sidebar_build_elements.js',
        '/assets/diakronos/js/builder/calendar_build_init.js',
        '/assets/diakronos/js/builder/module_load_functions.js'
    ];

    const loadScriptsSequential = async () => {
        for (const url of scriptUrls) {
            await new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = url;
                script.type = 'text/javascript'; // Globale Funktionen, kein module
                script.async = false;
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            });
        }
        console.log('✅ Alle Builder-Dateien geladen – Funktionen global verfügbar');
    };

    (async () => {
        try {
            await loadScriptsSequential();

            // Zuerst alle Module laden (FullCalendar muss VOR calendar_build_init da sein!)
            console.log('🔄 Lade Module in Reihenfolge...');
            if (window.module_load_modal) await window.module_load_modal();
            if (window.module_load_fullcalendar) await window.module_load_fullcalendar(); // ← JETZT vor Init!
            if (window.module_load_kronos_bundle) await window.module_load_kronos_bundle();

            // Jetzt Cleanup & Struktur bauen
            if (window.cleanup_dom_structure) window.cleanup_dom_structure();
            if (window.overlay_fix_msgprint) window.overlay_fix_msgprint();

            const appContainer = document.querySelector('.kronos-app-container');

            if (window.header_build_elements) window.header_build_elements(appContainer);

            const mainContentEl = document.querySelector('.kronos-main-content');

            if (window.sidebar_build_elements) window.sidebar_build_elements(mainContentEl);

            // Kalender-Init erst NACH FullCalendar!
            if (window.calendar_build_init) await window.calendar_build_init(mainContentEl);

            console.log('🎉 Page vollständig initialisiert');
        } catch (error) {
            console.error('❌ KRITISCHER FEHLER:', error);
            frappe.msgprint({
                message: `Kritischer Fehler: ${error.message}`,
                indicator: 'red'
            });
        }
    })();
};