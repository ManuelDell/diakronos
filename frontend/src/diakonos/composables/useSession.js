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
})

const isAdmin = computed(() => state.value.user.isAdmin)
const hasMitglied = computed(() => !!state.value.mitglied)

export function useSession() {
    return {
        user: computed(() => state.value.user),
        mitglied: computed(() => state.value.mitglied),
        modules: computed(() => state.value.modules),
        isAdmin,
        hasMitglied,
    }
}
