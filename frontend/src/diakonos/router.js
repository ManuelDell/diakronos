import { ref, computed, shallowRef } from 'vue'

// Lazy-loaded page components
const pages = {
    Home:            () => import('./pages/Home.vue'),
    Mitglieder:      () => import('./pages/Mitglieder.vue'),
    MitgliedDetail:  () => import('./pages/MitgliedDetail.vue'),
    GruppeDetail:    () => import('./pages/GruppeDetail.vue'),
    Gruppen:         () => import('./pages/Gruppen.vue'),
    Adressbuch:      () => import('./pages/Adressbuch.vue'),
    Kalender:        () => import('./pages/Kalender.vue'),
    Dienstplan:      () => import('./pages/Dienstplan.vue'),
    Anmeldungen:     () => import('./pages/Anmeldungen.vue'),
    Organigramm:     () => import('./pages/Organigramm.vue'),
    Statistik:       () => import('./pages/Statistik.vue'),
    Dsgvo:           () => import('./pages/Dsgvo.vue'),
    Profile:         () => import('./pages/Profile.vue'),
    Ressourcen:      () => import('./pages/Ressourcen.vue'),
    Beitraege:       () => import('./pages/Beitraege.vue'),
    Wiki:            () => import('./pages/Wiki.vue'),
}

// Exact routes
const routeMap = {
    '#/':              'Home',
    '#/mitglieder':    'Mitglieder',
    '#/gruppen':       'Gruppen',
    '#/adressbuch':    'Adressbuch',
    '#/kalender':      'Kalender',
    '#/dienstplan':    'Dienstplan',
    '#/anmeldungen':   'Anmeldungen',
    '#/organigramm':   'Organigramm',
    '#/statistik':     'Statistik',
    '#/dsgvo':         'Dsgvo',
    '#/profile':       'Profile',
    '#/ressourcen':    'Ressourcen',
    '#/beitraege':     'Beitraege',
    '#/wiki':          'Wiki',
}

// Dynamic routes: pattern regex → page name
const dynamicRoutes = [
    { pattern: /^#\/mitglied\/(.+)$/, page: 'MitgliedDetail', param: 'id' },
    { pattern: /^#\/gruppe\/(.+)$/, page: 'GruppeDetail', param: 'id' },
]

const currentHash = ref(window.location.hash || '#/')
const currentPageName = computed(() => {
    const exact = routeMap[currentHash.value]
    if (exact) return exact
    for (const r of dynamicRoutes) {
        if (r.pattern.test(currentHash.value)) return r.page
    }
    return 'Home'
})
const currentComponent = shallowRef(null)
const currentRouteParams = ref({})

// Route guards (simple)
const beforeEachGuards = []

export function onBeforeEach(fn) {
    beforeEachGuards.push(fn)
}

function resolveRoute() {
    const hash = window.location.hash || '#/'
    currentHash.value = hash

    // Extract params from dynamic routes
    let pageName = routeMap[hash]
    let params = {}
    if (!pageName) {
        for (const r of dynamicRoutes) {
            const m = hash.match(r.pattern)
            if (m) {
                pageName = r.page
                params[r.param] = decodeURIComponent(m[1])
                break
            }
        }
    }
    pageName = pageName || 'Home'
    currentRouteParams.value = params

    // Run guards
    for (const guard of beforeEachGuards) {
        const result = guard({ to: hash, name: pageName, params })
        if (result === false) return
        if (typeof result === 'string') {
            navigate(result)
            return
        }
    }

    const loader = pages[pageName] || pages.Home
    loader().then(mod => {
        currentComponent.value = mod.default
    }).catch(() => {
        currentComponent.value = null
    })
}

export function navigate(path) {
    if (typeof path !== 'string') {
        console.warn('[router] navigate expected string, got', typeof path, path)
        path = String(path || '')
    }
    if (!path.startsWith('#')) path = '#' + path
    window.location.hash = path
}

export function getRouteParam(key) {
    return currentRouteParams.value[key]
}

export function getRouteParams() {
    return { ...currentRouteParams.value }
}

// Listen to hash changes
window.addEventListener('hashchange', resolveRoute)

// Initial resolve
resolveRoute()

export { currentHash, currentPageName, currentComponent }
