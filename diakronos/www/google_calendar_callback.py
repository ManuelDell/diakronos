import frappe

no_cache = 1


def get_context(context):
    code  = frappe.form_dict.get("code")
    state = frappe.form_dict.get("state")
    error = frappe.form_dict.get("error")

    if error:
        context.redirect_url = f"/app/google-kalender-import?gcal_error={frappe.utils.quote(str(error))}"
        return

    if not code:
        context.redirect_url = "/app/google-kalender-import?gcal_error=no_code"
        return

    try:
        from diakronos.kronos.api.google_import import exchange_code
        exchange_code(code=code, state=state)
    except Exception as e:
        frappe.log_error(str(e), "google_calendar_callback")
        context.redirect_url = f"/app/google-kalender-import?gcal_error={frappe.utils.quote(str(e))}"
        return

    context.redirect_url = "/app/google-kalender-import?gcal_step=2"
