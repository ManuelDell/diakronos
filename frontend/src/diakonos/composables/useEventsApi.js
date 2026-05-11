function toLocalDateTimeString(date) {
  const pad = n => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
         `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function getCsrfToken() {
  return document.querySelector("meta[name=\"csrf-token\"]")?.content || ""
}

export function useEventsApi() {
  async function updateEvent(event, onSuccess, forceSeriesDetach = false) {
    if (!event?.id || !event.start) {
      console.error("useEventsApi.updateEvent: id und start erforderlich")
      return false
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
      if (!res.ok) throw new Error(await res.text())
      const result = await res.json()
      if (result.message?.success) {
        onSuccess?.()
        return true
      }
      return false
    } catch (err) {
      console.error("useEventsApi.updateEvent Fehler:", err)
      return false
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
      if (!res.ok) throw new Error(await res.text())
      const result = await res.json()
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
      if (!res.ok) throw new Error(await res.text())
      onSuccess?.()
      return true
    } catch (err) {
      console.error("useEventsApi.deleteEvent Fehler:", err)
      return false
    }
  }

  return { updateEvent, createEvent, deleteEvent }
}
