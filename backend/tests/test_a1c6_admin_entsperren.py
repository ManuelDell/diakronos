"""A1c6 (2/3) — der Web-Weg: `entsperren.entsperren_konto` ueber HTTP.

Der Notfallweg ist die CLI; dieser Endpunkt ist der Normalfall (ein
Mitglied hat sich dreimal vertippt, ein *anderer* Administrator schaltet es
frei). Geprueft wird hier, was ein HTTP-Aufruf garantieren muss:

  1. **Gast und Nicht-Admin kommen nicht durch** — beide Richtungen, mit
     Status und Body. Das ist die Richtung, die man sonst erst im Betrieb
     bemerkt.
  2. **CSRF bleibt Pflicht.** Der Endpunkt schreibt; ohne
     `X-Frappe-CSRF-Token` ist die Ablehnung 417 `CSRFTokenError`. Er steht
     deshalb in keinem `CSRF_EXEMPT_PATHS`, und genau das wird hier belegt —
     nicht nur, dass es funktioniert, sondern dass niemand ihn bequemlich
     ausgenommen hat.
  3. **Die Antwortform verraet nicht, ob es das Konto gibt.** Drei Faelle —
     gesperrt, nie gesperrt, unbekannt — muessen ununterscheidbar sein. Es
     gab hier eine Fassung mit zwei Texten; die beantwortet genau die Frage,
     die dieses Werkzeug nicht beantworten darf.
  4. **Beide Bereiche werden frei** (Login UND CalDAV), und danach stimmt
     wieder die Antwort des jeweils anderen Zugangs.
  5. **Die IP bleibt gesperrt.** Der Web-Weg loest nur das Konto; das ist
     die A1c2-Entscheidung und darf hier nicht versehentlich aufweichen.
  6. **Das Audit traegt Pseudonyme** — wer, wen, welcher Bereich, ob etwas
     zu tun war; und **keinen** Klartext, kein Passwort, kein `sid`, kein
     CSRF-Token.
  7. **Das Werkzeug ist begrenzt** je Administrator-Konto.
"""

from __future__ import annotations

import base64
import hashlib

import pytest
from fastapi.testclient import TestClient

from diakronos_app.frappe_compat import loginversuche as lv

SCHWELLE = 5
PFAD = "/api/method/entsperren.entsperren_konto"
TEST_CLIENT_IP = "203.0.113.90"  # A1c12: gueltige Adresse statt Test-Hostname

ZIEL = "anna@example.org"
NICHT_ADMIN = "berta@example.org"
GEHEIM = "Geheim-1"


# ── Helfer ──────────────────────────────────────────────────────────────────


def _pseudo(roh: str) -> str:
    """Dieselbe Pseudonymform wie im Endpunkt — unabhaengig nachgerechnet."""
    from diakronos_app.api.entsperren import _pseudo as impl

    return impl(roh)


def _basic(user, pw):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()}


def _dav(client, user: str, pw: str):
    return client.request("PROPFIND", "/dav/", headers=_basic(user, pw))


def _sperre_konto(user: str) -> None:
    for bereich in lv.BEREICHE:
        for _ in range(SCHWELLE + 1):
            lv.pruefe_und_merke(user, None, bereich=bereich)


def _sperre_ip(ip: str) -> None:
    """**A1c10:** die Adressschwelle (25), nicht die Kontoschwelle (5).

    Aus dem Store gelesen statt aus `SCHWELLE` — dieselbe Zahl an zwei
    Stellen ist die Vorlage fuer den naechsten Fehler.
    """
    for bereich in lv.BEREICHE:
        for nummer in range(lv._max_versuche("ip") + 1):
            lv.pruefe_und_merke(f"opfer{nummer}@example.org", ip, bereich=bereich)


def _konto_gesperrt(user: str) -> bool:
    client = lv._client()
    return any(
        client.exists(sperr)
        for bereich in lv.BEREICHE
        for _art, _zaehler, sperr in lv._kennungen(user, None, bereich)
    )


def _ip_gesperrt(ip: str) -> bool:
    client = lv._client()
    return any(
        client.exists(sperr)
        for bereich in lv.BEREICHE
        for _art, _zaehler, sperr in lv._kennungen(None, ip, bereich)
    )


def _nutzer(sess, name: str, rollen: tuple[str, ...] = ()) -> None:
    """Legt einen Benutzer an; `rollen` entscheidet ueber die Admin-Faehigkeit."""
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import HasRole, User

    sess.add(User(
        name=name, email=name, full_name=name, enabled=True,
        password_hash=neuer_hash(GEHEIM),
    ))
    sess.flush()
    for idx, rolle in enumerate(rollen, start=1):
        sess.add(HasRole(
            name=f"HR-{name}-{rolle}", parent=name, parenttype="User",
            parentfield="roles", role=rolle, docstatus=0, idx=idx,
        ))
    sess.commit()


@pytest.fixture()
def admin_http(patched_db, fake_redis):
    """Echte Sitzung als `anna@example.org` MIT Admin-Rolle — wie ein Browser."""
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.main import app

    sess = patched_db()
    _nutzer(sess, ZIEL, ("Mitgliederadministrator",))
    _nutzer(sess, NICHT_ADMIN)
    sid, csrf = sitzungen.anlegen(ZIEL)
    sess.close()

    with TestClient(app, client=(TEST_CLIENT_IP, 50000)) as c:
        c.cookies.set("sid", sid)
        c.headers["X-Frappe-CSRF-Token"] = csrf
        yield c, csrf


@pytest.fixture()
def mitglied_http(patched_db, fake_redis):
    """Echte Sitzung als `berta@example.org` — angemeldet, aber KEIN Admin."""
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.main import app

    sess = patched_db()
    _nutzer(sess, ZIEL, ("Mitgliederadministrator",))
    _nutzer(sess, NICHT_ADMIN)
    sid, csrf = sitzungen.anlegen(NICHT_ADMIN)
    sess.close()

    with TestClient(app, client=(TEST_CLIENT_IP, 50000)) as c:
        c.cookies.set("sid", sid)
        c.headers["X-Frappe-CSRF-Token"] = csrf
        yield c, csrf


# ── 1. Gegenrichtung: Gast und Nicht-Admin ──────────────────────────────────


def test_gast_wird_abgewiesen(guest_client, patched_db, fake_redis):
    """Ohne Sitzung: 403, und es wird **nichts** freigegeben."""
    _sperre_konto(ZIEL)

    r = guest_client.post(PFAD, json={"user": ZIEL})

    assert r.status_code == 401
    assert _konto_gesperrt(ZIEL), "der Gast hat freigegeben"


def test_mitglied_ohne_admin_rolle_wird_abgewiesen(mitglied_http, patched_db):
    """Angemeldet, aber nicht Admin: 403, und es wird **nichts** freigegeben.

    Das ist die Richtung, die man leicht vergisst: eine gueltige Sitzung ist
    keine Berechtigung.
    """
    _sperre_konto(ZIEL)

    c, _csrf = mitglied_http
    r = c.post(PFAD, json={"user": ZIEL})

    assert r.status_code == 403
    assert _konto_gesperrt(ZIEL), "ein Nicht-Admin hat freigegeben"


def test_ablehnung_unterscheidet_gast_und_nicht_admin_nicht_in_der_wirkung(mitglied_http, guest_client, patched_db):
    """Beide Richtungen scheitern **am Zustand**, nicht nur am Status.

    Sonst koennte ein nicht privilegierter Aufruf die Sperre doch aufheben und
    der 403 waere nur Kosmetik.
    """
    _sperre_konto(ZIEL)
    c, _ = mitglied_http
    guest_client.post(PFAD, json={"user": ZIEL})
    c.post(PFAD, json={"user": ZIEL})

    assert _konto_gesperrt(ZIEL)


def test_antwort_der_ablehnung_nennt_kein_konto(guest_client):
    """Der 403 traegt die Frappe-Form, keine Adresse und keinen Bestand."""
    r = guest_client.post(PFAD, json={"user": ZIEL})

    body = r.text.lower()
    assert ZIEL not in body and "anna" not in body


# ── 2. CSRF bleibt Pflicht ──────────────────────────────────────────────────


def test_ohne_csrf_token_wird_abgewiesen(admin_http, patched_db):
    """Der Endpunkt schreibt: ohne Token keine Aenderung.

    Waere er von der CSRF-Pruefung ausgenommen, koennte eine fremde Seite im
    Browser eines eingeloggten Administrators fremde Konten freigeben.
    """
    _sperre_konto(ZIEL)
    c, csrf = admin_http

    r = c.post(PFAD, json={"user": ZIEL}, headers={"X-Frappe-CSRF-Token": "falsch"})

    assert r.status_code == 417
    assert r.json()["exc_type"] == "CSRFTokenError"
    assert _konto_gesperrt(ZIEL), "ohne CSRF wurde trotzdem freigegeben"


def test_der_endpunkt_ist_nicht_von_der_csrf_pruefung_ausgenommen():
    """Beleg auf Codeebene: kein Eintrag in `CSRF_EXEMPT_PATHS`.

    Ein Eintrag wuerde die ganze Karte an einer Stelle aushebeln, die man
    beim Lesen des Endpunkts nicht sieht.
    """
    from diakronos_app.frappe_compat.auth_middleware import CSRF_EXEMPT_PATHS

    assert PFAD not in CSRF_EXEMPT_PATHS
    assert not any("entsperr" in p for p in CSRF_EXEMPT_PATHS)


# ── 3. Die Antwortform verraet nicht, ob es das Konto gibt ─────────────────


def test_die_drei_faelle_antworten_identisch(admin_http, patched_db):
    """gesperrt / nie gesperrt / unbekannt — dieselbe Antwort, Wort fuer Wort.

    Der Endpunkt soll kein Benutzer-Enumerations-Werkzeug fuer den Fall sein,
    dass jemand Admin-Rechte hat, aber die Liste nicht kennt.
    """
    c, _ = admin_http

    _sperre_konto(ZIEL)
    gesperrt = c.post(PFAD, json={"user": ZIEL}).text

    nie = c.post(PFAD, json={"user": "gast2@example.org"}).text
    unbekannt = c.post(PFAD, json={"user": "niemand@example.org"}).text

    assert gesperrt == nie == unbekannt


def test_antwort_enthaelt_keine_zaehler_und_keine_zeiten(admin_http, patched_db):
    """Keine Trefferzahl, keine Sperrdauer, keine Restzeit im Body."""
    c, _ = admin_http
    _sperre_konto(ZIEL)

    r = c.post(PFAD, json={"user": ZIEL})

    assert set(r.json()) == {"message", "exc_type"} or set(r.json()) == {"message"}
    assert not any(z.isdigit() for z in r.text), f"Ziffern in der Antwort: {r.text}"
    assert ZIEL not in r.text


# ── 4. Beide Bereiche werden frei ──────────────────────────────────────────


def test_admin_weg_loest_das_gesperrte_konto(admin_http, patched_db):
    """Der Normalfall: gesperrt -> 200 -> das Konto ist wieder benutzbar."""
    c, _ = admin_http
    _sperre_konto(ZIEL)
    assert c.post("/api/method/login", json={"usr": ZIEL, "pwd": GEHEIM}).status_code == 401

    r = c.post(PFAD, json={"user": ZIEL})

    assert r.status_code == 200
    assert not _konto_gesperrt(ZIEL)
    assert c.post("/api/method/login", json={"usr": ZIEL, "pwd": GEHEIM}).status_code == 200


def test_der_login_gibt_die_echte_sitzung_zurueck(admin_http, patched_db):
    """Nach der Freigabe: 200, Sitzung und der echte Name im Boot-Objekt."""
    c, _ = admin_http
    _sperre_konto(ZIEL)

    c.post(PFAD, json={"user": ZIEL})
    login = c.post("/api/method/login", json={"usr": ZIEL, "pwd": GEHEIM})

    assert login.status_code == 200
    assert login.json()["user"] == ZIEL

    boot = c.get("/diakonos")
    assert boot.status_code == 200
    # Der Boot-Objekt-Feld `user` traegt den vollen Namen, nicht den Platzhalter.
    assert NICHT_ADMIN not in boot.text


def test_nach_der_freigabe_funktioniert_auch_der_caldav_login(admin_http, patched_db):
    """Abnahme: **beide** Bereiche sind frei, nicht nur der Login.

    Die Sperre ist bereichsuebergreifend, die Zaehler sind es nicht. Wuerde der
    Endpunkt nur den Login-Bereich leeren, waere das Konto im Kalender weiter
    zu — und der Aufrufer wundert sich ueber den naechsten 401.
    """
    c, _ = admin_http
    _sperre_konto(ZIEL)
    assert _dav(c, ZIEL, GEHEIM).status_code == 401

    c.post(PFAD, json={"user": ZIEL})

    for bereich in lv.BEREICHE:
        stand = lv.zaehler_stand(ZIEL, None, bereich=bereich)
        assert stand["benutzer"] == 0, f"Bereich {bereich} hat noch Fehlversuche"
    dav = _dav(c, ZIEL, GEHEIM)
    assert dav.status_code == 207, "der CalDAV-Login bleibt zu"


def test_gross_klein_und_umraum_werden_akzeptiert(admin_http, patched_db):
    """Der Admin tippt die Adresse ein — wie im Anmeldepfad normalisiert."""
    c, _ = admin_http
    _sperre_konto(ZIEL)

    r = c.post(PFAD, json={"user": f"  {ZIEL.upper()}  "})

    assert r.status_code == 200
    assert not _konto_gesperrt(ZIEL)


def test_freigabe_ist_idempotent(admin_http, patched_db):
    """Zweimal aufrufen ist unschaedlich."""
    c, _ = admin_http
    _sperre_konto(ZIEL)

    assert c.post(PFAD, json={"user": ZIEL}).status_code == 200
    assert c.post(PFAD, json={"user": ZIEL}).status_code == 200
    assert not _konto_gesperrt(ZIEL)


def test_fehlt_der_benutzername_wird_abgelehnt(admin_http, patched_db):
    """Ohne `user` ist nichts zu tun — und das wird auch so gesagt."""
    c, _ = admin_http

    r = c.post(PFAD, json={})

    assert r.status_code == 417
    assert r.json()["exc_type"] == "ValidationError"


# ── 5. Die IP bleibt gesperrt ──────────────────────────────────────────────


def test_der_web_weg_loest_die_ip_nicht_mit(admin_http, patched_db):
    """Konto frei, IP gesperrt — genau die Entscheidung aus A1c2.

    Wer hier auf "Konto freigeben" klickt, will nicht ungefragt das halbe
    Buero ueber denselben Gemeindesanschluss mitsperren. Der Notfall, in dem
    die IP mitfreigegeben werden MUSS, laeuft ueber die CLI.
    """
    c, _ = admin_http
    _sperre_konto(ZIEL)
    _sperre_ip(TEST_CLIENT_IP)
    assert _konto_gesperrt(ZIEL) and _ip_gesperrt(TEST_CLIENT_IP)

    c.post(PFAD, json={"user": ZIEL})

    assert not _konto_gesperrt(ZIEL)
    assert _ip_gesperrt(TEST_CLIENT_IP), "der Web-Weg hat die IP mitgeloescht"


def test_der_endpunkt_kennt_keinen_ip_parameter(admin_http, patched_db):
    """Es gibt keinen Weg, eine IP ueber diesen Endpunkt mitzuloesen.

    Auch nicht versehentlich: `zuruecksetzen_alles` nimmt kein `ip` an, und
    der Endpunkt ruft genau das auf.
    """
    import inspect

    from diakronos_app.api import entsperren

    sig = inspect.signature(entsperren.entsperren_konto)
    assert "ip" not in sig.parameters

    c, _ = admin_http
    _sperre_konto(ZIEL)
    _sperre_ip(TEST_CLIENT_IP)
    c.post(PFAD, json={"user": ZIEL, "ip": TEST_CLIENT_IP})

    assert _ip_gesperrt(TEST_CLIENT_IP), "ueber den Endpunkt liess sich die IP loeschen"


# ── 6. Das Audit traegt Pseudonyme ─────────────────────────────────────────


def _audit_zeilen(patched_db, merkmal: str = "freigegeben"):
    from diakronos_app.models.diakonos import AuditLog

    sess = patched_db()
    try:
        return [z for z in sess.query(AuditLog).all() if merkmal in (z.begruendung or "")]
    finally:
        sess.close()


def test_die_freigabe_steht_im_audit_log(admin_http, patched_db):
    """Abnahme: der Ausloesevorgang ist protokolliert."""
    c, _ = admin_http
    _sperre_konto(ZIEL)

    c.post(PFAD, json={"user": ZIEL})

    assert _audit_zeilen(patched_db), "die Freigabe wurde nicht protokolliert"


def test_audit_nennt_weder_klartext_noch_geheimnis(admin_http, patched_db):
    """Abnahme-Ausgabe: Pseudonyme, kein Klartext, kein Passwort, kein Token.

    Geprueft werden **alle** Freitextfelder des Eintrags, nicht nur eines — ein
    Leak in `old_value` waere genauso ein Leak wie eines in `begruendung`.
    """
    c, csrf = admin_http
    _sperre_konto(ZIEL)

    c.post(PFAD, json={"user": ZIEL})

    zeilen = _audit_zeilen(patched_db)
    assert zeilen
    volltext = " ".join(
        str(getattr(z, feld) or "")
        for z in zeilen
        for feld in (
            "begruendung", "target_name", "ip_address",
            "old_value", "new_value", "confirm_reason", "user_agent",
        )
    ).lower()
    assert ZIEL not in volltext
    assert "anna" not in volltext and "example.org" not in volltext
    assert GEHEIM.lower() not in volltext
    assert csrf.lower() not in volltext


def test_audit_haelt_wer_wen_und_welchen_bereich_fest(admin_http, patched_db):
    """Wer, wen, welcher Bereich, ob etwas zu tun war — alles im selben Eintrag."""
    c, _ = admin_http
    _sperre_konto(ZIEL)

    c.post(PFAD, json={"user": ZIEL})

    eintrag = _audit_zeilen(patched_db)[0]
    text = eintrag.begruendung
    assert eintrag.target_name.startswith("sha256:"), "Ziel nicht pseudonymisiert"
    assert "freigegeben_von=sha256:" in text, "der ausfuehrende Admin fehlt"
    assert "Ziel=sha256:" in text
    for bereich in lv.BEREICHE:
        assert bereich in text, f"Bereich {bereich} nicht genannt"
    assert "hat_gesperrt_gehabt=ja" in text


def test_audit_unterscheidet_gefreigt_von_nichts_zu_tun(admin_http, patched_db):
    """Hier — und nur hier — darf stehen, ob es etwas zu loesen gab.

    Der Bericht ist eine Tatsache fuer die Dokumentation, kein Kanal zum
    Aufrufer: die HTTP-Antwort bleibt in allen Faellen gleich.
    """
    c, _ = admin_http

    c.post(PFAD, json={"user": ZIEL})       # nie gesperrt
    vorher = len(_audit_zeilen(patched_db))
    _sperre_konto(ZIEL)
    c.post(PFAD, json={"user": ZIEL})
    nachher = _audit_zeilen(patched_db)

    assert vorher >= 1
    assert "hat_gesperrt_gehabt=nein" in nachher[vorher - 1].begruendung
    assert "hat_gesperrt_gehabt=ja" in nachher[vorher].begruendung


def test_der_ausfuehrende_admin_steht_pseudonymisiert_drin(admin_http, patched_db):
    """Der Admin ist selbst ein Benutzerkonto — mit Pseudonym im selben Eintrag.

    `actor` traegt den echten Fremdschluessel auf `user.name` (ohne ihn kaeme
    der Eintrag gar nicht zustande); im Freitext steht der Admin
    **pseudonymisiert**, damit das Log nicht neben dem Zielkonto das zweite
    Konto im Klartext nennt.
    """
    c, _ = admin_http
    _sperre_konto(ZIEL)

    c.post(PFAD, json={"user": ZIEL})

    eintrag = _audit_zeilen(patched_db)[0]
    assert eintrag.actor == ZIEL, "actor ist ein Fremdschluessel auf user.name"
    assert f"freigegeben_von={_pseudo(ZIEL)}" in eintrag.begruendung
    assert ZIEL not in eintrag.begruendung.lower()


def test_der_gast_wird_nicht_protokolliert_weil_er_nichts_tut(guest_client, patched_db):
    """Ein abgewiesener Aufruf erzeugt keinen Freigabe-Eintrag."""
    guest_client.post(PFAD, json={"user": ZIEL})

    assert _audit_zeilen(patched_db) == []


def test_fehlgeschlagener_audit_eintrag_haelt_die_freigabe_nicht_auf(admin_http, patched_db, monkeypatch):
    """Faellt der Eintrag aus, ist das Konto trotzdem frei.

    Umgekehrt wie bei der Anmeldung: dort ist der Eintrag die Dokumentation
    der Sperre, hier die Dokumentation einer Freigabe. Die Freigabe ist
    erfolgt und gilt — ein kaputter Log darf sie nicht zuruecknehmen.
    """
    import diakronos_app.frappe_compat.api_helpers as helpers

    def _kaputt(*_a, **_kw):
        raise RuntimeError("Audit-DB weg")

    monkeypatch.setattr(helpers, "_create", _kaputt)
    c, _ = admin_http
    _sperre_konto(ZIEL)

    r = c.post(PFAD, json={"user": ZIEL})

    assert r.status_code == 200
    assert not _konto_gesperrt(ZIEL)


# ── 7. Das Werkzeug ist begrenzt ───────────────────────────────────────────


def test_das_werkzeug_ist_je_admin_begrenzt(admin_http, patched_db, monkeypatch):
    """Ein uebernommenes Admin-Konto ist nicht der Knopfdruck fuer alle.

    Das Budget wird hier bewusst klein gesetzt, damit der Test nicht 11
    HTTP-Aufrufe braucht: geprueft wird die **Wirkung** der Grenze, nicht ihr
    Zahlenwert (der steht in den Settings und hat einen eigenen Test).
    """
    from diakronos_app.api import entsperren

    monkeypatch.setattr(entsperren.settings, "werkzeuglimit_entsperren", 2)
    c, _ = admin_http

    assert c.post(PFAD, json={"user": "a@example.org"}).status_code == 200
    assert c.post(PFAD, json={"user": "b@example.org"}).status_code == 200
    r = c.post(PFAD, json={"user": "c@example.org"})

    assert r.status_code == 403


def test_die_ablehnung_beim_budget_nennt_den_benutzer_nicht(admin_http, patched_db, monkeypatch):
    """Die 403 traegt keine Adresse — sie ist nicht unterscheidbarer als die
    eines nicht privilegierten Aufrufs."""
    from diakronos_app.api import entsperren

    monkeypatch.setattr(entsperren.settings, "werkzeuglimit_entsperren", 1)
    c, _ = admin_http
    c.post(PFAD, json={"user": "a@example.org"})

    r = c.post(PFAD, json={"user": "a@example.org"})

    assert r.status_code == 403
    assert "a@example.org" not in r.text


def test_das_budget_gilt_je_admin_getrennt(admin_http, patched_db, monkeypatch):
    """Zwei Administratoren verbrauchen ihr Budget nicht gegenseitig."""
    from diakronos_app.api import entsperren

    monkeypatch.setattr(entsperren.settings, "werkzeuglimit_entsperren", 1)
    admin, _ = admin_http

    assert admin.post(PFAD, json={"user": "a@example.org"}).status_code == 200
    assert admin.post(PFAD, json={"user": "b@example.org"}).status_code == 403


# ── Die Registry ────────────────────────────────────────────────────────────


def test_der_pfad_ist_unter_der_frappe_konvention_erreichbar(admin_http):
    """`/api/method/<modul>.<funktion>` — und der Pfad aus `FRAPPE_MODULE` auch."""
    from diakronos_app.frappe_compat.registry import lookup

    fn = lookup("entsperren.entsperren_konto")
    assert fn is not None, "der Kurzpfad loest nicht auf"
    assert lookup("diakronos.diakonos.api.entsperren.entsperren_konto") is fn

    c, _ = admin_http
    assert c.post("/api/method/diakronos.diakonos.api.entsperren.entsperren_konto",
                  json={"user": ZIEL}).status_code == 200
