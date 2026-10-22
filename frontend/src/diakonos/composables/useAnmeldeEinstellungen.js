import { ref, computed } from 'vue'
import { apiCall } from './useApi.js'

const API = 'diakronos.anmeldung.'

/** N8: nur ein Schreibaufruf; fehlgeschlagenes Laden bleibt nicht bedienbar. */
export function useAnmeldeEinstellungen() {
  const laedt = ref(false)
  const speichert = ref(false)
  const geladen = ref(false)
  const oidcAktiv = ref(false)
  const modus = ref('abweisen')
  const adminUeberGruppen = ref(false)
  const rollen = ref([])
  const zuordnungen = ref([])
  const fehler = ref('')
  const erfolg = ref('')
  const zeilenFehler = ref({})
  const bedienbar = computed(() => geladen.value && oidcAktiv.value && !laedt.value && !speichert.value)

  async function laden() {
    laedt.value = true
    geladen.value = false
    fehler.value = ''
    try {
      const res = await apiCall(API + 'anmeldung_get_einstellungen', {})
      const d = res.message || res
      oidcAktiv.value = d.oidc_aktiv === true
      modus.value = d.unbekannte_nutzer || 'abweisen'
      adminUeberGruppen.value = d.admin_ueber_gruppen === true
      rollen.value = d.rollen || []
      zuordnungen.value = (d.rollen_zuordnung || []).map(z => ({ gruppe: z.gruppe, rolle: z.rolle }))
      geladen.value = true
    } catch (e) {
      fehler.value = e.message || 'Die Anmeldeeinstellungen konnten nicht geladen werden.'
    } finally {
      laedt.value = false
    }
  }

  async function speichern() {
    if (!bedienbar.value) return false
    zeilenFehler.value = {}
    fehler.value = ''
    erfolg.value = ''
    const gesehen = new Set()
    for (const [i, z] of zuordnungen.value.entries()) {
      const gruppe = z.gruppe.trim()
      if (!gruppe || !z.rolle) zeilenFehler.value[i] = 'Bitte Authentik-Gruppe und Rolle angeben.'
      else if (!rollen.value.includes(z.rolle)) zeilenFehler.value[i] = 'Bitte eine verfügbare Rolle wählen.'
      else if (gesehen.has(JSON.stringify([gruppe, z.rolle]))) zeilenFehler.value[i] = 'Diese Zuordnung ist doppelt vorhanden.'
      gesehen.add(JSON.stringify([gruppe, z.rolle]))
    }
    if (Object.keys(zeilenFehler.value).length) {
      fehler.value = 'Bitte prüfe die markierten Zuordnungen. Es wurde nichts gespeichert.'
      return false
    }
    speichert.value = true
    try {
      await apiCall(API + 'anmeldung_speichern', {
        modus: modus.value,
        admin_ueber_gruppen: adminUeberGruppen.value,
        zuordnungen: zuordnungen.value.map(z => ({ gruppe: z.gruppe.trim(), rolle: z.rolle })),
      })
      erfolg.value = 'Anmeldeeinstellungen gespeichert.'
      return true
    } catch (e) {
      fehler.value = e.message || 'Speichern fehlgeschlagen. Deine Eingaben bleiben erhalten.'
      return false
    } finally {
      speichert.value = false
    }
  }

  return { laedt, speichert, geladen, oidcAktiv, modus, adminUeberGruppen, rollen,
    zuordnungen, fehler, erfolg, zeilenFehler, bedienbar, laden, speichern }
}
