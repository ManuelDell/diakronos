// modal_core.js – Basis für alle Modals

class DiakronosModalBase {
    static createBase(options = {}) {
        const {
            title = 'Dialog',
            width = 'min(90vw, 620px)',
            maxHeight = '85vh',
            className = ''
        } = options;

        const overlay = document.createElement('div');
        overlay.className = `diakronos-overlay ${className}`;

        const dialog = document.createElement('div');
        dialog.className = 'diakronos-dialog';
        dialog.style.maxWidth = width;
        dialog.style.maxHeight = maxHeight;

        const header = document.createElement('div');
        header.className = 'diakronos-header';
        const h2 = document.createElement('h2');
        h2.textContent = title;
        header.appendChild(h2);

        const closeBtn = document.createElement('button');
        closeBtn.className = 'diakronos-close-red';
        closeBtn.textContent = '×';
        closeBtn.onclick = () => overlay.remove();
        header.appendChild(closeBtn);

        dialog.appendChild(header);

        const content = document.createElement('div');
        content.className = 'diakronos-content';
        dialog.appendChild(content);

        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        const close = () => overlay.remove();
        overlay.onclick = e => { if (e.target === overlay) close(); };
        document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); }, { once: true });

        return { overlay, dialog, content, close };
    }
}

// ✅ ES6 Export statt window Deklaration
export { DiakronosModalBase };
console.log('modal_core.js geladen – DiakronosModalBase exportiert');
