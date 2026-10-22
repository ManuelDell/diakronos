"""ID-1: der Leak-Test — nach dem Umschlüsseln steht der Klarname nirgends mehr.

WARUM HIER UND NICHT ALS SQL
----------------------------
Die Karte verlangt den Nachweis ÜBER DIE API: ein Nicht-Administrator darf für
eine AUSGETRETENE Person in KEINER Antwort den Klarnamen sehen — auch nicht
als Kennung. Ein SQL-Vergleich („kein `name` enthält ein Leerzeichen“) beweist
das nicht: die Anzeige-Regeln aus AUSTRITT-b/d kürzen zusätzlich, und ob die
Kennung durch einen Endpunkt sickert, zeigt nur die Antwort selbst.

GEGEN WAS
---------
Gegen die UMGESCHLÜSSELTE Kopie (Wegwerf-PostgreSQL, nach `alembic upgrade
head`), über `ID1_POSTGRES_URL`. Ohne die Variable wird übersprungen — wie
`test_dsgvo1_postgres.py`, inklusive derselben Sicherung gegen die falsche
Datenbank (`*_test`). Der Test SCHREIBT nur in dieser Wegwerf-DB (Anmeldung
des Lesers, Austritt der Zielperson) und räumt nichts weg: sie wird als Ganzes
verworfen.

WAS ALS „KLARNAME“ GILT
-----------------------
Vor- und Nachname der Person, wie sie VOR dem Umschlüsseln in `mitglied.name`
standen. Die Testperson wird dafür eigens angelegt — namentlich eine, deren
Kennung im Betrieb der Klarname WAR („Max Muster“), denn genau dieser Fall ist
der Anlass der Karte.
"""
from __future__ import annotations

import json
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("ID1_POSTGRES_URL"),
    reason="nur mit ID1_POSTGRES_URL (umgeschlüsselte Wegwerf-Kopie)",
)

MA = "Mitgliederadministrator"
ADMIN = "id1-admin@x.org"
LESER = "id1-leser@x.org"
#: Die Zielperson ist eine UMGESCHLÜSSELTE Person aus dem Altbestand (also
#: erfunden — der Export ist öffentlich) — nicht eine im Test angelegte. Nur so
#: prüft der Test den Zustand nach der Migration (eine im Test angelegte
#: Kennung steht nicht in der Abbildung).
#: Die Person hat ein Konto OHNE Verwaltungsrolle: die Rechteregel aus
#: P1-8 („Mitglied mit Verwaltungskonto nur durch System Manager“) greift
#: damit nicht, und der Austritt ist über `mitglied_austritt` möglich.
ZIEL_ALT = "Mira Blank"
ZIEL_VORNAME = "Mira"
ZIEL_NACHNAME = "Blank"
ZIEL_KONTO = "blank@example.org"


def _url() -> str:
    url = str(os.environ["ID1_POSTGRES_URL"])
    # Sicherung gegen die falsche Datenbank: der Test SCHREIBT (Konten,
    # Austritt). Er darf nur eine ausdrückliche Wegwerf-DB treffen — dieselbe
    # Regel wie in `test_dsgvo1_postgres.py`.
    assert "_test" in url, "ID1_POSTGRES_URL muss eine Wegwerf-Datenbank sein (*_test)"
    return url


@pytest.fixture()
def welt(monkeypatch):
    """Datenbank der Kopie, ohne Testnaht-Umweg: echte Identität je Aufruf."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import diakronos_app.db as dbmod
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Mitglied

    eng = create_engine(_url(), future=True)
    factory = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)
    monkeypatch.setattr(dbmod, "engine", eng)
    monkeypatch.setattr(dbmod, "SessionLocal", factory)

    s = factory()
    # Alle Testkonten in DERSELBEN Gruppe (`/gemeinde/|`): sonst sieht der
    # Leser die Zielperson gar nicht (`ancestor_path`-Überlappung) und der
    # Leak-Test wäre leer statt grün.
    for konto, rolle, vor, nach in (
        (ADMIN, MA, "Anna", "Admin"),
        (LESER, None, "Lena", "Leser"),
    ):
        if s.get(User, konto) is None:
            s.add(User(name=konto, email=konto, full_name=f"{vor} {nach}", enabled=True))
        # idempotent: die Wegwerf-Kopie bleibt zwischen den Tests stehen.
        if rolle and s.get(HasRole, f"HR-{konto}") is None:
            s.add(HasRole(name=f"HR-{konto}", parent=konto, parenttype="User",
                          parentfield="roles", role=rolle, docstatus=0, idx=1))
        if s.get(Mitglied, konto) is None:
            s.add(Mitglied(name=konto, vorname=vor, nachname=nach, email=konto,
                           status="Mitglied", user=konto, ausgeschlossen=0,
                           docstatus=0, idx=0, ancestor_path="/gemeinde/|"))
        else:
            s.get(Mitglied, konto).ancestor_path = "/gemeinde/|"
    # Die Zielperson steht bereits in der Kopie (umgeschlüsselt, s. o.) —
    # nur ihr Konto muss für die Kürzung ansprechbar sein.
    if s.get(User, ZIEL_KONTO) is None:
        s.add(User(name=ZIEL_KONTO, email=ZIEL_KONTO,
                   full_name=f"{ZIEL_VORNAME} {ZIEL_NACHNAME}", enabled=True))
    from sqlalchemy import text as _text

    neu = s.execute(_text("SELECT neu FROM id1_mitglied_kennung WHERE alt = :a"),
                    {"a": ZIEL_ALT}).scalar()
    ziel = s.get(Mitglied, neu) if neu else None
    if ziel is not None:
        # Dieselbe Gruppe wie Admin und Leser — so SIEHT der Leser die Person
        # (sonst prüft der Leak-Test nur, dass er sie nicht sieht).
        ziel.ancestor_path = "/gemeinde/|"
    s.commit()
    s.close()
    set_user(ADMIN)
    yield factory
    set_user("Administrator")


@pytest.fixture()
def umgeschluesselt(welt):
    """Kennung der Zielperson NACH dem Umschlüsseln (aus der Abbildung)."""
    from sqlalchemy import text

    from diakronos_app.db import SessionLocal

    s = SessionLocal()
    try:
        neu = s.execute(
            text("SELECT neu FROM id1_mitglied_kennung WHERE alt = :a"),
            {"a": ZIEL_ALT},
        ).scalar()
    finally:
        s.close()
    assert neu is not None, "die Zielperson wurde nicht umgeschlüsselt"
    return neu


def _austreten() -> None:
    """Zielperson austreten lassen — wiederholbar (die Kopie bleibt stehen)."""
    from sqlalchemy import text

    from diakronos_app.api.austritt import mitglied_austritt, mitglied_reaktivieren
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.session import set_user

    s = SessionLocal()
    try:
        neu = s.execute(text("SELECT neu FROM id1_mitglied_kennung WHERE alt = :a"),
                        {"a": ZIEL_ALT}).scalar()
    finally:
        s.close()
    set_user(ADMIN)
    try:
        mitglied_austritt(neu, "", "2026-10-01")
    except Exception:  # noqa: BLE001 — „bereits ausgetreten“ aus einem Vorlauf
        mitglied_reaktivieren(neu)
        mitglied_austritt(neu, "", "2026-10-01")


def _antworten(wer: str, kennung: str) -> dict[str, str]:
    """Alle API-Antworten, die für den Aufrufer die Person zeigen können."""
    from diakronos_app.api import dienstplan, gruppen, mitglieder, zugang
    from diakronos_app.frappe_compat.session import set_user

    set_user(wer)
    antworten: dict[str, str] = {}

    def merke(name: str, aufruf) -> None:
        try:
            antworten[name] = json.dumps(aufruf(), default=str, ensure_ascii=False)
        except Exception as fehler:  # noqa: BLE001 — „kein Zugriff“ ist eine Antwort
            antworten[name] = f"FEHLER {type(fehler).__name__}: {fehler}"

    merke("mitglieder_liste", lambda: mitglieder.get_mitglieder_liste(0, 100))
    merke("mitglieder_liste_suche", lambda: mitglieder.get_mitglieder_liste(0, 100, "Max"))
    merke("mitglied_detail", lambda: mitglieder.get_mitglied_detail(kennung))
    merke("adressbuch", lambda: mitglieder.get_adressbuch(""))
    merke("kontenliste", lambda: zugang.get_konten_liste())
    merke("moderator_auswahl", lambda: zugang.get_moderator_auswahl())
    merke("gruppen", lambda: gruppen.get_gruppen())
    merke("dienstplan", lambda: dienstplan.get_dienstplan())
    merke("meine_dienste", lambda: dienstplan.get_meine_dienste())
    return antworten


def test_leak_nicht_admin_sieht_klarnamen_nirgends(welt, umgeschluesselt):
    """Der Kern der Zusage: Klarname weder als Anzeige noch als Kennung."""
    from diakronos_app.frappe_compat.session import set_user

    _austreten()
    set_user(LESER)
    antworten = _antworten(LESER, umgeschluesselt)

    treffer = {name: antwort for name, antwort in antworten.items()
               if ZIEL_ALT in antwort}
    assert not treffer, f"Klarname in der Antwort: {sorted(treffer)}"


def test_leak_nicht_admin_sieht_die_alte_kennung_nicht(welt, umgeschluesselt):
    """Auch die alte KENNUNG (= der Klarname) darf in keiner Antwort stehen."""
    _austreten()
    antworten = _antworten(LESER, umgeschluesselt)
    # `mitglied_detail` mit der ALTEN Kennung: der Datensatz existiert nicht
    # mehr — geprüft wird, dass die Antwort ihn nicht nachliefert.
    assert ZIEL_ALT not in antworten["mitglied_detail"] or \
        antworten["mitglied_detail"].startswith("FEHLER")


def test_leak_gegenprobe_klarname_ist_ueberhaupt_auffindbar(welt, umgeschluesselt):
    """Gegenprobe: dieselben Antworten zeigen die Person — nur gekürzt.

    Ohne diese Probe wäre „kein Treffer“ auch bei kaputtem Aufbau grün (etwa
    wenn der Leser die Person gar nicht sieht): der Test soll den LEERLAUF
    ausschließen, nicht nur den Treffer.
    """
    from sqlalchemy import text

    from diakronos_app.db import SessionLocal

    s = SessionLocal()
    try:
        vorname = s.execute(text("SELECT vorname FROM mitglied WHERE name = :n"),
                            {"n": umgeschluesselt}).scalar()
    finally:
        s.close()
    assert vorname == ZIEL_VORNAME, "Testaufbau: die Person fehlt oder ist falsch benannt"

    _austreten()
    antworten = _antworten(LESER, umgeschluesselt)
    # Die KURZFORM darf erscheinen (AUSTRITT-b: ausgetretene Person gekürzt),
    # der volle Name nicht.
    assert any(ZIEL_VORNAME in antwort for antwort in antworten.values()), \
        "Testaufbau: der Leser sieht die Person gar nicht — Probe wäre leer"
    assert not any(ZIEL_ALT in antwort for antwort in antworten.values())


def test_leak_adressbuch_kuerzt_ausgetretene(welt, umgeschluesselt):
    """Das Adressbuch liefert den Klarnamen einer Ausgetretenen NICHT.

    Gefunden beim Leak-Test von ID-1: `get_adressbuch` gab `vorname`/`nachname`
    wörtlich aus — `maskiere_datensatz` regelt nur die Freigabe-Felder, nicht
    den Namen. Die anderen Listenwege kürzten längst (`personen_anzeige`).
    """
    from diakronos_app.api import mitglieder

    _austreten()
    antworten = _antworten(LESER, umgeschluesselt)
    adressbuch = json.loads(antworten["adressbuch"])
    zeile = [z for z in adressbuch["data"] if z.get("name") == umgeschluesselt]
    assert zeile, "Testaufbau: die Person fehlt im Adressbuch des Lesers"
    # Kurzform „Vorname N.“ im Feld `vorname`, der Nachname ist geleert.
    assert zeile[0]["vorname"] == f"{ZIEL_VORNAME} {ZIEL_NACHNAME[0]}.", zeile[0]
    assert not zeile[0]["nachname"], zeile[0]
    assert ZIEL_ALT not in antworten["adressbuch"]


def test_leak_kennung_selbst_traegt_keinen_namen(welt, umgeschluesselt):
    """Die Kennung nach dem Umschlüsseln ist zufällig, nicht der Klarname."""
    import re

    assert umgeschluesselt != ZIEL_ALT
    assert " " not in umgeschluesselt and "@" not in umgeschluesselt
    assert re.match(r"^[0-9a-f]{8}-[0-9a-f]$", umgeschluesselt), umgeschluesselt
