function loadDiakronosStyle(url) {
	if (document.querySelector('link[href*="' + url + '"')) return;
	const link = document.createElement('link');
	link.rel = 'stylesheet';
	link.href = url + '?v=' + Date.now();
	document.head.appendChild(link);
}

frappe.pages['dsgvo-uebersicht'].on_page_load = async function (wrapper) {
	frappe.ui.make_app_page({ parent: wrapper, title: 'DSGVO-Übersicht', single_column: true });
	wrapper.page.main.html(
		'<div style="padding:60px;text-align:center;color:#9ca3af;font-size:.9rem">Wird geladen…</div>'
	);
	loadDiakronosStyle('/assets/diakronos/frontend/style.css');
	loadDiakronosStyle('/assets/diakronos/frontend/admin.css');
	const { mountDsgvo } = await import('/assets/diakronos/frontend/admin.js?v=' + Date.now());
	wrapper.page.main.empty();
	mountDsgvo(wrapper.page.main[0]);
};

frappe.pages['dsgvo-uebersicht'].on_page_show = function () {
	document.dispatchEvent(new CustomEvent('diakonos:page-show', { detail: 'dsgvo' }));
};
