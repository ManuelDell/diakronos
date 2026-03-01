/**
 * ═══════════════════════════════════════════════════════════════
 * ELEMENT - EXTRACT ID
 * ═══════════════════════════════════════════════════════════════
 * Utility für Element-ID Extraction aus FullCalendar Events
 * ROBUST gegen verschiedene Quellen und Fehler
 */

class ElementExtractId {
    /**
     * Extrahiere Element-ID aus FullCalendar event object
     * Versucht mehrere Quellen, bis eine valide ID gefunden wird
     */
    static fromEvent(event) {
        if (!event) {
            console.warn('⚠️ ElementExtractId.fromEvent: event ist null/undefined');
            return undefined;
        }

        // Versuche mehrere Quellen in Priorität
        const sources = [
            { name: 'extendedProps.name', value: event.extendedProps?.name },
            { name: 'id', value: event.id },
            { name: 'extendedProps.id', value: event.extendedProps?.id },
            { name: '_id', value: event._id }
        ];

        for (const source of sources) {
            if (source.value && 
                source.value !== 'undefined' && 
                source.value !== 'null' && 
                source.value !== '' && 
                typeof source.value === 'string') {
                
                console.log(`✅ ElementExtractId: ID aus "${source.name}" = "${source.value}"`);
                return source.value;
            }
        }

        console.error('❌ ElementExtractId: Keine valide ID gefunden!', event);
        return undefined;
    }

    /**
     * Validiere ob eine ID gültig ist
     */
    static isValid(id) {
        return (
            id && 
            id !== 'undefined' && 
            id !== 'null' && 
            id !== '' && 
            typeof id === 'string' &&
            id.length > 0
        );
    }

    /**
     * Debug: Zeige alle verfügbaren ID-Quellen
     */
    static debug(event) {
        console.group('🔍 Element ID Extraction Debug');
        console.log('Event Object:', event);
        console.log('─── ID Quellen ───');
        console.log('event.id:', event?.id);
        console.log('event.extendedProps?.name:', event?.extendedProps?.name);
        console.log('event.extendedProps?.id:', event?.extendedProps?.id);
        console.log('event._id:', event?._id);
        console.log('─── Resultat ───');
        console.log('Resolved ID:', this.fromEvent(event));
        console.log('Is Valid:', this.isValid(this.fromEvent(event)));
        console.groupEnd();
    }

    /**
     * Sichere ID-Extraktion mit Error-Handling
     */
    static safe(event, fallbackId = null) {
        try {
            const id = this.fromEvent(event);
            return this.isValid(id) ? id : fallbackId;
        } catch (e) {
            console.error('❌ Error in ElementExtractId.safe():', e);
            return fallbackId;
        }
    }
}

export { ElementExtractId };
console.log('✅ ElementExtractId Modul geladen');
