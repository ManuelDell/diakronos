import { ref, computed } from 'vue'

const boot = window.__DIakonosBOOT || {}

const state = ref({
    user: {
        fullname: boot.user_fullname || '',
        email:    boot.user_email || '',
        image:    boot.user_image || '',
        isAdmin:  boot.is_admin || false,
    },
    mitglied: boot.mitglied || null,
    modules:  boot.modules || [],
    adminMode: false,
    adminModeReason: '',
    adminModeExpiresAt: null,
})

const isAdmin = computed(() => state.value.user.isAdmin)
const isAdminMode = computed(() => {
    if (!isAdmin.value) return false
    if (!state.value.adminMode) return false
    if (state.value.adminModeExpiresAt && Date.now() > state.value.adminModeExpiresAt) {
        state.value.adminMode = false
        state.value.adminModeReason = ''
        return false
    }
    return true
})
const hasMitglied = computed(() => !!state.value.mitglied)

function enterAdminMode(reason) {
    if (!isAdmin.value) return false
    state.value.adminMode = true
    state.value.adminModeReason = reason
    // 30 Minuten TTL
    state.value.adminModeExpiresAt = Date.now() + 30 * 60 * 1000
    return true
}

function exitAdminMode() {
    state.value.adminMode = false
    state.value.adminModeReason = ''
    state.value.adminModeExpiresAt = null
}

function extendAdminMode() {
    if (state.value.adminMode) {
        state.value.adminModeExpiresAt = Date.now() + 30 * 60 * 1000
    }
}

export function useSession() {
    return {
        user: computed(() => state.value.user),
        mitglied: computed(() => state.value.mitglied),
        modules: computed(() => state.value.modules),
        isAdmin,
        isAdminMode,
        hasMitglied,
        enterAdminMode,
        exitAdminMode,
        extendAdminMode,
    }
}
