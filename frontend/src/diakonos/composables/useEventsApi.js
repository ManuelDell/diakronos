import { apiAntwortPruefen } from './useApi.js'
function toLocalDateTimeString(date) {
  const pad = n => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
         `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function getCsrfToken() {
  return document.querySelector("meta[name=\"csrf-token\"]")?.content || ""
}

/**
 * K-A (R-P1-8): EINEN eigenen Termin laden — auch wenn er abgelehnt wurde.
 *
 * Abgelehnte Termine sind bewusst aus ALLEN Listen heraus (W-A); der
 * Antragsteller braucht aber den Ablehnungsgrund. Der Server liefert den
 * einzelnen, ausdruecklich angefragten Termin nur an den Antragsteller
 * (`Element.owner`) oder einen Moderator des Kalenders.
 *
 * @param {string} elementId — Kennung des Termins
 * @returns {Promise<Object|null>} Termin mit `ablehnungs_grund`, sonst null
 */
export async function getMeinTermin(elementId) {
  if (!elementId) return null
  try {
    const res = await fetch(
      "/api/method/diakronos.kronos.api.calendar_get.get_mein_termin",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-Frappe-CSRF-Token": getCsrfToken()
        },
        body: JSON.stringify({ element_id: elementId })
      }
    )
    const daten = await apiAntwortPruefen(res)
    return daten?.message ?? null
  } catch (err) {
    console.error("getMeinTermin Fehler:", err)
    return null
  }
}

export function useEventsApi() {
  /**
   * Verschieben/Groessenänderung eines Termins speichern.
   *
   * P1-1b: Liefert das Ergebnis der Serverantwort zurueck (`{ ok, wartet }`),
   * damit die Oberflaeche melden kann, dass eine Aenderung an einem
   * festgelegten Termin als offener Vorschlag auf die Moderation wartet. Ein
   * reines `true` verschwieg diesen Fall — der Termin sprang sichtbar zurueck.
   */
  async function updateEvent(event, onSuccess, forceSeriesDetach = false) {
    if (!event?.id || !event.start) {
      console.error("useEventsApi.updateEvent: id und start erforderlich")
      return { ok: false, wartet: false }
    }
    const effectiveEnd = event.end || event.start
    const props = event.extendedProps || {}
    // Get new resource after drag (resource timeline view)
    const newRessource = (event.getResources?.() || [])[0]?.id 
      || props.ressource 
      || ""
    try {
      const res = await fetch("/api/method/diakronos.kronos.api.event_crud.save_event", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-Frappe-CSRF-Token": getCsrfToken()
        },
        body: JSON.stringify({
          name:             event.id,
          element_name:     event.title,
          element_start:    toLocalDateTimeString(event.start),
          element_end:      toLocalDateTimeString(effectiveEnd),
          element_calendar: props.element_calendar || "",
          ressource:        newRessource,
          all_day:          event.allDay || false,
          description:      props.description || "",
          element_category: props.element_category || "",
          status:           props.status || "Festgelegt",
          series_id:        forceSeriesDetach ? "" : (props.series_id || "")
        })
      })
      const result = await apiAntwortPruefen(res)
      const nachricht = result.message || {}
      if (nachricht.success) {
        onSuccess?.()
        return { ok: true, wartet: Boolean(nachricht.aenderung_wartet), meldung: nachricht.meldung || "" }
      }
      return { ok: false, wartet: false }
    } catch (err) {
      console.error("useEventsApi.updateEvent Fehler:", err)
      return { ok: false, wartet: false }
    }
  }

  async function createEvent(title, start, end, element_calendar, onSuccess, extraFields = {}) {
    if (!title?.trim() || !start || !element_calendar) {
      console.error("useEventsApi.createEvent: title, start, element_calendar erforderlich")
      return null
    }
    const startStr = start instanceof Date ? toLocalDateTimeString(start) : start
    const endStr   = end instanceof Date   ? toLocalDateTimeString(end)   : (end || startStr)
    try {
      const res = await fetch("/api/method/diakronos.kronos.api.event_crud.create_event", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-Frappe-CSRF-Token": getCsrfToken()
        },
        body: JSON.stringify({
          element_name:     title,
          element_calendar: element_calendar,
          element_start:    startStr,
          element_end:      endStr,
          all_day:          extraFields.all_day || false,
          description:      extraFields.description || "",
          element_category: extraFields.element_category || "",
          status:           extraFields.status || "Festgelegt",
          series_id:        extraFields.series_id || "",
          series_end:       extraFields.series_end || "",
          repeat_interval:  extraFields.repeat_interval || "",
        })
      })
      const result = await apiAntwortPruefen(res)
      if (result.message?.id) {
        onSuccess?.(result.message.id)
        return result.message.id
      }
      return null
    } catch (err) {
      console.error("useEventsApi.createEvent Fehler:", err)
      return null
    }
  }

  async function deleteEvent(eventId, onSuccess) {
    if (!eventId) return false
    try {
      const res = await fetch(`/api/resource/Element/${eventId}`, {
        method: "DELETE",
        headers: { "X-Frappe-CSRF-Token": getCsrfToken() }
      })
      await apiAntwortPruefen(res)
      onSuccess?.()
      return true
    } catch (err) {
      console.error("useEventsApi.deleteEvent Fehler:", err)
      return false
    }
  }

  return { updateEvent, createEvent, deleteEvent }
}
