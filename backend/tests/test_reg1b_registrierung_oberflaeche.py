"""REG-1b — Formular-VORSCHAU fuer die Verwaltung.

Karte REG-1b, Punkt 3: „Vorschau-Knopf im Formular-Editor: zeigt das Formular
genau so, wie Besucher es sehen (gleiche Komponente wie die oeffentliche
Registrierungsseite, ohne Absenden).“

Der Frontend-Teil (dieselbe Komponente) steht in
``frontend/tests/reg1b-registrierung-oberflaeche.test.mjs``. Hier wird der
SERVER-Teil geprueft — die Daten, die die Vorschau anzeigt:

  1. **Nur Verwaltung.** Ohne Adminrolle gibt es keine Vorschau (und keine
     Preisgabe von Feldern/Bildern), mit Adminrolle schon.
  2. **Nichts erfunden.** Felder, Schalter, Beschreibung und Bilder kommen aus
     dem gespeicherten Formular — ueber DENSELBEN Weg wie die oeffentliche
     Anzeige (``_formular_felder``), damit Vorschau und Wirklichkeit nicht
     auseinanderlaufen.
  3. **Text, kein HTML.** Die Beschreibung wird als Klartext geliefert (auch
     ``<``/``>``), inklusive der Einwilligungstexte der oeffentlichen Seite.
  4. **Bilder nur fuer Administratoren.** Der Vorschau-Token
     (``vorschau-<formular>``) gilt ausschliesslich fuer Administratoren; ein
     Besucher mit demselben Token bekommt dieselbe Verweigerung wie bei jedem
     falschen Token.

Alle Tests laufen ohne Netz (``patched_db``, SQLite) und ohne Betriebsdaten —
Regel 11 der Karte.
"""

from __future__ import annotations

import io

import pytest

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24

MODUL = "diakronos.diakonos.api.registrierung_vorschau"
MODUL_BILD = "public"
FORM = "AF-REG1B"
ADMIN = "reg1b-admin@example.org"
SLUG = "reg1bslug"
LINK = "RL-REG1B"


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def files_dir(tmp_path, monkeypatch):
    """Eigene Ablage je Test — nie das Betriebs-Volume (Regel 11)."""
    from diakronos_app.settings import settings

    ziel = tmp_path / "files"
    monkeypatch.setattr(settings, "files_dir", str(ziel))
    return ziel


@pytest.fixture()
def welt(patched_db):
    """Ein Anmeldeformular mit Beschreibung, Feld und Schaltern."""
    from diakronos_app.models.diakonos import Anmeldeformular

    sess = patched_db()
    sess.add(
        Anmeldeformular(
            name=FORM,
            bezeichnung="Standard",
            mit_kinder=1,
            mit_gaesten=0,
            beschreibung="Kinder < 6 willkommen.",
            docstatus=0,
            idx=0,
        )
    )
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
def gast(patched_db, fake_redis):
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    with TestClient(app) as c:
        yield c


def _feld(label: str, **werte) -> None:
    """Ein Feld am Formular anlegen (Kind-Tabelle `Anmeldeformular Feld`)."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import AnmeldeformularFeld

    sess = SessionLocal()
    try:
        sess.add(
            AnmeldeformularFeld(
                name=f"{FORM}-{label}",
                parent=FORM,
                parenttype="Anmeldeformular",
                parentfield="felder",
                idx=1,
                label=label,
                feldtyp="Auswahl",
                optionen="Ja\nNein",
                pflichtfeld=True,
                fuer_gaeste=False,
                fuer_kinder=False,
                **werte,
            )
        )
        sess.commit()
    finally:
        sess.close()


def _vorschau(client, **daten):
    return client.post(f"/api/method/{MODUL}.get_formular_vorschau", data=daten)


# ════════════════════════════════════════════════════════════════════════════
# 1 — Nur Verwaltung
# ════════════════════════════════════════════════════════════════════════════


def test_vorschau_braucht_adminrechte(gast, welt):
    """Ein Besucher bekommt keine Vorschau — und keine Feldliste."""
    r = gast.post(f"/api/method/{MODUL}.get_formular_vorschau", data={"formular_id": FORM})
    assert r.status_code in (401, 403), r.text
    assert "felder" not in (r.json().get("message") or "")


def test_vorschau_liefert_felder_des_formulars(admin_client, welt):
    """Mit Adminrolle: Felder, Schalter und Beschreibung des Formulars."""
    _feld("T-Shirt-Größe")

    r = _vorschau(admin_client, formular_id=FORM)
    assert r.status_code == 200, r.text
    daten = r.json()["message"]

    assert daten["mit_kinder"] == 1
    assert daten["mit_gaesten"] == 0
    assert daten["beschreibung"] == "Kinder < 6 willkommen."
    assert [f["label"] for f in daten["felder"]] == ["T-Shirt-Größe"]
    assert daten["felder"][0]["optionen"] == "Ja\nNein"
    assert daten["bezeichnung"] == "Standard"


def test_vorschau_zeigt_den_einwilligungstext_der_oeffentlichen_seite(admin_client, welt):
    """Die Vorschau nennt denselben Wortlaut, den die Person bestaetigt."""
    from diakronos_app import spa

    r = _vorschau(admin_client, formular_id=FORM)
    assert r.status_code == 200, r.text
    daten = r.json()["message"]
    assert "texte" in daten, "die Einwilligungstexte fehlen in der Vorschau"
    assert daten["texte"] == spa.oeffentliche_texte()
    assert "willkommenstext" in daten


def test_vorschau_ohne_formular_zeigt_die_editor_angaben(admin_client, welt):
    """Noch nicht gespeichert: die Angaben aus dem Editor werden gezeigt."""
    import json

    felder = [{"label": "Vegetarisch", "feldtyp": "Ja-Nein", "pflichtfeld": 1}]
    r = _vorschau(
        admin_client,
        felder=json.dumps(felder),
        mit_kinder=1,
        mit_gaesten=1,
        beschreibung="Erster Entwurf",
    )
    assert r.status_code == 200, r.text
    daten = r.json()["message"]
    assert [f["label"] for f in daten["felder"]] == ["Vegetarisch"]
    assert daten["felder"][0]["feldtyp"] == "Ja-Nein"
    assert daten["felder"][0]["pflichtfeld"] == 1
    assert daten["mit_kinder"] == 1
    assert daten["mit_gaesten"] == 1
    assert daten["beschreibung"] == "Erster Entwurf"
    # Ohne Formular gibt es keine Bilder — nichts wird erfunden.
    assert daten["banner_bild"] == ""
    assert daten["hintergrund_bild"] == ""


def test_vorschau_ohne_felder_ist_leer(admin_client, welt):
    """Ohne Angaben: leere Feldliste, aber kein Fehler."""
    r = _vorschau(admin_client)
    assert r.status_code == 200, r.text
    daten = r.json()["message"]
    assert daten["felder"] == []
    assert daten["beschreibung"] == ""


def test_vorschau_unbekanntes_formular_meldet_sich(admin_client, welt):
    """Ein erfundenes Formular ergibt eine verstaendliche Meldung, keinen 500er."""
    r = _vorschau(admin_client, formular_id="AF-GIBT-ES-NICHT")
    # Der Compat-Router meldet eine fehlende Zeile als 404 (DoesNotExistError).
    assert r.status_code == 404, r.text
    assert "existiert nicht" in (r.json().get("message") or "").lower()


# ════════════════════════════════════════════════════════════════════════════
# 2 — Bilder: Vorschau-Token nur fuer Administratoren
# ════════════════════════════════════════════════════════════════════════════


def _hochgeladen(client, name: str = "banner.png", formular: str = FORM) -> str:
    """Bild ueber den vorhandenen Upload-Weg, AM Formular angehaengt (REG-1c)."""
    hoch = client.post(
        "/api/method/upload_file",
        files={"file": (name, io.BytesIO(PNG), "image/png")},
        data={"doctype": "Anmeldeformular", "docname": formular},
    )
    assert hoch.status_code == 200, hoch.text
    return hoch.json()["message"]["file_url"].rsplit("/", 1)[-1]


def _zuordnen(client, **daten):
    return client.post(
        "api/method/diakronos.diakonos.api.admin_hub.update_anmeldeformular",
        data={"formular_id": FORM, **daten},
    )


def test_oeffentlicher_bildpfad_traegt_den_link_token(admin_client, welt, files_dir):
    """REG-1b (Befund aus der Abnahme): die OEFFENTLICHE Seite bekommt den Bildpfad.

    `_validate_token` liest den Link ueber einen Spaltenabzug (`_LINK_FIELDS`).
    Fehlte dort `slug`, war der Pfad still leer — die Seite zeigte trotz
    hinterlegtem Bild weder Banner noch Hintergrund.
    """
    from diakronos_app.models.diakonos import Registrierungslink

    dateiname = _hochgeladen(admin_client)
    assert _zuordnen(admin_client, banner_bild_datei=dateiname).status_code == 200

    sess = welt
    sess.add(
        Registrierungslink(
            name=LINK,
            bezeichnung="Einladung",
            typ="Mitglied-Registrierung",
            aktiv=True,
            slug=SLUG,
            max_anmeldungen=0,
            anmeldungen_count=0,
            anmeldeformular=FORM,
            docstatus=0,
            idx=0,
        )
    )
    sess.commit()

    r = admin_client.get(
        "/api/method/diakronos.diakonos.api.registrierung.validate_token",
        params={"token": SLUG},
    )
    assert r.status_code == 200, r.text
    assert r.json()["message"]["banner_bild"] == f"/public/registrierung/{SLUG}/bild/banner"


def test_vorschau_liefert_bildpfad_ueber_den_vorschau_token(admin_client, welt, files_dir):
    """Das Banner der Vorschau haengt am Vorschau-Token, nicht an einem Link."""
    dateiname = _hochgeladen(admin_client)
    antwort = _zuordnen(admin_client, banner_bild_datei=dateiname)
    assert antwort.status_code == 200, antwort.text

    r = _vorschau(admin_client, formular_id=FORM)
    daten = r.json()["message"]
    assert daten["banner_bild"] == f"/public/registrierung/vorschau-{FORM}/bild/banner"


def test_vorschau_bild_ist_fuer_den_admin_abrufbar(admin_client, welt, files_dir):
    """Der angemeldete Administrator sieht sein Bild wirklich."""
    dateiname = _hochgeladen(admin_client)
    assert _zuordnen(admin_client, banner_bild_datei=dateiname).status_code == 200

    r = admin_client.get(f"/public/registrierung/vorschau-{FORM}/bild/banner")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("image/")
    assert bytes(r.content) == PNG


def test_vorschau_bild_ist_fuer_besucher_gesperrt(gast, welt, files_dir):
    """Ein Besucher mit dem Vorschau-Token bekommt nur die uebliche Verweigerung.

    Wichtig: dieselbe Meldung wie bei jedem falschen Token — sonst verriete die
    Antwort, dass es dieses Formular gibt.
    """
    r = gast.get(f"/public/registrierung/vorschau-{FORM}/bild/banner")
    assert r.status_code == 403, r.text
    assert "Registrierungslink" in (r.json().get("message") or "")


def test_vorschau_token_ohne_formular_ist_ungueltig(admin_client, welt):
    """`vorschau-` allein ist kein Token."""
    r = admin_client.get("/public/registrierung/vorschau-/bild/banner")
    assert r.status_code == 403, r.text


def test_vorschau_token_eines_unbekannten_formulars_ist_ungueltig(admin_client, welt):
    """REG-1c (3): `vorschau-<id>` prueft, dass das Formular EXISTIERT.

    Ohne diese Pruefung nahm `_validate_token` jede geratene Kennung an und
    lieferte eine „leere“ Anzeige statt einer klaren Absage. Die Antwort ist
    dieselbe Verweigerung wie bei jedem falschen Token und traegt keinen
    Hinweis auf vorhandene Formulare.
    """
    from diakronos_app.frappe_compat.exceptions import (
        PermissionError as FrappePermissionError,
    )
    from diakronos_app.api.registrierung import _validate_token

    r = admin_client.get("/public/registrierung/vorschau-AF-GIBTESNICHT/bild/banner")
    assert r.status_code == 403, r.text
    assert "Registrierungslink" in (r.json().get("message") or "")

    # Derselbe Weg direkt: Verweigerung, kein „Link“-Objekt.
    with pytest.raises(FrappePermissionError):
        _validate_token(f"vorschau-AF-GIBTESNICHT", admin=True)

    # Und das VORHANDENE Formular bleibt gueltig (kein Ueberschuss an Strenge).
    vorhanden = _validate_token(f"vorschau-{FORM}", admin=True)
    assert isinstance(vorhanden, dict)
    assert vorhanden.get("anmeldeformular") == FORM


def test_echter_link_token_bleibt_unveraendert(admin_client, welt):
    """Die Vorschau aendert den oeffentlichen Weg nicht: ein Link-Slug wirkt wie bisher.

    Ein ``vorschau-``-Praefix am ECHTEN Slug darf nicht zum Formular greifen —
    sonst liesse sich ein fremdes Bild ueber einen geratenen Namen holen.
    """
    from diakronos_app.models.diakonos import Registrierungslink

    sess = welt
    sess.add(
        Registrierungslink(
            name=LINK,
            bezeichnung="Einladung",
            typ="Mitglied-Registrierung",
            aktiv=True,
            slug=SLUG,
            max_anmeldungen=0,
            anmeldungen_count=0,
            anmeldeformular=FORM,
            docstatus=0,
            idx=0,
        )
    )
    sess.commit()

    r = admin_client.get(f"/public/registrierung/{SLUG}/bild/banner")
    # Kein Bild hinterlegt -> 404 wie bisher (kein Absturz, keine Preisgabe).
    assert r.status_code == 404, r.text
