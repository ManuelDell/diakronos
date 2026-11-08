"""BS-3a NACHTRAG 2 — Datenschutz-Nachreview (Opus, 08.11.): HOCH 1 + MITTEL 2/3.

Diese Datei haelt AUSSCHLIESSLICH die Befunde des zweiten Reviews fest; die
Grundvertraege stehen weiter in ``test_bs3a_ansprechpartner.py``.

  * **HOCH 1 — Ausgetretene nie oeffentlich.** ``api/austritt.py`` setzt
    ``status = "Ausgetreten"`` (grosses A). Der Vergleich in
    ``einwilligung.ist_oeffentlich`` war exakt kleingeschrieben — eine
    ausgetretene Person MIT Einwilligung war damit weiter oeffentlich.
    Geprueft wird jetzt: jeder Status aus ``api.gruppen_auswahl.AUSGESCHIEDEN``
    in beliebiger Schreibweise (``casefold``) UND das Flag
    ``ausgeschlossen`` (``or``, nicht ``und``).
  * **MITTEL 2 — Foto-Route.** ``/website/bild/person/<kennung>`` prueft
    zusaetzlich ``ist_oeffentlich`` (nicht nur die Foto-Zustimmung) und dass
    die Person AKTUELL als Ansprechpartner ausgewaehlt ist. Der Abgleich
    laeuft ueber den Index der ausgewaehlten Personen, nicht ueber alle
    Mitglieder je Anfrage.
  * **MITTEL 3 — Audit.** ``meine_einwilligung_setzen`` schreibt JE
    geaendertem Feld GENAU EINEN Eintrag (keine ``elif``-Kette): ein Aufruf
    mit Einwilligung + Foto erzeugt zwei, „nur Foto" genau einen, alle drei
    Felder genau drei.

Netz (Kartenregel 11): ``patched_db`` (In-Memory-SQLite), ``fake_redis``;
kein Test greift auf ``settings.database_url`` zu, keiner spricht Primo an.
"""

from __future__ import annotations

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat import sitzungen  # noqa: F401 — Fixture-Naht
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import (
    Dienstbereich,
    DienstbereichVerantwortlicher,
    Mitglied,
)
# Der Name kommt aus dem MODUL-ATTRIBUT: an `...models.diakonos` haengt
# SQLAlchemy einen clsregistry-Proxy, auf dem ein spaeterer Import scheitert.
from diakronos_app.models import DSGVOEinwilligung
from diakronos_app.models.website_ansprechpartner import WebsiteAnsprechpartner

MODUL = "diakronos_app.api.website"
PFAD_EINW_SETZEN = f"{MODUL}.meine_einwilligung_setzen"
PFAD_OEFFENTLICH = "website.oeffentlich"

ADMIN_MAIL = "verwaltung@example.org"
PERSON_MAIL = "anna@example.org"
FREMD_MAIL = "bert@example.org"


# ── Helfer ─────────────────────────────────────────────────────────────────


def _benutzer(sess, email: str, rollen=()) -> str:
    if sess.get(User, email) is None:
        sess.add(User(name=email, email=email, full_name=email, enabled=True))
        for idx, rolle in enumerate(rollen, start=1):
            sess.add(
                HasRole(
                    name=f"{email}-{rolle}",
                    parent=email,
                    parenttype="User",
                    parentfield="roles",
                    role=rolle,
                    docstatus=0,
                    idx=idx,
                )
            )
    return email


def _mitglied(sess, name: str, *, user=None, vorname="Anna", nachname="Beispiel",
              foto=None, einwilligung=False, foto_zustimmung=False,
              anzeigename=None, status=None, ausgeschlossen=False) -> Mitglied:
    zeile = Mitglied(
        name=name,
        vorname=vorname,
        nachname=nachname,
        email=f"{name}@example.org",
        user=user,
        foto=foto,
        status=status,
        ausgeschlossen=ausgeschlossen,
        website_einwilligung=einwilligung,
        website_einwilligung_foto=foto_zustimmung,
        website_anzeigename=anzeigename,
    )
    sess.add(zeile)
    return zeile


@pytest.fixture()
def welt(patched_db):
    """Bestand: Verwaltung, zwei Mitglieder, ein Dienstbereich."""
    sess = patched_db()
    _benutzer(sess, ADMIN_MAIL, ("Website-Moderator",))
    _benutzer(sess, PERSON_MAIL, ("Mitglied",))
    _benutzer(sess, FREMD_MAIL, ("Mitglied",))

    _mitglied(sess, "anna", user=PERSON_MAIL, vorname="Anna", nachname="Beispiel")
    _mitglied(sess, "bert", user=FREMD_MAIL, vorname="Bert", nachname="Berger")

    sess.add(Dienstbereich(name="musik", ministry="Musik", sortierung=1))
    sess.add(
        DienstbereichVerantwortlicher(
            name="dbv-1", parent="musik", parenttype="Dienstbereich",
            parentfield="verantwortliche", user=PERSON_MAIL, idx=1,
        )
    )
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_benutzer(welt, patched_db, fake_redis):
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    erzeugt: list[TestClient] = []

    def _bauen(benutzer: str) -> TestClient:
        set_user(benutzer)
        sid, csrf = sitzungen.anlegen(benutzer)
        c = TestClient(app)
        c.__enter__()
        c.cookies.set("sid", sid)
        c.headers["X-Frappe-CSRF-Token"] = csrf
        erzeugt.append(c)
        return c

    yield _bauen
    for c in erzeugt:
        c.__exit__(None, None, None)


@pytest.fixture()
def gast(patched_db, fake_redis):
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    c = TestClient(app)
    c.__enter__()
    yield c
    c.__exit__(None, None, None)


def _oeffentlich(client, **params):
    return client.get(f"/api/method/{PFAD_OEFFENTLICH}.ansprechpartner", params=params)


def _auswahl_anlegen(sess) -> None:
    sess.add(
        WebsiteAnsprechpartner(
            art="dienstbereich", funktion="musik", bezeichnung="",
            postfach=None, sortierung=1,
        )
    )
    sess.commit()


def _kennung(name: str) -> str:
    from diakronos_app.website import oeffentlich_auswahl as auswahl

    return auswahl.oeffentliche_kennung("person", name)


def _audit(welt) -> list[tuple[str, str]]:
    """Alle DSGVO-Einwilligung-Eintraege der Person als ``(typ, aktion)``."""
    welt.expire_all()
    eintraege = welt.query(DSGVOEinwilligung).filter(
        DSGVOEinwilligung.mitglied == "anna"
    ).all()
    return sorted((str(e.typ), str(e.aktion)) for e in eintraege)


# ── HOCH 1: der Status schlaegt die Einwilligung ───────────────────────────


def test_ausgetreten_mit_einwilligung_ist_nicht_oeffentlich(patched_db):
    """DER Befund: ``status == "Ausgetreten"`` (so setzt es api/austritt.py)."""
    from diakronos_app.api.austritt import STATUS_AUSGETRETEN
    from diakronos_app.website import einwilligung as regel

    sess = patched_db()
    # Genau der Zustand nach `austritt.austritt_durchfuehren`: Status +
    # `ausgeschlossen` gesetzt. Die Einwilligung bleibt (aus welchem Grund
    # auch immer) auf „ja“ stehen.
    zeile = _mitglied(
        sess, "anna", einwilligung=True, foto_zustimmung=True,
        status=STATUS_AUSGETRETEN, ausgeschlossen=True,
    )
    sess.commit()
    assert STATUS_AUSGETRETEN == "Ausgetreten", "Statusmarke des Austritts geaendert"
    assert regel.ist_oeffentlich(zeile) is False, "Ausgetretener ist oeffentlich"
    assert regel.foto_erlaubt(zeile) is True, (
        "foto_erlaubt ist die reine Feldpruefung — die Sperre kommt aus ist_oeffentlich"
    )


def test_ausgetreten_ohne_ausgeschlossen_flag_ist_nicht_oeffentlich(patched_db):
    """Die Statusmarke allein genuegt — ``ausgeschlossen`` ist der ZWEITE Riegel."""
    from diakronos_app.website import einwilligung as regel

    sess = patched_db()
    zeile = _mitglied(
        sess, "anna", einwilligung=True, status="Ausgetreten", ausgeschlossen=False
    )
    sess.commit()
    assert regel.ist_oeffentlich(zeile) is False


def test_ausgeschlossen_flag_ohne_status_ist_nicht_oeffentlich(patched_db):
    """Und umgekehrt: das Flag allein sperrt — ``or``, nicht ``and``."""
    from diakronos_app.website import einwilligung as regel

    sess = patched_db()
    zeile = _mitglied(
        sess, "anna", einwilligung=True, status="Aktiv", ausgeschlossen=True
    )
    sess.commit()
    assert regel.ist_oeffentlich(zeile) is False


@pytest.mark.parametrize(
    "status",
    [
        "Ausgetreten",
        "AUSGETRETEN",
        "ausgetreten",
        "  Ausgetreten  ",
        "Verstorben",
        "VERSTORBEN",
        "verstorben",
        "Verstorben/Ausgetreten",
        "verstorben/ausgetreten",
        "Geloescht",
        "Gelöscht",
        "geloescht",
        "Ausgeschlossen",
        "AUSGESCHLOSSEN",
    ],
)
def test_status_schreibweise_egal(patched_db, status):
    """Jeder Status aus ``AUSGESCHIEDEN`` sperrt — in jeder Schreibweise."""
    from diakronos_app.website import einwilligung as regel

    sess = patched_db()
    zeile = _mitglied(sess, "anna", einwilligung=True, status=status)
    sess.commit()
    assert regel.status_ist_ausgeschieden(zeile) is True, status
    assert regel.ist_oeffentlich(zeile) is False, status


@pytest.mark.parametrize("status", [None, "", "Aktiv", "aktiv", "Gast", "Interessent"])
def test_gewaehnlicher_status_sperrt_nicht(patched_db, status):
    """Kein Ueberblocken: nur die bekannten Endstaende sperren."""
    from diakronos_app.website import einwilligung as regel

    sess = patched_db()
    zeile = _mitglied(sess, "anna", einwilligung=True, status=status)
    sess.commit()
    assert regel.status_ist_ausgeschieden(zeile) is False, status
    assert regel.ist_oeffentlich(zeile) is True, status


def test_statusliste_ist_die_bestehende_wahrheit():
    """Keine zweite Liste: NIE_OEFFENTLICH_STATUS kommt aus ``AUSGESCHIEDEN``."""
    from diakronos_app.api.gruppen_auswahl import AUSGESCHIEDEN
    from diakronos_app.website import einwilligung as regel

    assert frozenset(AUSGESCHIEDEN) <= regel.NIE_OEFFENTLICH_STATUS
    assert "ausgeschlossen" in regel.NIE_OEFFENTLICH_STATUS
    # Die Liste ist kleingeschrieben — der Vergleich faellt mit ``casefold``.
    assert regel.NIE_OEFFENTLICH_STATUS == frozenset(
        s.casefold() for s in regel.NIE_OEFFENTLICH_STATUS
    )


def test_ausgetretener_verschwindet_sofort_von_der_website(gast, welt):
    """Ende zu Ende: Austritt (Status + Flag) -> die Person ist weg (L3)."""
    anna = welt.get(Mitglied, "anna")
    anna.website_einwilligung = True
    _auswahl_anlegen(welt)
    assert len(_oeffentlich(gast).json()["message"]) == 1

    anna.status = "Ausgetreten"
    anna.ausgeschlossen = True
    welt.commit()
    assert _oeffentlich(gast).json()["message"] == [], (
        "ausgetretene Person erscheint weiter auf der Website"
    )


# ── MITTEL 2: Foto-Route ───────────────────────────────────────────────────


def _bild_setup(welt, tmp_path, monkeypatch, *, einwilligung=True,
                foto_zustimmung=True, auswahl=True):
    """Mitarbeiterbild im Test-Dateiordner + passende Einwilligung."""
    from diakronos_app.settings import settings

    ordner = tmp_path / "files"
    ordner.mkdir(exist_ok=True)
    monkeypatch.setattr(settings, "files_dir", str(ordner))
    # Kleinstes gueltiges PNG (1x1, grau) — die Route prueft den Inhalt.
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xa8\xa5\x01"
        b"\x00\x00\x04\xff\x01\x0c\x0c\x03\xe5\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    (ordner / "anna.png").write_bytes(png)

    anna = welt.get(Mitglied, "anna")
    anna.foto = "anna.png"
    anna.website_einwilligung = einwilligung
    anna.website_einwilligung_foto = foto_zustimmung
    if auswahl:
        welt.add(
            WebsiteAnsprechpartner(
                art="dienstbereich", funktion="musik", bezeichnung="",
                postfach=None, sortierung=1,
            )
        )
    welt.commit()
    return anna


def test_foto_route_ausgetretene_person_ist_404(gast, welt, tmp_path, monkeypatch):
    """DER Test der Karte: ausgetretene Person MIT Foto-Zustimmung -> 404."""
    anna = _bild_setup(welt, tmp_path, monkeypatch)
    kennung = _kennung("anna")
    assert gast.get(f"/website/bild/person/{kennung}").status_code == 200, (
        "Ausgangslage kaputt: Bild kommt nicht"
    )

    # Austritt wie in api/austritt.py: Status + Flag, Einwilligung bleibt.
    anna.status = "Ausgetreten"
    anna.ausgeschlossen = True
    welt.commit()
    antwort = gast.get(f"/website/bild/person/{kennung}")
    assert antwort.status_code == 404, "Bild einer ausgetretenen Person ausgeliefert"

    # Auch die reine Statusmarke (ohne Flag) genuegt.
    anna.ausgeschlossen = False
    anna.status = "Verstorben"
    welt.commit()
    assert gast.get(f"/website/bild/person/{kennung}").status_code == 404


def test_foto_route_nur_fuer_ausgewaehlte_ansprechpartner(gast, welt, tmp_path,
                                                          monkeypatch):
    """Einwilligung allein genuegt nicht: die Person muss ausgewaehlt sein."""
    anna = _bild_setup(welt, tmp_path, monkeypatch, auswahl=False)
    assert anna.website_einwilligung is True
    kennung = _kennung("anna")
    assert gast.get(f"/website/bild/person/{kennung}").status_code == 404, (
        "Mitgliederfoto ohne Verwaltungsauswahl abrufbar"
    )

    _auswahl_anlegen(welt)
    assert gast.get(f"/website/bild/person/{kennung}").status_code == 200


def test_foto_route_widerruf_und_entfernte_auswahl(gast, welt, tmp_path, monkeypatch):
    """Widerruf und Entfernen der Auswahl wirken sofort (kein Zwischenspeicher)."""
    anna = _bild_setup(welt, tmp_path, monkeypatch)
    kennung = _kennung("anna")
    assert gast.get(f"/website/bild/person/{kennung}").status_code == 200

    anna.website_einwilligung = False
    welt.commit()
    assert gast.get(f"/website/bild/person/{kennung}").status_code == 404, (
        "Namens-Widerruf wirkt nicht auf das Bild"
    )

    anna.website_einwilligung = True
    welt.commit()
    assert gast.get(f"/website/bild/person/{kennung}").status_code == 200

    welt.query(WebsiteAnsprechpartner).delete()
    welt.commit()
    assert gast.get(f"/website/bild/person/{kennung}").status_code == 404


def test_foto_route_prueft_nur_ausgewaehlte_personen(patched_db, monkeypatch):
    """Kein Vollscan je Anfrage: der Index enthaelt NUR die Ausgewaehlten."""
    from diakronos_app.website import oeffentlich_daten as daten

    sess = patched_db()
    # 50 Personen ohne Auswahl — sie duerfen den Index nicht fuellen.
    for i in range(50):
        _mitglied(
            sess, f"person{i}", vorname=f"Person{i}", nachname="Test",
            einwilligung=True, foto="bild.png",
        )
    _mitglied(sess, "anna", user=PERSON_MAIL, einwilligung=True, foto="anna.png")
    sess.add(Dienstbereich(name="musik", ministry="Musik", sortierung=1))
    sess.add(
        DienstbereichVerantwortlicher(
            name="dbv-1", parent="musik", parenttype="Dienstbereich",
            parentfield="verantwortliche", user=PERSON_MAIL, idx=1,
        )
    )
    sess.commit()
    assert daten.person_ist_oeffentlicher_ansprechpartner(sess, _kennung("anna")) is False
    assert daten.person_ist_oeffentlicher_ansprechpartner(sess, _kennung("person7")) is False

    _auswahl_anlegen(sess)
    index = daten._ansprechpartner_personen_index(sess)
    assert set(index) == {_kennung("anna")}, (
        f"Index enthaelt {len(index)} statt genau die ausgewaehlte Person"
    )
    assert daten.mitglied_zu_oeffentlicher_kennung(sess, _kennung("anna")) is not None
    assert daten.mitglied_zu_oeffentlicher_kennung(sess, _kennung("person7")) is None


def test_foto_route_unbekannte_kennung_ist_404(gast, welt, tmp_path, monkeypatch):
    _bild_setup(welt, tmp_path, monkeypatch)
    assert gast.get("/website/bild/person/" + "0" * 32).status_code == 404
    assert gast.get("/website/bild/person/anna").status_code == 404, (
        "die interne Personenkennung darf kein Bild oeffnen"
    )


# ── MITTEL 3: Audit je geaendertem Feld genau ein Eintrag ──────────────────


def test_audit_einwilligung_und_foto_im_selben_aufruf(als_benutzer, welt):
    """Beide Felder geaendert -> zwei Eintraege, je einer pro Feld."""
    client = als_benutzer(PERSON_MAIL)
    antwort = client.post(
        f"/api/method/{PFAD_EINW_SETZEN}",
        json={"einwilligung": True, "foto": True},
    )
    assert antwort.status_code == 200, antwort.text
    assert _audit(welt) == [("website", "erteilt"), ("website_foto", "erteilt")]


def test_audit_nur_foto_genau_ein_eintrag(als_benutzer, welt):
    """„nur foto“ -> genau EIN Eintrag (die alte elif-Kette schwieg hier)."""
    client = als_benutzer(PERSON_MAIL)
    assert client.post(
        f"/api/method/{PFAD_EINW_SETZEN}", json={"einwilligung": True}
    ).status_code == 200
    welt.query(DSGVOEinwilligung).delete()
    welt.commit()

    assert client.post(
        f"/api/method/{PFAD_EINW_SETZEN}", json={"foto": True}
    ).status_code == 200
    assert _audit(welt) == [("website_foto", "erteilt")]


def test_audit_alle_drei_felder_genau_drei_eintraege(als_benutzer, welt):
    """Kein Feld wird doppelt protokolliert (der alte Anzeigename-Block)."""
    client = als_benutzer(PERSON_MAIL)
    antwort = client.post(
        f"/api/method/{PFAD_EINW_SETZEN}",
        json={"einwilligung": True, "foto": True, "anzeigename": "Anna B."},
    )
    assert antwort.status_code == 200, antwort.text
    assert _audit(welt) == [
        ("website", "erteilt"),
        ("website_anzeigename", "gesetzt"),
        ("website_foto", "erteilt"),
    ]


def test_audit_widerruf_protokolliert_das_foto_mit(als_benutzer, welt):
    """Der Widerruf setzt die Foto-Zustimmung zurueck — das wird mitgeschrieben."""
    client = als_benutzer(PERSON_MAIL)
    assert client.post(
        f"/api/method/{PFAD_EINW_SETZEN}",
        json={"einwilligung": True, "foto": True},
    ).status_code == 200
    welt.query(DSGVOEinwilligung).delete()
    welt.commit()

    assert client.post(
        f"/api/method/{PFAD_EINW_SETZEN}", json={"einwilligung": False}
    ).status_code == 200
    assert _audit(welt) == [("website", "widerrufen"), ("website_foto", "widerrufen")]


def test_audit_ohne_aenderung_kein_eintrag(als_benutzer, welt):
    """Nichts angegeben -> 417 und kein Protokolleintrag (kein Rauschen)."""
    client = als_benutzer(PERSON_MAIL)
    antwort = client.post(f"/api/method/{PFAD_EINW_SETZEN}", json={})
    assert antwort.status_code == 417, antwort.text
    assert _audit(welt) == []


# ── NIEDRIG 4: PNG- und WebP-Metadaten ─────────────────────────────────────


def _png_chunk(typ: bytes, inhalt: bytes) -> bytes:
    import zlib

    return (
        len(inhalt).to_bytes(4, "big")
        + typ
        + inhalt
        + zlib.crc32(typ + inhalt).to_bytes(4, "big")
    )


def _png(metadaten: bool = True) -> bytes:
    """Kleinstes PNG (1x1) mit oder ohne Metadaten-Chunks."""
    import zlib

    ihdr = _png_chunk(
        b"IHDR", b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    )
    idat = _png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
    iend = _png_chunk(b"IEND", b"")
    if not metadaten:
        return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend
    return (
        b"\x89PNG\r\n\x1a\n"
        + ihdr
        + _png_chunk(b"tEXt", b"Author\x00Anna Beispiel")
        + _png_chunk(b"iTXt", b"XML:com.adobe.xmp\x00\x00\x00\x00\x00GPS 49.14")
        + idat
        + _png_chunk(b"eXIf", b"Exif\x00\x00GPSLatitude=49.14")
        + _png_chunk(b"zTXt", zlib.compress(b"Comment\x00\ndas hier"))
        + iend
    )


def _webp(metadaten: bool = True) -> bytes:
    """Kleinstes WebP-Gerüst: RIFF + VP8X + VP8 + (EXIF/XMP).

    Alle Chunk-Inhalte haben GERADE Länge (kein Füllbyte) — so bleibt die
    RIFF-Größe ein exakter Vergleich und ein Fehler in der Polsterung fällt
    im Metadaten-Test auf.
    """
    def chunk(typ: bytes, inhalt: bytes) -> bytes:
        assert len(inhalt) % 2 == 0, f"Testdatei: {typ!r} mit ungerader Länge"
        return typ + len(inhalt).to_bytes(4, "little") + inhalt

    teile = [chunk(b"VP8X", b"\x00" * 10), chunk(b"VP8 ", b"\x00" * 10)]
    if metadaten:
        teile.append(chunk(b"EXIF", b"GPSLatitude=49.14;GPSLongitude=9.21X"))
        teile.append(chunk(b"XMP ", b"<x:xmpmeta>Anna Beispiel</x:xmpmeta>\x00\x00"))
    rumpf = b"WEBP" + b"".join(teile)
    return b"RIFF" + (len(rumpf)).to_bytes(4, "little") + rumpf


def _webp_mit_polsterung() -> bytes:
    """WebP mit einem ungeraden Chunk: das Füllbyte MUSS erhalten bleiben."""
    rumpf = (
        b"WEBP"
        + b"VP8X" + (10).to_bytes(4, "little") + b"\x00" * 10
        + b"XMP " + (5).to_bytes(4, "little") + b"abcde" + b"\x00"
        + b"VP8 " + (4).to_bytes(4, "little") + b"\x01\x02\x03\x04"
    )
    return b"RIFF" + (len(rumpf)).to_bytes(4, "little") + rumpf


def test_webp_polsterbyte_bleibt():
    """Ein gerades/ungerades Chunk-Füllbyte darf die Struktur nicht kippen."""
    from diakronos_app.gemeinde_logo import ohne_metadaten

    vorher = _webp_mit_polsterung()
    nachher = ohne_metadaten(vorher, "image/webp")
    assert b"XMP " not in nachher
    assert b"VP8 " in nachher and b"VP8X" in nachher
    assert int.from_bytes(nachher[4:8], "little") + 8 == len(nachher)


def test_png_metadaten_entfernt():
    from diakronos_app.gemeinde_logo import ohne_metadaten

    vorher = _png()
    assert b"Author" in vorher, "tEXt fehlt in der Testdatei"
    assert b"GPSLatitude" in vorher, "eXIf fehlt in der Testdatei"
    assert b"XML:com.adobe.xmp" in vorher, "iTXt fehlt in der Testdatei"
    # zTXt ist komprimiert — der Klartext steht nicht in den Bytes, der CHUNK
    # aber schon (er wird als Ganzes entfernt).
    assert b"zTXt" in vorher

    nachher = ohne_metadaten(vorher, "image/png")
    assert nachher.startswith(b"\x89PNG\r\n\x1a\n")
    for marke in (b"Author", b"GPSLatitude", b"XML:com.adobe.xmp"):
        assert marke not in nachher, f"Metadaten {marke!r} im ausgelieferten PNG"
    for typ in (b"tEXt", b"iTXt", b"zTXt", b"eXIf"):
        assert typ not in nachher, typ
    # Bild und Struktur bleiben: IHDR, IDAT und IEND unverändert.
    for typ in (b"IHDR", b"IDAT", b"IEND"):
        assert typ in nachher, typ
    assert nachher.endswith(_png_chunk(b"IEND", b""))
    assert len(nachher) < len(vorher)


def test_png_ohne_metadaten_bleibt_unveraendert():
    from diakronos_app.gemeinde_logo import ohne_metadaten

    png = _png(metadaten=False)
    assert ohne_metadaten(png, "image/png") == png


def test_webp_metadaten_entfernt_und_groesse_angepasst():
    from diakronos_app.gemeinde_logo import ohne_metadaten

    vorher = _webp()
    assert b"GPSLatitude" in vorher and b"xmpmeta" in vorher

    nachher = ohne_metadaten(vorher, "image/webp")
    assert nachher[:4] == b"RIFF" and nachher[8:12] == b"WEBP"
    assert b"EXIF" not in nachher
    assert b"XMP " not in nachher
    assert b"GPSLatitude" not in nachher
    assert b"xmpmeta" not in nachher
    assert b"VP8 " in nachher, "Bilddaten verloren"
    # RIFF-Größe = Länge ab "WEBP": muss exakt zur neuen Datei passen, sonst
    # lehnt der Browser sie ab.
    riff_laenge = int.from_bytes(nachher[4:8], "little")
    assert riff_laenge + 8 == len(nachher), (
        f"RIFF-Groesse {riff_laenge + 8} passt nicht zur Datei ({len(nachher)})"
    )
    assert len(nachher) < len(vorher)


def test_webp_ohne_metadaten_bleibt_unveraendert():
    from diakronos_app.gemeinde_logo import ohne_metadaten

    webp = _webp(metadaten=False)
    assert ohne_metadaten(webp, "image/webp") == webp


def test_ohne_metadaten_wirft_nie(patched_db):
    """Kaputte Eingaben je Format: unverändert zurück, kein Fehler."""
    from diakronos_app.gemeinde_logo import ohne_metadaten

    for typ, roh in (
        ("image/png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 3),
        ("image/png", b"\x89PNG\r\n\x1a\n\xff\xff\xff\xff"),
        ("image/webp", b"RIFF\x00\x00\x00\x00WEBP"),
        ("image/webp", b"RIFF" + b"\xff" * 12 + b"WEBP" + b"\x00" * 4),
        ("image/jpeg", b"\xff\xd8"),
    ):
        assert ohne_metadaten(roh, typ) == roh, (typ, roh)


def test_bild_route_person_entfernt_auch_png_metadaten(gast, welt, tmp_path,
                                                       monkeypatch):
    """Ende zu Ende: das ausgelieferte PNG enthält kein tEXt/eXIf mehr."""
    from diakronos_app.settings import settings

    ordner = tmp_path / "files"
    ordner.mkdir()
    monkeypatch.setattr(settings, "files_dir", str(ordner))
    (ordner / "anna.png").write_bytes(_png())

    anna = welt.get(Mitglied, "anna")
    anna.foto = "anna.png"
    anna.website_einwilligung = True
    anna.website_einwilligung_foto = True
    welt.add(
        WebsiteAnsprechpartner(
            art="dienstbereich", funktion="musik", bezeichnung="",
            postfach=None, sortierung=1,
        )
    )
    welt.commit()

    antwort = gast.get(f"/website/bild/person/{_kennung('anna')}")
    assert antwort.status_code == 200, antwort.text
    assert antwort.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"Author" not in antwort.content
    assert b"GPSLatitude" not in antwort.content
