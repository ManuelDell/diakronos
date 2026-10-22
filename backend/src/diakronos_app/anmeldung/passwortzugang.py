"""N5: Passwort-Links sind 256-Bit-Geheimnisse, gespeichert wird nur SHA-256.

Kein Versand. Ein Token pro Konto; Ersetzen und Einlösen sperren dieselbe
Zeile. Das Startpasswort gibt niemals eine Vollsitzung, sondern nur einen
kurzen, zweckgebundenen Passwort-Link. CalDAV bleibt bis zum Wechsel gesperrt.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from sqlalchemy import select

from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.models.passwortzugang import Passwortzugang


def _jetzt():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def pruefe_passwort(passwort):
    if not isinstance(passwort, str) or not 8 <= len(passwort) <= 1024:
        raise ValidationError("Das Passwort muss zwischen 8 und 1024 Zeichen haben.")


def wechsel_noetig(user):
    from diakronos_app.db import lesesitzung
    with lesesitzung() as sess:
        row = sess.get(Passwortzugang, user)
        return bool(row and row.wechsel_noetig)


def wechsel_noetig_gecacht(user):
    """Middleware: gleicher kurzer Redis-Cache und Widerruf wie Benutzerstatus.

    Fehler verweigern lokale Sitzungen. SSO-Sitzungen benötigen diese Prüfung
    nicht. Schreibwege widerrufen nach Commit ohnehin alle Sitzungen.
    """
    from diakronos_app.frappe_compat import benutzer_status as b
    key = b._key(user) + ':erstwechsel'
    try:
        client = b._client()
        wert = client.get(key)
        if wert is None:
            noetig = wechsel_noetig(user)
            client.set(key, '1' if noetig else '0', ex=b._ttl())
            return noetig
        return wert in ('1', b'1')
    except Exception:
        return True


def startpasswort_markieren(sess, user):
    row = sess.get(Passwortzugang, user, with_for_update=True)
    if row is None:
        row = Passwortzugang(user=user)
        sess.add(row)
    row.wechsel_noetig = True
    row.token_hash = None
    row.gueltig_bis = None


def link_erzeugen(user, *, erstwechsel=False):
    """Aufrufer prüft Adminrecht oder korrektes Startpasswort VOR diesem Aufruf."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import User
    from diakronos_app.frappe_compat.benutzer_status import konto_ist_aktiv
    kennung = secrets.token_urlsafe(32)
    bis = _jetzt() + (timedelta(minutes=15) if erstwechsel else timedelta(days=7))
    with SessionLocal() as sess:
        konto = sess.get(User, user, with_for_update=True)
        if not konto_ist_aktiv(konto):
            raise ValidationError("Für dieses Konto kann kein Passwort-Link erstellt werden.")
        row = sess.get(Passwortzugang, user, with_for_update=True)
        if row is None:
            row = Passwortzugang(user=user, wechsel_noetig=False)
            sess.add(row)
        row.token_hash = hashlib.sha256(kennung.encode()).hexdigest()
        row.gueltig_bis = bis
        sess.commit()
    return {"link": f"/diakonos/passwort-setzen#token={kennung}",
            "gueltig_bis": bis.isoformat() + "Z"}


def passwort_uebernehmen(token, passwort):
    from diakronos_app.anmeldung.konfiguration import oidc_aktiv
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import User
    from diakronos_app.frappe_compat import benutzer_status
    from diakronos_app.frappe_compat.passwoerter import neuer_hash, pruefe

    pruefe_passwort(passwort)
    ungueltig = "Dieser Link ist nicht mehr gültig. Bitte frage bei der Gemeinde nach einem neuen Link."
    if oidc_aktiv() or not isinstance(token, str) or len(token) != 43:
        raise ValidationError(ungueltig)
    digest = hashlib.sha256(token.encode()).hexdigest()
    with SessionLocal() as sess:
        # Alle Schreibwege sperren zuerst die Kontozeile (einheitliche Reihenfolge).
        user = sess.scalar(select(Passwortzugang.user).where(Passwortzugang.token_hash == digest))
        konto = sess.get(User, user, with_for_update=True) if user else None
        row = sess.get(Passwortzugang, user, with_for_update=True) if user else None
        if (konto is None or row is None or row.token_hash != digest or row.gueltig_bis is None
                or row.gueltig_bis <= _jetzt() or not benutzer_status.konto_ist_aktiv(konto)):
            raise ValidationError(ungueltig)
        if row.wechsel_noetig and pruefe(passwort, konto.password_hash or ""):
            raise ValidationError("Das neue Passwort muss sich vom Startpasswort unterscheiden.")
        konto.password_hash = neuer_hash(passwort)
        row.wechsel_noetig = False
        row.token_hash = None
        row.gueltig_bis = None
        sess.commit()
    benutzer_status.widerrufe_sitzungen(user)
    return {"success": True}
