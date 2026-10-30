"""REG-1a — Registrierung: Startdatum, Beschreibung, Formularbilder.

Karte REG-1a (Manuel 23.10.), Backend-Teil. Die Faelle sind entlang der
Zusage der Karte gebaut:

  1. **Startdatum** (``registrierungslink.gueltig_ab``): vor dem Tag ist der
     Link fuer Besucher nicht nutzbar (klare Meldung „Anmeldung ab …“),
     Administratoren sehen ihn trotzdem. Das gilt fuer alle drei Wege, ueber
     die ein Besucher den Link benutzt: ``validate_token`` (JSON), die
     ausgelieferte Seite (``window.__diakronos.linkFehler``) und das Absenden
     (``submit_registrierung``/``submit_gast``) — sowie fuer die Formularbilder.
     Zusaetzlich kennt die Zustandsanzeige der Verwaltung den Zustand
     ``bevorstehend``.

  2. **Beschreibung** am Formular: reiner Text/Markdown-light, XSS-sicher —
     normalisiert gespeichert, in ``validate_token`` und im Boot-Objekt der
     Seite ausgeliefert, nie als HTML.

  3. **Bilder** (Banner + Hintergrund): Upload ueber den vorhandenen
     Datei-Mechanismus (``upload_file``), Groessen-/Typpruefung wie dort; die
     Zuordnung passiert ueber ``update_anmeldeformular``. Abruf fuer Besucher
     AUSSCHLIESSLICH ueber ``/public/registrierung/<token>/bild/<rolle>`` —
     ``/files/…`` verlangt eine Anmeldung.

Vorgehen: erst die roten Faelle schreiben, dann implementieren; die Datei
bleibt als Regressionsschutz. Alle Tests laufen ohne Netz (``patched_db``,
SQLite) und ohne Betriebsdaten — Regel 11 der Karte.
"""

from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
JPEG = b"\xff\xd8\xff\xe0JPEG"
HTML_DATEI = b"<html><script>alert(1)</script></html>"

MODUL = "diakronos.diakonos.api.registrierung"
MODUL_LINK = "diakronos.diakonos.api.registrierungslink_api"
MODUL_HUB = "diakronos.diakonos.api.admin_hub"
SLUG = "reg1aslug"
LINK = "RL-REG1A"
FORM = "AF-REG1A"
ADMIN = "reg1a-admin@example.org"


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def files_dir(tmp_path, monkeypatch):
    """Eigene Ablage je Test — nie das Betriebs-Volume (Regel 11)."""
    from diakronos_app.settings import settings

    ziel = tmp_path / "files"
    monkeypatch.setattr(settings, "files_dir", str(ziel))
    return ziel


def _link(**werte) -> "object":
    from diakronos_app.models.diakonos import Registrierungslink

    daten = {
        "name": LINK,
        "bezeichnung": "Einladung",
        "typ": "Mitglied-Registrierung",
        "aktiv": True,
        "slug": SLUG,
        "max_anmeldungen": 0,
        "anmeldungen_count": 0,
        "anmeldeformular": FORM,
        "docstatus": 0,
        "idx": 0,
    }
    daten.update(werte)
    return Registrierungslink(**daten)


def _form(**werte) -> "object":
    from diakronos_app.models.diakonos import Anmeldeformular

    daten = {
        "name": FORM,
        "bezeichnung": "Standard",
        "mit_kinder": True,
        "mit_gaesten": False,
        "docstatus": 0,
        "idx": 0,
    }
    daten.update(werte)
    return Anmeldeformular(**daten)


@pytest.fixture()
def welt(patched_db):
    sess = patched_db()
    sess.add(_form())
    sess.add(_link())
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def admin_client(client, patched_db):
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.models.core import HasRole, User

    sess = patched_db()
    if sess.get(User, ADMIN) is None:
        sess.add(User(name=ADMIN, email=ADMIN, full_name="Admin", enabled=True))
    if not sess.query(HasRole).filter_by(parent=ADMIN, role="Mitgliederadministrator").first():
        sess.add(
            HasRole(
                name=f"{ADMIN}-MA",
                parent=ADMIN,
                parenttype="User",
                parentfield="roles",
                idx=1,
                role="Mitgliederadministrator",
            )
        )
    sess.commit()
    sess.close()

    set_user(ADMIN)
    try:
        yield client
    finally:
        set_user("Administrator")


@pytest.fixture()
def gast(session_weg):
    """Nicht angemeldeter Besucher derselben App und DB, ohne Sitzung.

    Der `client`-Fixture der Suite haengt an einer echten Admin-Sitzung
    (Cookie + CSRF-Kopf am Client) — ein `set_user("Guest")` allein kippt die
    NICHT, die Middleware liest weiter das Cookie. Deshalb ein eigener
    TestClient auf derselben App: `patched_db` hat die Engine schon auf diese
    Instanz gepatcht (auth-noetige Tabellen tragen In-Memory-SQLite gemeinsam),
    und ohne Cookie ist jeder Aufruf `Guest`. Gebaut wird er NACH dem
    angemeldeten Client (Fixture-Reihenfolge), damit dessen Sitzung nicht
    durch einen zweiten `TestClient`-Kontext neu aufgebaut wird.
    """
    from diakronos_app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def session_weg(patched_db, fake_redis):
    """Nur die Abhaengigkeiten des Clients — damit `gast` allein nutzbar bleibt."""
    return None


def _morgen() -> str:
    return (dt.date.today() + dt.timedelta(days=3)).isoformat()


def _gestern() -> str:
    return (dt.date.today() - dt.timedelta(days=3)).isoformat()


def _upload(client, name="bild.png", mime="image/png", inhalt=PNG, **data):
    """Upload ueber den vorhandenen Weg — mit eigener CSRF-Kennung.

    Der `client`-Fixture haengt seine Sitzung per Default-Header an; nach
    `set_user("Guest")` gilt aber die Gast-Sitzung, und der Schreibschutz
    verlangt den Token im Aufruf. `POST`-Tests, die als Admin laufen
    (`admin_client`), funktionieren mit und ohne diesen Kopf gleich.
    """
    return client.post(
        "/api/method/upload_file",
        files={"file": (name, io.BytesIO(inhalt), mime)},
        data=data,
    )


# ════════════════════════════════════════════════════════════════════════════
# 1 — Startdatum am Registrierungslink
# ════════════════════════════════════════════════════════════════════════════


def test_startdatum_validate_token_verweigert_mit_klarer_meldung(gast, welt):
    """Vor „gültig ab“ ist der Link fuer Besucher nicht nutzbar — mit Datum im Text."""
    from diakronos_app.models.diakonos import Registrierungslink

    sess = welt
    sess.get(Registrierungslink, LINK).gueltig_ab = dt.date.fromisoformat(_morgen())
    sess.commit()

    r = gast.get(f"/api/method/{MODUL}.validate_token", params={"token": SLUG})
    assert r.status_code == 403, r.text
    text = r.json().get("message") or ""
    tag, monat, jahr = _morgen().split("-")[::-1]
    assert f"{tag}.{monat}.{jahr}" in text, text
    assert text.startswith("Anmeldung ab "), text


def test_startdatum_am_tag_selbst_gilt_der_link(gast, welt):
    """Am Tag von „gültig ab“ ist der Link nutzbar (nicht erst danach)."""
    from diakronos_app.models.diakonos import Registrierungslink

    sess = welt
    sess.get(Registrierungslink, LINK).gueltig_ab = dt.date.today()
    sess.commit()

    r = gast.get(f"/api/method/{MODUL}.validate_token", params={"token": SLUG})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["typ"] == "Mitglied-Registrierung"


def test_startdatum_admin_sieht_den_link_trotzdem(admin_client, welt):
    """Administratoren koennen den Link vor dem Startdatum ansehen."""
    from diakronos_app.models.diakonos import Registrierungslink

    sess = welt
    sess.get(Registrierungslink, LINK).gueltig_ab = dt.date.fromisoformat(_morgen())
    sess.commit()

    r = admin_client.get(
        f"/api/method/{MODUL}.get_oeffentliche_formular", params={"token": SLUG}
    )
    assert r.status_code == 200, r.text
    assert r.json()["message"]["typ"] == "Mitglied-Registrierung"


def test_startdatum_besucher_sieht_kein_formular(gast, welt):
    """Ohne Adminrolle bleibt der Link vor dem Startdatum zu — auch hier."""
    from diakronos_app.models.diakonos import Registrierungslink

    sess = welt
    sess.get(Registrierungslink, LINK).gueltig_ab = dt.date.fromisoformat(_morgen())
    sess.commit()

    r = gast.get(
        f"/api/method/{MODUL}.get_oeffentliche_formular", params={"token": SLUG}
    )
    assert r.status_code == 403, r.text
    assert "Anmeldung ab" in (r.json().get("message") or "")


def test_startdatum_absenden_ist_gesperrt(gast, welt):
    """Auch ein direkter Absende POST kommt vor dem Startdatum nicht durch."""
    from diakronos_app.models.diakonos import Anmeldung, Registrierungslink

    sess = welt
    sess.get(Registrierungslink, LINK).gueltig_ab = dt.date.fromisoformat(_morgen())
    sess.commit()

    r = gast.post(
        f"/api/method/{MODUL}.submit_registrierung",
        data={"token": SLUG, "vorname": "Anna", "nachname": "Beispiel", "dsgvo": True},
    )
    assert r.status_code == 403, r.text
    assert "Anmeldung ab" in (r.json().get("message") or "")
    assert sess.query(Anmeldung).count() == 0


def test_startdatum_seite_zeigt_meldung_statt_formular(monkeypatch, welt):
    """Die oeffentliche Seite traegt die Meldung in `linkFehler` (kein Formular)."""
    from diakronos_app import spa
    from diakronos_app.models.diakonos import Registrierungslink

    sess = welt
    sess.get(Registrierungslink, LINK).gueltig_ab = dt.date.fromisoformat(_morgen())
    sess.commit()

    monkeypatch.setattr(spa, "oeffentliche_texte", lambda: {})
    monkeypatch.setattr(spa, "_willkommenstext", lambda: "")
    daten = spa._oeffentliche_daten("registrierung", SLUG)
    assert daten["token"] == ""
    assert daten["felder"] == []
    assert daten["linkFehler"].startswith("Anmeldung ab ")


def test_startdatum_zustand_bevorstehend():
    """Der Zustand der Verwaltung kennt „bevorstehend“ (vor vollem Kontingent)."""
    from diakronos_app.anmeldung.registrierungslink import zustand

    ergebnis = zustand(
        {
            "aktiv": 1,
            "gueltig_ab": _morgen(),
            "gueltig_bis": None,
            "max_anmeldungen": 1,
            "anmeldungen_count": 1,
        }
    )
    assert ergebnis["zustand"] == "bevorstehend"
    assert ergebnis["bevorstehend"] is True
    assert ergebnis["gueltig_ab"] == _morgen()


def test_startdatum_vergangenheit_ist_sofort_gueltig():
    from diakronos_app.anmeldung.registrierungslink import zustand

    assert zustand({"aktiv": 1, "gueltig_ab": _gestern()})["zustand"] == "aktiv"


def test_create_link_schreibt_gueltig_ab(admin_client, welt):
    r = admin_client.post(
        f"/api/method/{MODUL_LINK}.create_link",
        data={"bezeichnung": "Neu", "typ": "Mitglied-Registrierung", "gueltig_ab": _morgen()},
    )
    assert r.status_code == 200, r.text
    assert r.json()["message"]["link"]["gueltig_ab"] == _morgen()


def test_create_link_lehnt_unsinniges_datum_ab(admin_client, welt):
    r = admin_client.post(
        f"/api/method/{MODUL_LINK}.create_link",
        data={"bezeichnung": "Neu", "typ": "Mitglied-Registrierung", "gueltig_ab": "31.02.2026"},
    )
    assert r.status_code == 417, r.text
    assert "JJJJ-MM-TT" in (r.json().get("message") or "")


def test_update_link_setzt_und_loescht_startdatum(admin_client, welt):
    from diakronos_app.models.diakonos import Registrierungslink

    r = admin_client.post(
        f"/api/method/{MODUL_LINK}.update_link",
        data={"link_id": LINK, "gueltig_ab": _morgen()},
    )
    assert r.status_code == 200, r.text
    assert str(welt.get(Registrierungslink, LINK).gueltig_ab) == _morgen()

    r = admin_client.post(
        f"/api/method/{MODUL_LINK}.update_link", data={"link_id": LINK, "gueltig_ab": ""}
    )
    assert r.status_code == 200, r.text
    assert welt.get(Registrierungslink, LINK).gueltig_ab is None


def test_hub_liste_enthaelt_startdatum(admin_client, welt):
    r = admin_client.get(f"/api/method/{MODUL_HUB}.get_anmeldungen_hub")
    assert r.status_code == 200, r.text
    (link,) = [l for l in r.json()["message"]["links"] if l["name"] == LINK]
    assert "gueltig_ab" in link
    assert link["bevorstehend"] is False


# ════════════════════════════════════════════════════════════════════════════
# 2 — Beschreibung am Formular
# ════════════════════════════════════════════════════════════════════════════


def test_beschreibung_wird_als_text_gespeichert(admin_client, welt):
    from diakronos_app.models.diakonos import Anmeldeformular

    roh = "Herzlich willkommen!\n\n**Bitte** alle Felder ausfüllen.\n<script>alert(1)</script>"
    r = admin_client.post(
        f"/api/method/{MODUL_HUB}.update_anmeldeformular",
        data={"formular_id": FORM, "beschreibung": roh},
    )
    assert r.status_code == 200, r.text

    gespeichert = welt.get(Anmeldeformular, FORM).beschreibung
    assert "Bitte" in gespeichert
    assert "**" not in gespeichert  # Markdown-Betonung wird zu Text
    # Operator-Review REG-1a, Punkt 2: gespeichert wird KLARTEXT. Die spitzen
    # Klammern bleiben Zeichen — das Escaping macht die Anzeige (`{{ }}`),
    # sonst liest der Besucher woertlich „&lt;script&gt;“.
    assert "<script>alert(1)</script>" in gespeichert
    assert "&lt;" not in gespeichert and "&gt;" not in gespeichert


def test_beschreibung_kommt_oeffentlich_an(gast, welt, admin_client):
    from diakronos_app.models.diakonos import Anmeldeformular

    welt.get(Anmeldeformular, FORM).beschreibung = "Nur **kurz** was schreiben"
    welt.commit()

    r = gast.get(f"/api/method/{MODUL}.validate_token", params={"token": SLUG})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["beschreibung"] == "Nur kurz was schreiben"

    # Die Boot-Daten der Seite tragen denselben Text (Anzeige = API).
    from diakronos_app import spa

    daten = spa._oeffentliche_daten("registrierung", SLUG)
    assert daten["beschreibung"] == "Nur kurz was schreiben"


def test_beschreibung_wird_nicht_als_html_ausgeliefert(gast, welt):
    """HTML kommt als TEXT an — nie als Markup.

    Der Server liefert Klartext; die Anzeige (`registrierung/App.vue`) setzt
    ihn ueber `{{ }}` ein (kein `v-html`), damit ist es unschaedlich. Vorher
    maskierte der Server selbst — dann las der Besucher „&lt;img“.
    """
    from diakronos_app.models.diakonos import Anmeldeformular

    welt.get(Anmeldeformular, FORM).beschreibung = "<img src=x onerror=alert(1)>"
    welt.commit()

    r = gast.get(f"/api/method/{MODUL}.validate_token", params={"token": SLUG})
    text = r.json()["message"]["beschreibung"]
    # Klartext, damit die Anzeige ihn ESCAPEN kann — nicht schon maskiert.
    assert text == "<img src=x onerror=alert(1)>"
    assert "&lt;" not in text
    # Die ausgelieferte Seite traegt den Text als JSON-String (kein Markup im
    # HTML-Dokument): `<` erscheint dort als \u003c bzw. maskiert im Skript.
    seite = gast.get(f"/diakonos/registrierung?token={SLUG}")
    if seite.status_code == 200:
        assert "<img src=x onerror=alert(1)>" not in seite.text


def test_beschreibung_ohne_formular_ist_leer(gast, welt):
    from diakronos_app.models.diakonos import Registrierungslink

    welt.get(Registrierungslink, LINK).anmeldeformular = None
    welt.commit()

    r = gast.get(f"/api/method/{MODUL}.validate_token", params={"token": SLUG})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["beschreibung"] == ""
    assert r.json()["message"]["banner_bild"] == ""


# ════════════════════════════════════════════════════════════════════════════
# 3 — Banner und Hintergrund
# ════════════════════════════════════════════════════════════════════════════


def test_bild_wird_ueber_upload_zugeordnet_und_oeffentlich_ausgeliefert(
    admin_client, welt, files_dir
):
    """Der ganze Weg: Upload -> zuordnen -> Besucher sieht es ueber den Link."""
    # REG-1c: das Bild entsteht AM Formular (`doctype`/`docname`) — nur so
    # eine Datei nimmt `pruefe_bilddatei` an.
    hoch = _upload(admin_client, name="banner.png", doctype="Anmeldeformular", docname=FORM)
    assert hoch.status_code == 200, hoch.text
    dateiname = hoch.json()["message"]["file_url"].rsplit("/", 1)[-1]

    # Zuweisung ueber den oeffentlichen Weg (Administrator sieht den Link immer;
    # der Aufruf schreibt in DERSELBEN Sitzung wie das folgende Lesen).
    zu = admin_client.post(
        f"/api/method/{MODUL_HUB}.update_anmeldeformular",
        data={"formular_id": FORM, "banner_bild_datei": dateiname},
    )
    assert zu.status_code == 200, zu.text
    from diakronos_app.models.diakonos import Anmeldeformular
    from diakronos_app.db import SessionLocal

    with SessionLocal() as lese:
        assert lese.get(Anmeldeformular, FORM).bannerbild == dateiname

    # Warum nicht ueber die API gelesen wird: `get_doc` leiht sich in diesem
    # Fall die SITZUNG DES TESTS, die den gerade geschriebenen Stand noch nicht
    # sieht (autoflush=False, expire_all verboten — SEC-c/SEC-d). Geprueft wird
    # der Anzeigeweg deshalb mit einer FRISCHEN Lese-Sitzung als Kontext.
    # Lesen ueber die API/den Fachweg sieht den frischen Stand hier nicht
    # (Autoflush aus, expire_all verboten, parallele Test-Sitzung). Geprueft
    # werden die letzten zwei Glieder deshalb GETRENNT: die Spalte direkt und
    # die Ableitung Spalte -> Pfad ueber die echte Funktion.
    from diakronos_app.anmeldung.formularbilder import bild_pfad
    from diakronos_app.models.diakonos import Anmeldeformular
    from diakronos_app.db import SessionLocal

    with SessionLocal() as lese:
        gespeichert = lese.get(Anmeldeformular, FORM).bannerbild
    pfad = bild_pfad(SLUG, "banner", gespeichert)
    assert pfad == f"/public/registrierung/{SLUG}/bild/banner"

    bild = admin_client.get(pfad)
    assert bild.status_code == 200, bild.text
    assert bild.content == PNG
    assert bild.headers["content-type"].split(";")[0] == "image/png"
    assert bild.headers["x-content-type-options"] == "nosniff"


def test_bild_ist_am_formular_vorbei_nicht_oeffentlich(
    admin_client, welt, files_dir, monkeypatch
):
    """`/files/<name>` verlangt eine Anmeldung — genau so ist es gewollt.

    Der Upload laeuft als Admin; der Abruf OHNE Anmeldung wird an der Naht
    `frappe_compat.session.session.user` geprueft (dieselbe Stelle, die auch
    `files.serve_file` liest). Bewusst kein zweiter HTTP-Client: die
    Suite-Sitzung ist Cookie-gebunden und wuerde dabei neu aufgebaut.
    """
    from diakronos_app.frappe_compat import session as compat_session

    hoch = _upload(admin_client, name="banner.png", doctype="Anmeldeformular", docname=FORM)
    assert hoch.status_code == 200, hoch.text
    dateiname = hoch.json()["message"]["file_url"].rsplit("/", 1)[-1]
    admin_client.post(
        f"/api/method/{MODUL_HUB}.update_anmeldeformular",
        data={"formular_id": FORM, "banner_bild_datei": dateiname},
    )

    monkeypatch.setattr(compat_session, "user", "Guest", raising=False)
    assert admin_client.get(f"/files/{dateiname}").status_code == 403
    monkeypatch.setattr(compat_session, "user", "Administrator", raising=False)
    assert admin_client.get(f"/files/{dateiname}").status_code == 200


def test_bild_pfad_verlangt_gueltigen_token(gast, welt, files_dir):
    files_dir.mkdir(parents=True, exist_ok=True)
    (files_dir / "reg1a-bild.png").write_bytes(PNG)
    from diakronos_app.models.diakonos import Anmeldeformular

    welt.get(Anmeldeformular, FORM).bannerbild = "reg1a-bild.png"
    welt.commit()

    assert gast.get("/public/registrierung/nosuchtoken/bild/banner").status_code == 403
    assert gast.get(f"/public/registrierung/{SLUG}/bild/banner").status_code == 200
    # Unbekannte Rolle ist kein Bild.
    assert gast.get(f"/public/registrierung/{SLUG}/bild/kopf").status_code == 404


def test_bild_vor_startdatum_nicht_abrufbar(gast, welt, files_dir):
    """Die Bilder haengen am selben Startdatum wie das Formular."""
    files_dir.mkdir(parents=True, exist_ok=True)
    (files_dir / "reg1a-bild.png").write_bytes(PNG)
    from diakronos_app.models.diakonos import Anmeldeformular, Registrierungslink

    welt.get(Anmeldeformular, FORM).hintergrundbild = "reg1a-bild.png"
    welt.get(Registrierungslink, LINK).gueltig_ab = dt.date.fromisoformat(_morgen())
    welt.commit()

    r = gast.get(f"/public/registrierung/{SLUG}/bild/hintergrund")
    assert r.status_code == 403
    assert "Anmeldung ab" in (r.json().get("message") or "")


def test_kein_bild_gesetzt_ist_404(gast, welt, files_dir):
    assert gast.get(f"/public/registrierung/{SLUG}/bild/banner").status_code == 404


def test_nur_rasterbilder_als_formularbild(admin_client, welt, files_dir):
    """SVG und HTML werden nie als Formularbild ausgeliefert oder gespeichert."""
    files_dir.mkdir(parents=True, exist_ok=True)
    (files_dir / "reg1a-svg.png").write_bytes(HTML_DATEI)

    r = admin_client.post(
        f"/api/method/{MODUL_HUB}.update_anmeldeformular",
        data={"formular_id": FORM, "banner_bild_datei": "reg1a-svg.png"},
    )
    assert r.status_code == 417, r.text
    assert "Bilddatei" in (r.json().get("message") or "")


def test_erfundener_dateiname_wird_abgelehnt(admin_client, welt, files_dir):
    r = admin_client.post(
        f"/api/method/{MODUL_HUB}.update_anmeldeformular",
        data={"formular_id": FORM, "banner_bild_datei": "../../etc/passwd"},
    )
    assert r.status_code == 417, r.text


def test_bild_entfernen_leert_die_spalte(admin_client, welt, files_dir):
    files_dir.mkdir(parents=True, exist_ok=True)
    (files_dir / "reg1a-bild.png").write_bytes(PNG)
    from diakronos_app.models.diakonos import Anmeldeformular

    welt.get(Anmeldeformular, FORM).bannerbild = "reg1a-bild.png"
    welt.commit()

    r = admin_client.post(
        f"/api/method/{MODUL_HUB}.update_anmeldeformular",
        data={"formular_id": FORM, "bilder_entfernen": "banner"},
    )
    assert r.status_code == 200, r.text
    assert welt.get(Anmeldeformular, FORM).bannerbild is None


def test_bild_entfernen_lehnt_unbekannte_rolle_ab(admin_client, welt):
    r = admin_client.post(
        f"/api/method/{MODUL_HUB}.update_anmeldeformular",
        data={"formular_id": FORM, "bilder_entfernen": "logo"},
    )
    assert r.status_code == 417, r.text


def test_jpeg_wird_ebenfalls_ausgeliefert(admin_client, welt, files_dir):
    hoch = _upload(
        admin_client, name="hinten.jpg", mime="image/jpeg", inhalt=JPEG,
        doctype="Anmeldeformular", docname=FORM,
    )
    dateiname = hoch.json()["message"]["file_url"].rsplit("/", 1)[-1]
    admin_client.post(
        f"/api/method/{MODUL_HUB}.update_anmeldeformular",
        data={"formular_id": FORM, "hintergrund_bild_datei": dateiname},
    )

    r = admin_client.get(f"/public/registrierung/{SLUG}/bild/hintergrund")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].split(";")[0] == "image/jpeg"


def test_kopf_endpunkt_liefert_beschreibung_und_bilder(admin_client, welt):
    from diakronos_app.models.diakonos import Anmeldeformular

    welt.get(Anmeldeformular, FORM).beschreibung = "Kurz"
    welt.commit()

    r = admin_client.get(
        f"/api/method/{MODUL_HUB}.get_anmeldeformular_kopf", params={"formular_id": FORM}
    )
    assert r.status_code == 200, r.text
    kopf = r.json()["message"]
    assert kopf["beschreibung"] == "Kurz"
    assert kopf["bannerbild"] == ""
    assert kopf["banner_bild_url"] == ""


# ════════════════════════════════════════════════════════════════════════════
# 4 — Nacharbeit Operator-Review (REG-1a): Bild-Lebenszyklus, Klartext,
#     Herkunft der Datei, Zeitzone des Datums
# ════════════════════════════════════════════════════════════════════════════
#
# Begruendung der Faelle (Operator-Review nach dem ersten Durchlauf):
#
#   (1) DSGVO — beim Entfernen/Ersetzen/Loeschen bleibt die Bilddatei samt
#       `File`-Datensatz liegen. Ein Bild ohne Formular ist ein Datenrest ohne
#       Zweck, bei Fotos mit Personen ein Loeschbefund.
#   (2) Die Beschreibung wird mit `&lt;`/`&gt;` gespeichert; Besucher lesen
#       dann woertlich „&lt;“. Escaping ist Sache der Anzeige (`{{ }}`).
#   (3) `pruefe_bilddatei` akzeptierte JEDE Datei unter `files_dir` — auch
#       fremde, private Dateien eines Mitglieds. Zulaessig ist nur, was ueber
#       `upload_file` angelegt wurde (es gibt einen `File`-Datensatz).
#   (4) `schreibe_bild` war toter Code (kein Aufrufer) und umging damit den
#       `File`-Datensatz — ersatzlos entfernt.
#   (5) Das Start-/Enddatum wurde in der Zeitzone des Containers (UTC)
#       bestimmt, nicht in der der Gemeinde (Europe/Berlin) — um Mitternacht
#       galt der Link damit zwei Stunden zu lang bzw. zu kurz.


def _file_zeilen(name: str) -> list:
    """Alle `File`-Datensaetze zu einem Dateinamen (frische Lese-Sitzung)."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    with SessionLocal() as lese:
        return (
            lese.query(FileModel)
            .filter(FileModel.file_url.in_([f"/files/{name}", f"/private/files/{name}"]))
            .all()
        )


def _datei_existiert(files_dir, name: str) -> bool:
    return (files_dir / name).is_file()


def _hochgeladen(client, name="bild.png", mime="image/png", inhalt=PNG, formular=None) -> str:
    """Upload ueber den vorhandenen Weg -> Dateiname.

    REG-1c: `formular` haengt die Datei an ein Anmeldeformular (so entsteht ein
    Formularbild). Ohne Angabe entsteht eine Datei OHNE Bezug — genau die, die
    der Server seither ablehnt.
    """
    zusatz = {}
    if formular is not None:
        zusatz["doctype"] = "Anmeldeformular"
        zusatz["docname"] = formular
    hoch = _upload(client, name=name, mime=mime, inhalt=inhalt, **zusatz)
    assert hoch.status_code == 200, hoch.text
    return hoch.json()["message"]["file_url"].rsplit("/", 1)[-1]


def _zuordnen(client, **data):
    """Bild einem Formular zuordnen (Administrator)."""
    return client.post(
        f"/api/method/{MODUL_HUB}.update_anmeldeformular",
        data={"formular_id": FORM, **data},
    )


def _zweites_formular(name: str, **werte) -> None:
    """Ein zweites Anmeldeformular anlegen (frische Sitzung)."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Anmeldeformular

    sess = SessionLocal()
    try:
        sess.add(
            Anmeldeformular(
                name=name,
                bezeichnung=name,
                mit_kinder=False,
                mit_gaesten=False,
                docstatus=0,
                idx=0,
                **werte,
            )
        )
        sess.commit()
    finally:
        sess.close()


# ── (1) Datei + File-Datensatz beim Entfernen/Ersetzen/Loeschen ────────────


def test_bild_entfernen_loescht_datei_und_file_datensatz(admin_client, welt, files_dir):
    """„Bild entfernen“ raeumt die Datei und ihren `File`-Datensatz mit weg."""
    dateiname = _hochgeladen(admin_client, formular=FORM)
    assert _zuordnen(admin_client, banner_bild_datei=dateiname).status_code == 200

    assert _file_zeilen(dateiname), "Vorbedingung: Upload legt einen File-Datensatz an"
    assert _datei_existiert(files_dir, dateiname)

    r = _zuordnen(admin_client, bilder_entfernen="banner")
    assert r.status_code == 200, r.text

    assert _file_zeilen(dateiname) == []
    assert not _datei_existiert(files_dir, dateiname)


def test_bild_ersetzen_loescht_das_alte_bild(admin_client, welt, files_dir):
    """Ein neues Banner ersetzt das alte — das alte wird geloescht, nicht gehortet."""
    alt = _hochgeladen(admin_client, name="alt.png", formular=FORM)
    neu = _hochgeladen(admin_client, name="neu.png", formular=FORM)
    assert _zuordnen(admin_client, banner_bild_datei=alt).status_code == 200
    assert _zuordnen(admin_client, banner_bild_datei=neu).status_code == 200

    assert _file_zeilen(alt) == []
    assert not _datei_existiert(files_dir, alt)
    # Das neue Bild bleibt — es ist jetzt das Banner.
    assert _file_zeilen(neu) != []
    assert _datei_existiert(files_dir, neu)


def test_gemeinsam_genutztes_bild_bleibt_erhalten(admin_client, welt, files_dir):
    """Nutzt ein ZWEITES Formular dieselbe Datei, wird sie nicht geloescht."""
    dateiname = _hochgeladen(admin_client, name="gemeinsam.png", formular=FORM)
    _zweites_formular("AF-REG1A-ZWEI", bannerbild=dateiname)

    assert _zuordnen(admin_client, banner_bild_datei=dateiname).status_code == 200
    r = _zuordnen(admin_client, bilder_entfernen="banner")
    assert r.status_code == 200, r.text

    assert _datei_existiert(files_dir, dateiname), "anderes Formular nutzt das Bild noch"
    assert _file_zeilen(dateiname) != []


def test_formular_loeschen_loescht_seine_bilder(admin_client, welt, files_dir):
    """Formular loeschen nimmt die eigenen Bilder mit (Datei + `File`-Datensatz)."""
    dateiname = _hochgeladen(admin_client, name="bannerloeschen.png", formular="AF-REG1A-DEL")
    _zweites_formular("AF-REG1A-DEL", bannerbild=dateiname)

    r = admin_client.post(
        f"/api/method/{MODUL_HUB}.delete_anmeldeformular",
        data={"formular_id": "AF-REG1A-DEL", "bestaetigt": 1},
    )
    assert r.status_code == 200, r.text

    assert not _datei_existiert(files_dir, dateiname)
    assert _file_zeilen(dateiname) == []


# ── (2) Beschreibung: Klartext, kein vorab maskiertes HTML ─────────────────


def test_beschreibung_bleibt_klartext_mit_spitzen_klammern(admin_client, welt):
    """`Kinder < 6` bleibt lesbar: gespeichert wird Klartext, nicht `&lt;`.

    Escaping gehoert in die Anzeige (`{{ }}` in Vue), nicht in den Speicher —
    sonst liest der Besucher woertlich „&lt;“.
    """
    from diakronos_app.anmeldung.formularbilder import normalisiere_beschreibung
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Anmeldeformular

    text = "Kinder < 6 sind willkommen; Fragen an a@b.de > 5 Tage vorher."
    assert normalisiere_beschreibung(text) == text

    r = _zuordnen(admin_client, beschreibung=text)
    assert r.status_code == 200, r.text

    with SessionLocal() as lese:
        gespeichert = lese.get(Anmeldeformular, FORM).beschreibung
    assert gespeichert == text
    assert "&lt;" not in gespeichert and "&amp;" not in gespeichert


def test_beschreibung_wird_beim_anzeigen_nicht_doppelt_maskiert(gast, welt):
    """Der Besucher-Text enthaelt kein vorab maskiertes `&lt;` (Anzeige escapet)."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Anmeldeformular

    sess = SessionLocal()
    try:
        sess.get(Anmeldeformular, FORM).beschreibung = "Kinder < 6 willkommen"
        sess.commit()
    finally:
        sess.close()

    r = gast.get(f"/api/method/{MODUL}.validate_token", params={"token": SLUG})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["beschreibung"] == "Kinder < 6 willkommen"


def test_beschreibung_html_bleibt_reiner_text(gast, welt):
    """HTML im Text kommt als ZEICHEN an — nie als Markup, nie maskiert."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Anmeldeformular

    sess = SessionLocal()
    try:
        sess.get(Anmeldeformular, FORM).beschreibung = "<script>alert(1)</script>"
        sess.commit()
    finally:
        sess.close()

    r = gast.get(f"/api/method/{MODUL}.validate_token", params={"token": SLUG})
    assert r.status_code == 200, r.text
    # Escaping macht die Anzeige (`{{ }}`); hier steht der reine Text.
    assert r.json()["message"]["beschreibung"] == "<script>alert(1)</script>"


# ── (3) Nur Dateien aus DEM Formular-Upload sind zulaessig ─────────────────


def test_fremde_datei_aus_files_dir_wird_abgelehnt(admin_client, welt, files_dir):
    """Eine von Hand abgelegte Datei (kein `File`-Datensatz) ist kein Upload."""
    files_dir.mkdir(parents=True, exist_ok=True)
    (files_dir / "reg1a-fremd.png").write_bytes(PNG)

    r = _zuordnen(admin_client, banner_bild_datei="reg1a-fremd.png")
    assert r.status_code == 417, r.text
    assert "hochgeladen" in (r.json().get("message") or "")


def test_private_datei_eines_mitglieds_wird_abgelehnt(admin_client, welt, files_dir):
    """Private Dateien (Owner = Mitglied) werden nie zum oeffentlichen Bild.

    REG-1b: Die Herkunft entscheidet ueber die ROLLE des Eigentuemers, nicht
    ueber „ist es der gerade handelnde Admin“: Dateien von Verwaltungskonten
    sind zulaessig, Dateien von Mitgliedern nicht.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    files_dir.mkdir(parents=True, exist_ok=True)
    name = "reg1a-privat.png"
    (files_dir / name).write_bytes(PNG)

    sess = SessionLocal()
    try:
        sess.add(
            FileModel(
                name="FRG1A00001",
                file_name="privat.png",
                file_url=f"/files/{name}",
                is_private=True,
                owner="mitglied@example.org",
                docstatus=0,
                idx=0,
            )
        )
        sess.commit()
    finally:
        sess.close()

    r = _zuordnen(admin_client, banner_bild_datei=name)
    assert r.status_code == 417, r.text


def test_eigene_formulardatei_eines_anderen_administrators_ist_zulaessig(
    admin_client, welt, files_dir
):
    """Eine AM FORMULAR angehaengte Datei bleibt nutzbar — auch fuer andere Admins.

    REG-1b hatte den Fall „ein ZWEITER Administrator kann ein vorhandenes Bild
    nicht mehr zuordnen“ gemeldet und die Pruefung auf „jede Datei eines
    Verwalters“ gelockert. REG-1c nimmt die Lockerung zurueck und entscheidet
    stattdessen ueber die ZUORDNUNG: diese Datei ist an genau dieses Formular
    angehaengt (`attached_to_doctype`/`attached_to_name`) und bleibt deshalb
    zulaessig, unabhaengig davon, WER sie hochgeladen hat.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel, HasRole, User

    zweiter = "reg1a-admin2@example.org"
    sess = SessionLocal()
    try:
        if sess.get(User, zweiter) is None:
            sess.add(User(name=zweiter, email=zweiter, full_name="Admin 2", enabled=True))
            sess.add(
                HasRole(
                    name=f"{zweiter}-MA",
                    parent=zweiter,
                    parenttype="User",
                    parentfield="roles",
                    idx=1,
                    role="Mitgliederadministrator",
                )
            )
        files_dir.mkdir(parents=True, exist_ok=True)
        name = "reg1a-admin2.png"
        (files_dir / name).write_bytes(PNG)
        sess.add(
            FileModel(
                name="FRG1A00003",
                file_name="admin2.png",
                file_url=f"/files/{name}",
                is_private=True,
                owner=zweiter,
                attached_to_doctype="Anmeldeformular",
                attached_to_name=FORM,
                docstatus=0,
                idx=0,
            )
        )
        sess.commit()
    finally:
        sess.close()

    r = _zuordnen(admin_client, banner_bild_datei=name)
    assert r.status_code == 200, r.text


def test_fremde_verwalterdatei_wird_abgelehnt(admin_client, welt, files_dir):
    """REG-1c (1): Die private Datei eines Verwalters ist KEIN Formularbild.

    Die Lockerung aus REG-1b („jede private Datei eines Verwalters zulaessig“)
    ist zurueckgenommen. Diese Datei stammt von einem Verwalter, haengt aber an
    einem MITGLIED (z. B. Profilfoto) — sie darf nie oeffentliches Formularbild
    werden. Der Upload selbst ist zulaessig (Verwalter duerfen anhaengen); die
    ZUORDNUNG zum Formular wird verweigert.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel, HasRole, User

    verwalter = "reg1c-admin@example.org"
    sess = SessionLocal()
    try:
        if sess.get(User, verwalter) is None:
            sess.add(User(name=verwalter, email=verwalter, full_name="Verwalter", enabled=True))
            sess.add(
                HasRole(
                    name=f"{verwalter}-MA",
                    parent=verwalter,
                    parenttype="User",
                    parentfield="roles",
                    idx=1,
                    role="Mitgliederadministrator",
                )
            )
        files_dir.mkdir(parents=True, exist_ok=True)
        name = "reg1c-fremd.png"
        (files_dir / name).write_bytes(PNG)
        sess.add(
            FileModel(
                name="FRG1C00001",
                file_name="foto.png",
                file_url=f"/files/{name}",
                is_private=True,
                owner=verwalter,
                attached_to_doctype="Mitglied",
                attached_to_name="MITGLIED-1",
                docstatus=0,
                idx=0,
            )
        )
        sess.commit()
    finally:
        sess.close()

    r = _zuordnen(admin_client, banner_bild_datei=name)
    assert r.status_code == 417, r.text


def test_datei_ohne_bezug_wird_abgelehnt(admin_client, welt, files_dir):
    """REG-1c (1): Ein Upload ohne `doctype`/`docname` haengt an nichts -> abgelehnt.

    Der Editor schickt die Zuordnung seit REG-1c mit; eine Datei ohne Bezug
    (z. B. ein Upload aus einem anderen Formular des Editors) ist kein Bild
    DIESES Formulars.
    """
    dateiname = _hochgeladen(admin_client, name="ohnebezug.png")  # ohne formular=
    r = _zuordnen(admin_client, banner_bild_datei=dateiname)
    assert r.status_code == 417, r.text


def test_datei_eines_anderen_formulars_wird_abgelehnt(admin_client, welt, files_dir):
    """REG-1c (1): Ein Bild, das an einem ANDEREN Formular haengt, bleibt dort.

    Sonst liesse sich ein einmal zugeordnetes Bild eines fremden Formulars
    uebernehmen, ohne dass es dort entfernt wird.
    """
    _zweites_formular("AF-REG1C-ANDERES")
    dateiname = _hochgeladen(
        admin_client, name="anderesformular.png", formular="AF-REG1C-ANDERES"
    )

    r = _zuordnen(admin_client, banner_bild_datei=dateiname)
    assert r.status_code == 417, r.text


def test_eigene_formulardatei_wird_angenommen(admin_client, welt, files_dir):
    """REG-1c (1): Der regulaere Weg — Upload MIT `docname` — wird angenommen."""
    dateiname = _hochgeladen(admin_client, name="eigenes-ok.png", formular=FORM)

    r = _zuordnen(admin_client, banner_bild_datei=dateiname)
    assert r.status_code == 200, r.text

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Anmeldeformular

    with SessionLocal() as lese:
        assert lese.get(Anmeldeformular, FORM).bannerbild == dateiname


def test_umbenannte_datei_wird_abgelehnt(admin_client, welt, files_dir):
    """Datei umbenannt -> der `File`-Datensatz passt nicht mehr -> abgelehnt."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    files_dir.mkdir(parents=True, exist_ok=True)
    name = "reg1a-umbenannt.png"
    (files_dir / name).write_bytes(PNG)

    sess = SessionLocal()
    try:
        sess.add(
            FileModel(
                name="FRG1A00002",
                file_name="original.png",
                file_url="/files/reg1a-original.png",
                is_private=False,
                owner="reg1a-admin@example.org",
                docstatus=0,
                idx=0,
            )
        )
        sess.commit()
    finally:
        sess.close()

    r = _zuordnen(admin_client, banner_bild_datei=name)
    assert r.status_code == 417, r.text


def test_schreibe_bild_ist_entfernt():
    """(4) `schreibe_bild` war toter Code — und umging den `File`-Datensatz."""
    from diakronos_app.anmeldung import formularbilder

    assert not hasattr(formularbilder, "schreibe_bild")


# ── (5) Zeitzone der Gemeinde fuer „gueltig ab“ / „gueltig bis“ ────────────


def test_datum_wird_in_der_zeitzone_der_gemeinde_bestimmt(monkeypatch, welt):
    """Um Mitternacht gilt das Datum der GEMEINDE, nicht das des Containers.

    In UTC ist es am 26.10. noch der 25.10. (00:30 Europe/Berlin ist 22:30
    UTC am Vortag). Wer `date.today()` des Containers nimmt, laesst den Link
    damit zwei Stunden zu spaet beginnen und zwei Stunden zu frueh enden.
    """
    import importlib

    from diakronos_app.api import registrierung as mod
    from diakronos_app.models.diakonos import Registrierungslink

    heute_ort = dt.date(2026, 10, 26)
    monkeypatch.setattr(
        mod, "heute_ortszeit", lambda: dt.datetime(2026, 10, 26, 0, 30), raising=False
    )
    importlib.invalidate_caches()
    assert mod._heute_gemeinde() == heute_ort

    sess = welt
    # Genau HEUTE (Ortszeit) -> der Link ist gueltig, obwohl er in UTC noch
    # „morgen“ waere.
    sess.get(Registrierungslink, LINK).gueltig_ab = heute_ort
    sess.get(Registrierungslink, LINK).gueltig_bis = heute_ort
    sess.commit()

    # Wirft NICHT: der Link gilt am Tag selbst schon (Ortszeit), obwohl er in
    # UTC noch „morgen“ waere.
    link = mod._validate_token(SLUG)
    assert link["name"] == LINK


def test_zeitzone_hat_eine_einzige_quelle():
    """REG-1c (2): Anzeige und Wirkung rechnen ueber DIESELBE Funktion.

    Vorher stand die Zeitzonen-Rechnung zweimal im Code
    (``anmeldung.registrierungslink.heute_gemeinde`` und
    ``api.registrierung.heute_ortszeit``). Gleich waren sie nur, solange
    niemand eine davon aenderte. Jetzt gibt es die Rechnung genau einmal;
    ``api.registrierung`` reicht sie durch.
    """
    import inspect

    from diakronos_app.anmeldung import registrierungslink as link_mod
    from diakronos_app.api import registrierung as reg_mod

    # Die Uhr steht nur an einer Stelle im Quelltext.
    assert "now(zone)" in inspect.getsource(link_mod.jetzt_gemeinde)
    assert "ZoneInfo(" in inspect.getsource(link_mod.jetzt_gemeinde)
    assert "ZoneInfo" not in inspect.getsource(reg_mod.heute_ortszeit)
    assert "datetime.now(" not in inspect.getsource(reg_mod.heute_ortszeit)

    # Und der Weg ist derselbe: was der Test festnagelt, kommt dort an.
    jetzt = reg_mod.heute_ortszeit()
    assert reg_mod._heute_gemeinde() == jetzt.date()
    assert link_mod.heute_gemeinde() == jetzt.date()


def test_gueltig_ab_nach_gueltig_bis_wird_abgelehnt(admin_client, welt):
    """Ein Link, der erst nach seinem Ablauf beginnt, ist ein Eingabefehler."""
    r = admin_client.post(
        f"/api/method/{MODUL_LINK}.create_link",
        data={
            "bezeichnung": "Unmoeglich",
            "typ": "Mitglied-Registrierung",
            "gueltig_ab": "2026-12-01",
            "gueltig_bis": "2026-11-01",
            "ohne_ablauf": 1,
        },
    )
    assert r.status_code == 417, r.text
    assert "gültig ab" in (r.json().get("message") or "").lower()


def test_update_link_prueft_die_reihenfolge_der_daten(admin_client, welt):
    """Auch beim Aendern: „gueltig ab“ darf nicht hinter „gueltig bis“ liegen."""
    from diakronos_app.models.diakonos import Registrierungslink

    sess = welt
    sess.get(Registrierungslink, LINK).gueltig_bis = dt.date(2026, 11, 1)
    sess.commit()

    r = admin_client.post(
        f"/api/method/{MODUL_LINK}.update_link",
        data={"link_id": LINK, "gueltig_ab": "2026-12-01"},
    )
    assert r.status_code == 417, r.text
    assert "gültig ab" in (r.json().get("message") or "").lower()
