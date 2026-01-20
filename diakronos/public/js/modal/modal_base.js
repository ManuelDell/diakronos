/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS MODAL - BASE CLASS
 * ═══════════════════════════════════════════════════════════════
 * Basis-Funktionen für alle Modal-Dialoge
 */

class KronosModalBase {
    
    /**
     * 🏗️ CREATE MODAL STRUCTURE
     * Erstellt Modal und Dialog Container
     */
    static createModal(options = {}) {
        const {
            id = 'modal-' + Date.now(),
            width = '500px',
            maxHeight = '80vh'
        } = options;
        
        const modal = document.createElement('div');
        modal.id = id;
        modal.style.cssText = KronosModalHelpers.getModalStyle();
        
        const dialog = document.createElement('div');
        dialog.style.cssText = KronosModalHelpers.getDialogStyle() + `
            min-width: ${width};
            max-height: ${maxHeight};
            overflow-y: auto;
        `;
        
        modal.appendChild(dialog);
        document.body.appendChild(modal);
        
        return { modal, dialog };
    }
    
    /**
     * 🎛️ SETUP CLOSE HANDLERS
     * ESC-Taste und Click außerhalb
     */
    static setupCloseHandlers(modalElement, closeCallback) {
        const closeModal = () => {
            KronosModalHelpers.closeModal(modalElement, closeCallback);
        };
        
        // Click außerhalb schließen
        modalElement.addEventListener('click', (e) => {
            if (e.target === modalElement) {
                closeModal();
            }
        });
        
        // ESC-Taste
        const escListener = (e) => {
            if (e.key === 'Escape') {
                closeModal();
            }
        };
        document.addEventListener('keydown', escListener);
        
        // Return für externe Nutzung
        return { closeModal, escListener };
    }
    
    /**
     * 🔘 CREATE BUTTON
     */
    static createButton(options = {}) {
        const {
            id = '',
            text = 'Button',
            primary = false,
            onClick = () => {}
        } = options;
        
        const button = document.createElement('button');
        if (id) button.id = id;
        button.textContent = text;
        button.style.cssText = `
            padding: 10px 20px;
            border: ${primary ? 'none' : '1px solid #dadce0'};
            border-radius: 4px;
            background: ${primary ? '#1f73e6' : '#f5f5f5'};
            color: ${primary ? 'white' : '#202124'};
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
        `;
        
        button.addEventListener('click', onClick);
        
        // Hover Effect
        button.addEventListener('mouseenter', () => {
            button.style.backgroundColor = primary ? '#1967d2' : '#efefef';
        });
        button.addEventListener('mouseleave', () => {
            button.style.backgroundColor = primary ? '#1f73e6' : '#f5f5f5';
        });
        
        return button;
    }
    
    /**
     * 🏷️ CREATE FORM FIELD
     */
    static createFormField(options = {}) {
        const {
            label = 'Field',
            type = 'text',
            id = '',
            value = '',
            placeholder = '',
            required = false
        } = options;
        
        const container = document.createElement('div');
        container.style.cssText = 'margin-bottom: 16px;';
        
        const labelEl = document.createElement('label');
        labelEl.style.cssText = 'display: block; margin-bottom: 6px; font-weight: 500; color: #202124;';
        labelEl.textContent = label + (required ? ' *' : '');
        
        let inputEl;
        
        if (type === 'textarea') {
            inputEl = document.createElement('textarea');
            inputEl.style.cssText = `
                width: 100%;
                padding: 10px;
                border: 1px solid #dadce0;
                border-radius: 4px;
                font-size: 14px;
                font-family: inherit;
                box-sizing: border-box;
                height: 80px;
                resize: vertical;
            `;
            inputEl.value = value;
        } else if (type === 'select') {
            inputEl = document.createElement('select');
            inputEl.style.cssText = `
                width: 100%;
                padding: 10px;
                border: 1px solid #dadce0;
                border-radius: 4px;
                font-size: 14px;
                box-sizing: border-box;
            `;
        } else {
            inputEl = document.createElement('input');
            inputEl.type = type;
            inputEl.style.cssText = `
                width: 100%;
                padding: 10px;
                border: 1px solid #dadce0;
                border-radius: 4px;
                font-size: 14px;
                font-family: inherit;
                box-sizing: border-box;
            `;
            inputEl.value = value;
            if (placeholder) inputEl.placeholder = placeholder;
        }
        
        if (id) inputEl.id = id;
        
        container.appendChild(labelEl);
        container.appendChild(inputEl);
        
        return { container, inputEl };
    }
    
    /**
     * 📝 CREATE HEADER
     */
    static createHeader(options = {}) {
        const {
            emoji = '',
            title = 'Dialog',
            subtitle = ''
        } = options;
        
        const container = document.createElement('div');
        container.style.cssText = 'margin-bottom: 24px;';
        
        const h2 = document.createElement('h2');
        h2.style.cssText = 'margin: 0 0 8px 0; font-size: 18px; color: #202124;';
        h2.textContent = `${emoji} ${title}`;
        
        container.appendChild(h2);
        
        if (subtitle) {
            const p = document.createElement('p');
            p.style.cssText = 'margin: 0; color: #999; font-size: 12px;';
            p.textContent = subtitle;
            container.appendChild(p);
        }
        
        return container;
    }
    
    /**
     * 🎯 CREATE BUTTON GROUP
     */
    static createButtonGroup(buttons = []) {
        const container = document.createElement('div');
        container.style.cssText = 'display: flex; gap: 10px;';
        
        buttons.forEach(btn => {
            container.appendChild(btn);
        });
        
        return container;
    }
}

// Export
window.KronosModalBase = KronosModalBase;
console.log('✅ Modal Base Class geladen');
