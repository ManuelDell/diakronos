# diakronos/caldav/auth.py – Basic Auth gegen Frappe-Nutzerdatenbank

import base64


def get_authenticated_user(request):
    """
    Liest den Authorization-Header, prüft Credentials gegen Frappe.
    Gibt den Frappe-Username (E-Mail) zurück oder None bei Fehler.
    """
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Basic '):
        return None

    try:
        decoded  = base64.b64decode(auth[6:]).decode('utf-8')
        username, password = decoded.split(':', 1)

        from frappe.utils.password import check_password
        check_password(username, password)   # wirft Exception bei falschem PW
        return username

    except Exception:
        return None
