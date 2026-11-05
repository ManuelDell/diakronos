import { ref, computed } from 'vue'
import { useImpersonation } from './useImpersonation.js'
import { anzeigename } from './anzeigename.mjs'

const boot = window.__DIakonosBOOT || {}

// UX2f2b: Der Zustand wird für den Prüfstand der Formulare (jsdom-Mount)
// exportiert — `is_admin` kommt EINMAL beim Modulstart aus dem Boot-Objekt,
// ohne diesen Weg ließe sich das Bearbeiten-Formular nicht testen. Im Betrieb
// liest ihn niemand von außen.
const state = ref({
    user: {
        fullname: boot.user_fullname || '',
        email:    boot.user_email || '',
        image:    boot.user_image || '',
        isAdmin:  boot.is_admin || false,
    },
    mitglied: boot.mitglied || null,
    modules:  boot.modules || [],
    // DM1: Dev-Modus nur fuer Admins/Tester und nur bei eingeschaltetem
    // Schalter (der Server liefert beides im Boot-Objekt).
    istTester: Boolean(boot.ist_tester),
    devmodeAn: Boolean(boot.devmode),
    // MAIL-1b (N3): „System Manager“ ist die Rolle, die den Mailversand
    // einstellen darf. Der Server entscheidet (`boot.roles`); hier wird nur
    // ausgeblendet, was er ohnehin verweigert.
    istSystemManager: (boot.roles || []).includes('System Manager'),
    // WEB-3: die vollständige Rollenliste der Sitzung (`Has Role`) — dieselbe
    // Quelle, aus der der Server `is_admin` ableitet. Menüpunkte mit eigener
    // Rollenliste („Website“) werden damit ausgeblendet, nicht anders geprüft.
    rollen: Array.isArray(boot.roles) ? boot.roles : [],
})

export { state as __zustand };

const imp = useImpersonation()

const user = computed(() => {
    if (imp.isActive.value) {
        return { ...state.value.user, fullname: imp.fullName.value, isAdmin: false }
    }
    return state.value.user
})

const mitglied = computed(() => {
    if (imp.isActive.value) {
        const parts = imp.fullName.value.split(' ')
        return {
            name:     imp.mitglied.value,
            vorname:  parts[0] || '',
            nachname: parts.slice(1).join(' ') || '',
            status:   '',
        }
    }
    return state.value.mitglied
})

const isAdmin = computed(() => imp.isActive.value ? false : state.value.user.isAdmin)
const hasMitglied = computed(() => !!mitglied.value)
// UXD-R23: „Gast“ ist der Mitgliedsstatus ohne Konto-Rechte. Die Regel stand
// dreimal wortgleich in AppSidebar, AppBottomNav und würde sonst in
// QuickLinksWidget ein viertes Mal entstehen — hier EINMAL.
const istGast = computed(() => !isAdmin.value && mitglied.value?.status === 'Gast')
// DM1: Server-Auskunft über Dev-Modus und Tester-Rolle (bleibt serverseitig
// entschieden; hier nur für das Ausblenden).
const istTester = computed(() => imp.isActive.value ? false : state.value.istTester)
const devmodeAn = computed(() => state.value.devmodeAn)
// MAIL-1b: während einer Identitätsübernahme gelten die Rechte des Kontos,
// nicht die des Zuschauers (wie bei `isAdmin`).
const istSystemManager = computed(() =>
    imp.isActive.value ? false : state.value.istSystemManager)
// WEB-3: während einer Identitätsübernahme gelten die Rechte des Kontos, nicht
// die des Zuschauers — wie bei `isAdmin`/`istSystemManager`. Ohne Rollen sieht
// der Nutzer keine rollengeschützten Einträge (fail closed).
const rollen = computed(() => imp.isActive.value ? [] : state.value.rollen)

/**
 * OP-HANDY-25: Anzeigename für Begrüßung und Avatar.
 * Regel in `anzeigename.mjs` (ohne Vue prüfbar) — hier nur die Bindung an die
 * reaktiven Quellen.
 */
const anzeigeName = computed(() => anzeigename(mitglied.value, user.value?.fullname))

export function useSession() {
    return {
        user,
        mitglied,
        modules: computed(() => state.value.modules),
        isAdmin,
        hasMitglied,
        istGast,
        istTester,
        devmodeAn,
        istSystemManager,
        rollen,
        anzeigeName,
    }
}
