"""Portierung von `admin_hub.py` — Teilmenge fuer P2b + P4k.

Quelle (READ-ONLY): `referenz/diakronos-frappe/diakonos/diakonos/api/admin_hub.py`

Portiert (P2b): `get_statistik` (admin_hub.py:100-163).
Portiert (P4k, diese Karte): `get_dsgvo_uebersicht`, `get_anmeldungen_hub`,
`genehmige_anmeldung`, `lehne_anmeldung_ab`, `get_anmeldeformulare`,
`create_anmeldeformular`, `update_anmeldeformular_felder`.

Die SPA ruft die ORIGINAL-Pfade `diakronos.diakonos.api.admin_hub.<fn>` auf
(Aufrufliste des Frappe-Frontends); dafuer traegt dieses Modul `FRAPPE_MODULE`.

BESONDERHEIT `genehmige_anmeldung` — im Altcode liegt die Fachlogik NICHT im
Endpunkt, sondern im DocType-Controller-Hook `Anmeldung.on_update` →
`_create_mitglied_und_dsgvo()` (`doctype/anmeldung/anmeldung.py:15-70`).
Im Standalone-Backend gibt es keine DocType-Lifecycle-Hooks; die Portierung
bildet den Hook deshalb explizit in `_anmeldung_zu_mitglied()` ab (Mitglied +
DSGVO Einwilligung + Audit Log + Notification Log an Mitgliederadministratoren).
Das Verhalten ist 1:1: nur bei `status == "Bestätigt"` UND `verarbeitet == 0`.

PERMISSION — fail closed (siehe `frappe_compat/permissions.py`):
`_require_admin` prueft wie das Original `Mitgliederadministrator` bzw.
`System Manager`.
"""

from __future__ import annotations

# Original-Frappe-Modulpfad. Die SPA ruft ausschliesslich diese Form auf;
# die Registry registriert daraus `diakronos.diakonos.api.admin_hub.<funktion>`.
FRAPPE_MODULE = "diakronos.diakonos.api.admin_hub"

import json as _json
from datetime import date
from typing import Any

from diakronos_app.api.audit import log as _audit_log
from diakronos_app.anmeldung.registrierungslink import OFFENE_ANMELDESTATI
from diakronos_app.frappe_compat.api_helpers import (
    _child_delete,
    _child_replace,
    _child_rows,
    _create,
    _delete_doc,
    _now,
    _update_doc,
    log_error,
)
from diakronos_app.frappe_compat import db, get_all, whitelist
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    PermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.permissions import get_roles, is_guest, ist_user_zeile
from diakronos_app.frappe_compat.query import get_doc, get_value

#: Status -> Schluessel in der Statistik (admin_hub.py:113-118).
STATUS_KEY_MAP = {
    "Mitglied": "mitglied",
    "Gast": "gast",
    "Passives Mitglied": "passives_mitglied",
    "Passiver Gast": "passiver_gast",
}

#: Status, die als "offen" gelten (admin_hub.py:133).
OFFENE_ANMELDESTATI = ("Anmeldeanfrage", "Ausstehend")


def _require_admin() -> None:
    """Wortgleich zu admin_hub.py:5-10."""
    if is_guest():
        throw("Zugriff verweigert.", PermissionError)
    roles = get_roles()
    if "Mitgliederadministrator" not in roles and "System Manager" not in roles:
        throw("Nur für Mitgliederadministratoren.", PermissionError)


def _erster_des_monats() -> str:
    """`get_first_day(nowdate())` als ISO-String (YYYY-MM-01)."""
    heute = date.today()
    return heute.replace(day=1).isoformat()


@whitelist(allow_guest=False)
def get_statistik():
    """Kennzahlen fuer den Admin-Hub. Portiert aus admin_hub.py:100-163."""
    _require_admin()

    # ── Mitglieder ──────────────────────────────────────────────────────────
    alle_mitglieder = get_all(
        "Mitglied", fields=["name", "status", "datenschutz_einwilligung"]
    )
    m_stats = {
        "gesamt": len(alle_mitglieder),
        "mitglied": 0,
        "gast": 0,
        "passives_mitglied": 0,
        "passiver_gast": 0,
    }
    for m in alle_mitglieder:
        key = STATUS_KEY_MAP.get(m.get("status") or "")
        if key:
            m_stats[key] += 1

    # ── DSGVO ───────────────────────────────────────────────────────────────
    # Personen zählen, nicht Protokollzeilen (Befund UXD-R16): die Kachel
    # „Datenschutz“ muss die Zahl der Mitglieder mit/ohne Einwilligung zeigen.
    # `Mitglied.datenschutz_einwilligung` ist die maßgebliche Quelle; die
    # Zeilen in „DSGVO Einwilligung“ enthalten auch Foto/Werbe-Einträge und
    # damit mehr Zeilen als Personen.
    dsgvo_ok = sum(1 for m in alle_mitglieder if m.get("datenschutz_einwilligung"))
    dsgvo_fehlt = len(alle_mitglieder) - dsgvo_ok
    # Widerrufen zählt ebenfalls PERSONEN, nicht Widerrufszeilen (UXD-R16): je
    # Person zählt der jüngste `datenschutz`-Eintrag. Eine Person mit mehreren
    # Widerrufszeilen (z. B. erst widerrufen, dann erneut widerrufen) zählt so
    # nur einmal; Foto- und Werbe-Einträge bleiben außen vor.
    protokoll = get_all(
        "DSGVO Einwilligung",
        fields=["mitglied", "typ", "aktion", "zeitstempel"],
        order_by="zeitstempel asc",
    )
    letzter_datenschutz: dict[str, str] = {}
    for zeile in protokoll:
        if zeile.get("typ") == "datenschutz":
            letzter_datenschutz[zeile.get("mitglied")] = zeile.get("aktion") or ""
    dsgvo_wr = sum(
        1 for person in letzter_datenschutz
        if letzter_datenschutz[person] == "widerrufen"
    )

    # ── Anmeldungen ─────────────────────────────────────────────────────────
    alle_anm = get_all("Anmeldung", fields=["name", "status", "anmeldedatum"])
    monat_start = _erster_des_monats()
    diesen_monat = sum(
        1 for a in alle_anm
        if a.get("anmeldedatum") and str(a["anmeldedatum"]) >= monat_start
    )
    offen = sum(1 for a in alle_anm if a.get("status") in OFFENE_ANMELDESTATI)

    nach_status: dict = {}
    for a in alle_anm:
        status = a.get("status")
        nach_status[status] = nach_status.get(status, 0) + 1

    # ── Registrierungslinks ─────────────────────────────────────────────────
    alle_links = get_all(
        "Registrierungslink",
        fields=["name", "bezeichnung", "aktiv", "anmeldungen_count"],
        order_by="anmeldungen_count desc",
    )
    aktiv = sum(1 for link in alle_links if link.get("aktiv"))
    top_links = alle_links[:5]

    return {
        "mitglieder": m_stats,
        "dsgvo": {"ok": dsgvo_ok, "widerrufen": dsgvo_wr, "fehlt": dsgvo_fehlt},
        "anmeldungen": {
            "gesamt": len(alle_anm),
            "diesen_monat": diesen_monat,
            "offen": offen,
            "nach_status": nach_status,
        },
        "links": {
            "aktiv": aktiv,
            "inaktiv": len(alle_links) - aktiv,
            "gesamt_anmeldungen": sum(link.get("anmeldungen_count") or 0 for link in alle_links),
            "top": top_links,
        },
    }


# ── DSGVO-Uebersicht (admin_hub.py:14-56) ───────────────────────────────────


@whitelist(allow_guest=False)
def get_dsgvo_uebersicht():
    """DSGVO-Status je Mitglied. Portiert aus admin_hub.py:14-56."""
    _require_admin()

    mitglieder = get_all(
        "Mitglied",
        fields=[
            "name", "vorname", "nachname", "status", "email",
            "datenschutz_einwilligung", "datenschutz_datum",
        ],
        order_by="nachname asc",
    )

    letzter = {}
    for z in get_all("DSGVO Einwilligung", fields=["mitglied", "typ", "aktion", "zeitstempel"],
                     order_by="zeitstempel asc, name asc"):
        if z.get("typ") == "datenschutz":
            letzter[z.get("mitglied")] = z
    for m in mitglieder:
        z = letzter.get(m["name"], {})
        # Das Stammdatenflag ist maßgeblich. Foto-/Werbeprotokolle und das
        # historische widerrufen-Flag dürfen den Personenstand nicht verfälschen.
        m["dsgvo_status"] = (
            "ok" if m.get("datenschutz_einwilligung") else
            "widerrufen" if z.get("aktion") == "widerrufen" else "fehlt"
        )
        m["dsgvo_datum"] = (
            m.get("datenschutz_datum") if m["dsgvo_status"] == "ok"
            else str(z["zeitstempel"])[:10] if z.get("zeitstempel") else None
        )

    # DSGVO-2d: Eine gelöschte Person ist hier eine Zeile ohne Personendaten —
    # kein Name, keine Adresse, kein Profil-Link, kein „Anonymisieren“ (die
    # Löschung ist erledigt). `geloescht` sagt der Oberfläche, dass sie diese
    # Zeile nur noch anzeigend führen darf. Die Zeile bleibt in der Liste,
    # damit die Zählung unten zur Gemeindegröße passt.
    from diakronos_app.frappe_compat.personen_anzeige import (
        GELOESCHT_ANZEIGE, ist_geloescht,
    )

    for m in mitglieder:
        geloescht = ist_geloescht(m)
        m["geloescht"] = geloescht
        if geloescht:
            m.update(vorname=GELOESCHT_ANZEIGE, nachname="", email=None)

    ok = sum(1 for m in mitglieder if m["dsgvo_status"] == "ok")
    widerrufen = sum(1 for m in mitglieder if m["dsgvo_status"] == "widerrufen")
    fehlt = sum(1 for m in mitglieder if m["dsgvo_status"] == "fehlt")

    return {
        "mitglieder": mitglieder,
        "stats": {
            "gesamt": len(mitglieder),
            "ok": ok,
            "widerrufen": widerrufen,
            "fehlt": fehlt,
        },
    }


# ── Anmeldungen-Hub (admin_hub.py:59-97) ────────────────────────────────────


@whitelist(allow_guest=False)
def get_anmeldungen_hub():
    """Anmeldungen samt Antworten, Kindern und Links (admin_hub.py:59-97)."""
    _require_admin()

    anmeldungen = get_all(
        "Anmeldung",
        fields=[
            "name", "vorname", "nachname", "status", "anmeldungstyp",
            "anmeldedatum", "email",
            # OP-ADMIN-8: Telefon, Geburtstag und Kommentar fehlten im Dialog
            # ("Telefon: –" trotz DB-Wert).
            "telefon", "geburtstag", "kommentar",
            # N2: Zielfeld `gruppe` der Anmeldung, damit „Aufnehmen“ sie
            # vorbelegen kann (statt sie still im Hintergrund zuzuweisen).
            "gruppe",
        ],
        order_by="anmeldedatum desc",
        limit_page_length=500,
    )

    anmeldung_names = [a["name"] for a in anmeldungen]

    # Kinder nur laden, wenn es Eltern gibt: `["in", []]` wuerde in SQL zu
    # `IN ()` — deshalb der Guard (die Live-Abfrage des Originals laeuft
    # ebenfalls nur bei nicht-leerer Liste fachlich sinnvoll).
    antworten_map: dict = {}
    kinder_map: dict = {}
    if anmeldung_names:
        for a in get_all(
            "Anmeldung Antwort",
            filters={"parent": ["in", anmeldung_names]},
            fields=["parent", "feldlabel", "antwort"],
        ):
            antworten_map.setdefault(a["parent"], []).append(
                {"label": a["feldlabel"], "wert": a["antwort"]}
            )

        for k in get_all(
            "Anmeldung Kind",
            filters={"parent": ["in", anmeldung_names]},
            fields=["parent", "vorname", "nachname", "geburtstag"],
        ):
            kinder_map.setdefault(k["parent"], []).append(
                {
                    "vorname": k["vorname"],
                    "nachname": k["nachname"],
                    "geburtstag": str(k["geburtstag"] or ""),
                }
            )

    for a in anmeldungen:
        a["antworten"] = antworten_map.get(a["name"], [])
        a["kinder"] = kinder_map.get(a["name"], [])

    _markiere_anmeldungs_dubletten(anmeldungen)

    links = get_all(
        "Registrierungslink",
        fields=[
            "name", "bezeichnung", "typ", "aktiv", "slug",
            "gueltig_bis", "max_anmeldungen", "anmeldungen_count", "link_anzeige",
        ],
        order_by="creation desc",
    )
    # UXD-R3: Altdaten tragen in `link_anzeige` den relativen Frappe-Pfad
    # (`/registrierung?token=…`). Die Oberflaeche zeigt/kopiert genau diesen
    # Wert; er muss auf die Standalone-Adresse zeigen, sonst laeuft ein
    # kopierter Link in einen 404. Dieselbe Ableitung wie in create_link.
    links = [_normalisiere_link(l) for l in links]

    # N3: Je Link die Zahl der offenen Anfragen — EIN Aufruf ueber alle Links
    # (kein N+1). Gezaehlt wird ueber `registrierungslink`, damit auch Anfragen
    # ohne bekannten Linknamen nicht in fremde Karten rutschen.
    # Kein `limit_page_length=0`: der Wert heisst in dieser Compat-Schicht
    # „keine Zeilen“ (so auch in `test_p0_1_resource_rollenmatrix.py`
    # dokumentiert); eine weggelassene Grenze liefert alle Zeilen.
    offene_je_link: dict = {}
    for zeile in get_all(
        "Anmeldung",
        fields=["registrierungslink"],
        filters={"status": ["in", list(OFFENE_ANMELDESTATI)]},
    ):
        schluessel = zeile.get("registrierungslink") if isinstance(zeile, dict) else None
        if schluessel:
            offene_je_link[schluessel] = offene_je_link.get(schluessel, 0) + 1

    # N3: Die Antwort ist eine ZUSTANDSLISTE. Ein Serverfilter (`aktiv = 1`)
    # waere hier fachlich falsch: gerade abgelaufene, volle und ausgeschaltete
    # Links muss die Verwaltung sehen (Konzept Abschnitt 5: „Abgelaufen oder
    # voll: Karte grau mit Schild“). `wuerde_ausgeblendet` nennt der Server
    # trotzdem je Zeile, damit ein Restfilter sofort auffaellt.
    links = [
        _link_mit_zustand(l, offene_je_link.get(l.get("name"), 0)) for l in links
    ]

    return {"anmeldungen": anmeldungen, "links": links}


def _normalisiere_email(email) -> str:
    """E-Mail fuer den Dublettenvergleich normalisieren (Befund 6, P1-9b).

    Der Vergleich war vorher exakt: Bestandsdaten mit Grossbuchstaben
    (`Max@Beispiel.de`) entgingen der Pruefung.

    SEC-c: die Regel liegt EINMAL in `email_belegung.normalisiere` (NFKC, ohne
    jeden Unicode-Leerraum, klein) — dieselbe Funktion, mit der die
    Mitglied-Schreibschranke speichert. Ein eigenes `strip().lower()` hier
    haette Tab, NBSP und Vollbreite wieder durchgelassen.
    """
    from diakronos_app.email_belegung import normalisiere

    return normalisiere(email)


def _dubletten_treffer(email: str) -> list[str]:
    """Bestandsmitglieder mit derselben E-Mail (gross/klein-unabhaengig).

    Kein `limit_page_length` — die frueheren 5 Treffer reichten fuer die
    Meldung, aber die Pruefung selbst lief nie ueber alle Zeilen. Hier wird
    bewusst die ganze Tabelle durchsucht (das Anmeldungs-Hub ist eine
    Admin-Ansicht, der Aufruf laeuft nicht im Sekundentakt).
    """
    ziel = _normalisiere_email(email)
    if not ziel:
        return []
    treffer = []
    for m in get_all("Mitglied", fields=["name", "email"]) or []:
        if isinstance(m, dict):
            wenn = _normalisiere_email(m.get("email"))
            name = m.get("name")
        else:  # pluck-Fall: nur der Name
            wenn, name = _normalisiere_email(m), m
        if wenn == ziel and name:
            treffer.append(str(name))
    return treffer


def _markiere_anmeldungs_dubletten(anmeldungen: list) -> None:
    """Setzt `email_vorhanden` je offener Anmeldung (Befund 6, P1-9b).

    Vorher lud die Oberflaeche die ersten 200 Mitglieder und verglich im
    Browser: bei mehr Mitgliedern blieb die Dublette unentdeckt, der Server
    lehnte anschliessend ab — ohne dass die freigebende Person im Dialog
    einen Weg zum Bestaetigen hatte. Die Pruefung gehoert an den Ort der
    Wahrheit; die Oberflaeche zeigt sie nur noch an.
    """
    emails = {
        _normalisiere_email(a.get("email"))
        for a in anmeldungen
        if _normalisiere_email(a.get("email"))
    }
    if not emails:
        for a in anmeldungen:
            a["email_vorhanden"] = 0
        return

    vorhandene: set[str] = set()
    for m in get_all("Mitglied", fields=["email"]):
        e = _normalisiere_email(m.get("email") if isinstance(m, dict) else m)
        if e:
            vorhandene.add(e)

    for a in anmeldungen:
        a["email_vorhanden"] = (
            1 if _normalisiere_email(a.get("email")) in vorhandene else 0
        )


def _normalisiere_link(link: dict) -> dict:
    """`link_anzeige` auf die Standalone-Adresse bringen (sonst unveraendert).

    Befund 7 (P0-4b): dieselbe Ableitung wie im Anlegepfad, aus EINEM Modul
    (`anmeldung/registrierungslink.py`) — vorher gab es hier eine dritte Kopie.
    """
    from diakronos_app.anmeldung.registrierungslink import normalisiere_link

    return normalisiere_link(link)


def _link_mit_zustand(link: dict, offene_anfragen: int) -> dict:
    """Zeile eines Registrierungslink um die Anzeigewerte des Zustands (N3).

    Konzept Abschnitt 5 verlangt je Karte „gültig bis“ UND „x von y Plätzen“
    mit Balken sowie den Zustand „Abgelaufen“/„Voll“. Die Regel dafuer liegt in
    `anmeldung/registrierungslink.zustand` — dieselbe Quelle, die der
    oeffentliche Pruefpfad benutzt; vorher kannte die Verwaltungsliste sie
    nicht und zeigte fuer abgelaufene Links weiter „aktiv“.
    """
    from diakronos_app.anmeldung.registrierungslink import zustand

    link.update(zustand(link, offene_anfragen=offene_anfragen))
    return link


# ── Anmeldung genehmigen / ablehnen (admin_hub.py:165-194) ──────────────────


def _dsgvo_standardtext() -> str:
    """Wortgleich zu `_dsgvo_standardtext()` (anmeldung.py:73-78)."""
    return (
        "Ich willige ein, dass meine personenbezogenen Daten (Name, Kontaktdaten) "
        "zum Zweck der Mitgliederverwaltung gemäß Art. 6 Abs. 1 lit. a DSGVO "
        "gespeichert und verarbeitet werden. Die Einwilligung kann jederzeit "
        "widerrufen werden."
    )


def _als_wahr(wert) -> bool:
    """Toleranter Wahrheitstest fuer 0/1/'0'/'1'/True/False (Check-Felder)."""
    if isinstance(wert, bool):
        return wert
    if wert is None:
        return False
    return str(wert).strip().lower() in {"1", "true", "ja", "yes"}


def _anmeldung_zu_mitglied(
    doc, *, status: str | None = None, gruppe: str | None = None
) -> tuple[str, list[str]]:
    """Portierung von `Anmeldung.on_update` → `_create_mitglied_und_dsgvo()`.

    Quelle: `doctype/anmeldung/anmeldung.py:19-70`. Reihenfolge, Feldnamen und
    Seiteneffekte sind 1:1 uebernommen:

      1. Mitglied anlegen (Status je `anmeldungstyp`)
      2. DSGVO Einwilligung anlegen (`widerrufen=0`, Einwilligungstext-Snapshot)
      3. Mitglied.datenschutz_einwilligung/datenschutz_datum setzen
         (`update_modified=False` im Original)
      4. Audit-Log `Profiländerung`
      5. Anmeldung.mitglied/verarbeitet setzen (`update_modified=False`)
      6. Mitgliederadministratoren per Notification Log benachrichtigen

    B4 (P1-7b): Die Anmeldung traegt ein Zielfeld `gruppe`. Der Altcode (und
    die erste Portierung) hat es nie ausgewertet — das Mitglied blieb ohne
    Gruppe zurueck, ohne dass die freigebende Person es erfuhr. Die Zuweisung
    laeuft jetzt ueber `add_mitglied_to_gruppe` (dieselbe Rechte- und
    Existenzpruefung wie im Rest): schlaegt sie fehl, wird das Mitglied
    trotzdem angelegt und der Grund als Warnung zurueckgegeben, statt still zu
    verschwinden. Rueckgabe ist deshalb `(mitglied_name, warnungen)`.

    N2 (OP-ADMIN-7/8): Beim Aufnehmen waehlt die freigebende Person Status und
    Gruppe ausdruecklich. `status`/`gruppe` sind deshalb optionale Vorgaben;
    fehlen sie, gilt weiterhin die Ableitung aus `anmeldungstyp` bzw. das
    Zielfeld `gruppe` der Anmeldung (Altverhalten der Portierung).

    M1 (R-N2-code): „Keine Gruppe“ liess sich nicht durchsetzen — die
    Oberflaeche sendet dann `''`, und `gruppe or zielfeld` verwarf die leere
    Auswahl wieder. `'Keine Gruppe'` kommt aus dem Ergebnis von
    `aufnehmen` als leerer Text an.
    """
    anmeldung_name = doc.name
    mitglied_status = status or (
        "Mitglied" if doc.anmeldungstyp == "Mitglied-Registrierung" else "Gast"
    )
    warnungen: list[str] = []

    # OP-ADMIN-7: E-Mail kleinschreiben (Dubletten sonst unerkannt).
    # SEC-c: und zwar mit der EINEN Normalisierung (NFKC, ohne jeden
    # Leerraum) — die Gast-Eingabe aus der oeffentlichen Registrierung kam
    # vorher mit Vollbreite/Nullbreiten-Zeichen bis hierher durch und wurde
    # als zweite Person angelegt.
    from diakronos_app.email_belegung import normalisiere as _email_normal

    email = _email_normal(doc.email)

    # OP-ADMIN-7: Vor dem Anlegen auf dieselbe E-Mail pruefen. Sonst entstehen
    # zwei Mitglieder mit identischen Daten; danach verweigern
    # `permissions.py`/`profile.py` die Zuordnung dauerhaft ("Mehrdeutige
    # Mitglied-Zuordnung") und die Person ist nicht mehr loeschbar.
    #
    # Befund 6 (P1-9b): Der Vergleich war exakt — Bestandsdaten mit
    # Grossbuchstaben (`Max@Beispiel.de`) entgingen der Pruefung. Er laeuft
    # jetzt ueber alle Zeilen gross/klein-unabhaengig (dieselbe Normalisierung
    # wie `mitglieder.py` beim Schreiben).
    if not _als_wahr(getattr(doc, "dublette_bestaetigt", 0)):
        if email:
            treffer = _dubletten_treffer(email)
            if treffer:
                throw(
                    "Es gibt bereits ein Mitglied mit dieser E-Mail-Adresse "
                    f"({', '.join(treffer)}). Bitte pruefen: bestehendes Mitglied "
                    "bearbeiten oder die Anmeldung mit ausdruecklicher Bestaetigung "
                    "trotzdem annehmen.",
                    ValidationError,
                )

    mitglied_name = _create(
        "Mitglied",
        {
            "vorname": doc.vorname,
            "nachname": doc.nachname,
            "email": email,
            "telefonnummer": doc.telefon or "",
            "geburtstag": doc.geburtstag or None,
            "status": mitglied_status,
        },
    )

    dsgvo_zeitstempel = _now()
    _create(
        "DSGVO Einwilligung",
        {
            "mitglied": mitglied_name,
            "zeitstempel": dsgvo_zeitstempel,
            "einwilligungstext": doc.dsgvo_text_snapshot or _dsgvo_standardtext(),
            "ip_adresse": doc.ip_adresse or "",
            "widerrufen": 0,
        },
    )

    _update_doc(
        "Mitglied",
        mitglied_name,
        {
            "datenschutz_einwilligung": 1,
            "datenschutz_datum": str(dsgvo_zeitstempel)[:10],
        },
        skip_modified=True,  # Original: update_modified=False
    )

    _audit_log(
        action_typ="Profiländerung",
        target_doctype="Mitglied",
        target_name=mitglied_name,
        begruendung=(
            f"Mitglied aus Anmeldung {anmeldung_name} bestätigt "
            f"(Typ: {doc.anmeldungstyp})"
        ),
    )

    _update_doc(
        "Anmeldung",
        anmeldung_name,
        {"mitglied": mitglied_name, "verarbeitet": 1},
        skip_modified=True,  # Original: update_modified=False
    )

    _notify_mitgliederadmin(doc, mitglied_name)

    # B4: Zielfeld der Anmeldung auswerten. Fehler duerfen das bereits
    # angelegte Mitglied nicht verwerfen, aber auch nicht stumm bleiben.
    # N2: Hat die freigebende Person beim Aufnehmen eine Gruppe gewaehlt,
    # gilt diese vor dem Zielfeld der Anmeldung.
    #
    # M1 (R-N2-code): `gruppe is None` heisst „nicht gewaehlt“ -> Zielfeld der
    # Anmeldung (Altverhalten). Der leere Text `''` dagegen ist eine bewusste
    # Auswahl („Keine Gruppe“) und darf NICHT auf das Zielfeld zurueckfallen —
    # sonst laesst sich die Vorbelegung nicht wieder entfernen.
    ziel_gruppe = getattr(doc, "gruppe", None) if gruppe is None else gruppe
    if ziel_gruppe:
        try:
            from diakronos_app.api.gruppen import add_mitglied_to_gruppe

            add_mitglied_to_gruppe(
                gruppe_id=ziel_gruppe,
                mitglied_id=mitglied_name,
                rolle="Mitglied",
                is_untergruppe=False,
            )
        except Exception as e:  # noqa: BLE001
            log_error(
                f"Anmeldung {anmeldung_name}: Gruppe-Zuweisung fehlgeschlagen: {e}",
                "_anmeldung_zu_mitglied",
            )
            warnungen.append(
                f"Mitglied angelegt, aber Gruppe „{ziel_gruppe}“ konnte nicht "
                f"zugewiesen werden: {e}"
            )

    return mitglied_name, warnungen


def _notify_mitgliederadmin(doc, mitglied_name: str) -> None:
    """Portierung von `_notify_mitgliederadmin()` (anmeldung.py:55-70).

    Empfaenger: alle User mit Rolle `Mitgliederadministrator` — im Altcode
    ueber `frappe.get_all("Has Role", pluck="parent")`.
    """
    admins = get_all(
        "Has Role",
        filters={"role": "Mitgliederadministrator"},
        fields=["parent", "parenttype"],
    )
    for row in admins:
        # R-N10 Punkt 7: nur Benutzer-Kindzeilen; Altdaten ohne `parenttype`
        # (NULL/leer) zaehlen als `User` (`permissions.ist_user_zeile`).
        if not isinstance(row, dict) or not ist_user_zeile(row.get("parenttype")):
            continue
        user = row.get("parent")
        if not user:
            continue
        from diakronos_app.benachrichtigungen import schreibe_meldung

        schreibe_meldung(
            for_user=user, subject=f"Mitglied angelegt: {doc.vorname} {doc.nachname}",
            inhalt=(f"Anmeldung <b>{doc.name}</b> bestätigt.<br>"
                    f"Mitglied: <b>{mitglied_name}</b>"),
            document_type="Mitglied", document_name=mitglied_name,
        )


@whitelist(allow_guest=False)
def genehmige_anmeldung(anmeldung_id, dublette_bestaetigt=0, status=None, gruppe=None):
    """Setzt Anmeldung auf 'Bestätigt' → legt Mitglied + DSGVO an.

    Portierung von `admin_hub.py:165-174`. Der Altcode verlaesst sich auf den
    DocType-Hook `Anmeldung.on_update`; im Standalone uebernimmt
    `_anmeldung_zu_mitglied()` dessen Fachlogik (inkl. `verarbeitet`-Guard).

    `dublette_bestaetigt=1` (OP-ADMIN-7/OP-UI-13): Der Aufrufer hat die
    Warnung "E-Mail schon vergeben" gesehen und will die zweite Person
    trotzdem anlegen — ohne diese ausdrueckliche Bestaetigung verweigert
    `_anmeldung_zu_mitglied` die Dublette.

    N2 (OP-ADMIN-7/8): Beim Aufnehmen waehlt die freigebende Person optional
    den Mitglied-Status (`status`) und die Zielgruppe (`gruppe`). Fehlen sie,
    gilt wie bisher der aus `anmeldungstyp` abgeleitete Status bzw. das
    Zielfeld `gruppe` der Anmeldung.
    """
    _require_admin()

    # N2: Der Status kommt aus der Auswahl der Oberflaeche — der Server prueft
    # ihn trotzdem gegen die echten Status, statt einen beliebigen Wert
    # anzunehmen (Ausblenden im Menue ist nur Komfort).
    if status is not None:
        from diakronos_app.api.mitglieder import MITGLIED_STATUS

        status = (status or "").strip()
        if status not in MITGLIED_STATUS:
            throw(
                f"Unbekannter Status „{status}“. Zulässig: "
                + ", ".join(MITGLIED_STATUS),
                ValidationError,
            )

    doc = get_doc("Anmeldung", anmeldung_id)
    doc.status = "Bestätigt"
    # Bestaetigung nur durchreichen, wenn sie gesetzt wurde (sonst wuerde das
    # Attribut die Semantik des Hooks veraendern).
    if _als_wahr(dublette_bestaetigt):
        doc.dublette_bestaetigt = 1
    _update_doc("Anmeldung", anmeldung_id, {"status": "Bestätigt"})

    # B4: Warnungen aus der Mitgliedsanlage (z.B. nicht zuweisbare Gruppe)
    # werden durchgereicht, damit die freigebende Person sie sieht.
    warnungen: list[str] = []
    if not doc.verarbeitet:
        mitglied_name, warnungen = _anmeldung_zu_mitglied(
            doc, status=status, gruppe=gruppe
        )
        doc.mitglied = mitglied_name
        doc.verarbeitet = 1

    return {"success": True, "mitglied": doc.mitglied, "warnungen": warnungen}


@whitelist(allow_guest=False)
def lehne_anmeldung_ab(anmeldung_id, grund=""):
    """Setzt Anmeldung auf 'Abgelehnt' (admin_hub.py:177-189)."""
    _require_admin()

    doc = get_doc("Anmeldung", anmeldung_id)
    kommentar = doc.kommentar or ""
    if grund:
        kommentar = kommentar + f"\n[Abgelehnt: {grund}]"

    _update_doc(
        "Anmeldung",
        anmeldung_id,
        {"status": "Abgelehnt", "kommentar": kommentar},
    )

    return {"success": True}


# ── Anmeldeformulare (admin_hub.py:192-230) ─────────────────────────────────


@whitelist(allow_guest=False)
def get_anmeldeformulare():
    """Liste aller Anmeldeformulare fuer Dropdowns (admin_hub.py:192-201).

    N2/OP-ADMIN-19: Die Spalte „Felder“ zeigte immer „–“, weil die Anzahl nie
    mitkam. Sie wird hier je Formular mitgezaehlt (das ist die einzige Stelle,
    die die Liste fuer die Oberflaeche liefert).
    """
    _require_admin()

    formulare = get_all(
        "Anmeldeformular",
        fields=["name", "bezeichnung", "mit_gaesten", "mit_kinder"],
        order_by="bezeichnung asc",
    )

    namen = [f["name"] for f in formulare]
    feld_anzahl: dict[str, int] = {}
    if namen:
        for feld in get_all(
            "Anmeldeformular Feld",
            filters={"parent": ["in", namen]},
            fields=["parent"],
        ):
            eltern = feld["parent"]
            if eltern:
                feld_anzahl[eltern] = feld_anzahl.get(eltern, 0) + 1

    for f in formulare:
        f["felder_anzahl"] = feld_anzahl.get(f["name"], 0)

    return {"formulare": formulare}


@whitelist(allow_guest=False)
def get_anmeldeformular_felder(formular_id):
    """Die Felder eines Anmeldeformulars (OP-ADMIN-19).

    Das Formular liess sich in der Oberflaeche weder oeffnen noch aendern: die
    Felder waren nie abrufbar, `update_anmeldeformular_felder` hatte also
    keinen Weg, den Bestand zu laden. Diese Funktion liefert genau die Form,
    die der Schreib-Endpunkt erwartet — Auswahl, Zaehlen in der Liste und
    Bearbeiten sprechen damit dieselbe Sprache.
    """
    _require_admin()

    doc = get_doc("Anmeldeformular", str(formular_id or "").strip())
    if doc is None:
        raise ValidationError("Anmeldeformular nicht gefunden.")

    felder = [
        {
            "label": z.get("label") or "",
            "feldtyp": z.get("feldtyp") or "Text",
            "optionen": z.get("optionen") or "",
            "pflichtfeld": 1 if z.get("pflichtfeld") else 0,
            "fuer_gaeste": 1 if z.get("fuer_gaeste") else 0,
            "fuer_kinder": 1 if z.get("fuer_kinder") else 0,
        }
        for z in _child_rows("Anmeldeformular Feld", doc.name, "felder",
                             ["label", "feldtyp", "optionen", "pflichtfeld",
                              "fuer_gaeste", "fuer_kinder"])
    ]
    return {
        "success": True,
        "name": doc.name,
        "bezeichnung": doc.get("bezeichnung") or doc.name,
        "mit_gaesten": 1 if doc.get("mit_gaesten") else 0,
        "mit_kinder": 1 if doc.get("mit_kinder") else 0,
        "felder": felder,
    }


@whitelist(allow_guest=False)
def update_anmeldeformular(formular_id, bezeichnung=None, mit_gaesten=None,
                           mit_kinder=None, felder_json=None):
    """Anmeldeformular aendern: Bezeichnung, Schalter, Felder (OP-ADMIN-19).

    `felder_json` ersetzt die Feldliste vollstaendig (wie
    `update_anmeldeformular_felder`); `None` laesst sie unveraendert. Die drei
    uebrigen Felder sind der Kopf des Formulars.
    """
    _require_admin()

    doc = get_doc("Anmeldeformular", str(formular_id or "").strip())
    if doc is None:
        raise ValidationError("Anmeldeformular nicht gefunden.")

    werte: dict[str, Any] = {}
    if bezeichnung is not None:
        text = str(bezeichnung).strip()
        if not text:
            raise ValidationError("Bitte eine Bezeichnung angeben.")
        if len(text) > 140:
            raise ValidationError("Die Bezeichnung darf höchstens 140 Zeichen lang sein.")
        werte["bezeichnung"] = text
    if mit_gaesten is not None:
        werte["mit_gaesten"] = 1 if int(mit_gaesten or 0) else 0
    if mit_kinder is not None:
        werte["mit_kinder"] = 1 if int(mit_kinder or 0) else 0

    if werte:
        _update_doc("Anmeldeformular", doc.name, werte)

    if felder_json is not None:
        update_anmeldeformular_felder(doc.name, felder_json)

    return {"success": True, "id": doc.name}


@whitelist(allow_guest=False)
def delete_anmeldeformular(formular_id, bestaetigt=0):
    """Anmeldeformular loeschen — nur ohne zugeordnete Registrierungslinks.

    Ein Formular, auf das ein Registrierungslink zeigt, wird NICHT geloescht:
    die Anmeldeseite haette danach kein Formular mehr und wuerde eine leere
    Seite zeigen, ohne dass jemand sieht warum.
    """
    _require_admin()

    doc = get_doc("Anmeldeformular", str(formular_id or "").strip())
    if doc is None:
        raise ValidationError("Anmeldeformular nicht gefunden.")

    links = get_all(
        "Registrierungslink",
        filters={"anmeldeformular": doc.name},
        fields=["name"],
    ) or []
    if links:
        raise ValidationError(
            f"Dieses Formular wird noch von {len(links)} Registrierungslinks verwendet. "
            "Bitte zuerst dort ein anderes Formular wählen."
        )
    if not int(bestaetigt or 0):
        raise ValidationError("Zum Löschen bitte bestätigen.")

    _child_delete("Anmeldeformular Feld", doc.name, "felder")
    _child_delete("Anmeldeformular Dokument", doc.name, "dokumente")
    _delete_doc("Anmeldeformular", doc.name)
    return {"success": True, "id": doc.name}


@whitelist(allow_guest=False)
def create_anmeldeformular(bezeichnung, mit_gaesten=0, mit_kinder=0):
    """Schnellanlage eines Anmeldeformulars aus dem Hub (admin_hub.py:204-218)."""
    _require_admin()

    doc_name = _create(
        "Anmeldeformular",
        {
            "bezeichnung": bezeichnung,
            "mit_gaesten": int(mit_gaesten or 0),
            "mit_kinder": int(mit_kinder or 0),
        },
    )

    return {"success": True, "id": doc_name}


@whitelist(allow_guest=False)
def update_anmeldeformular_felder(formular_id, felder_json):
    """Ersetzt alle Felder eines Anmeldeformulars (admin_hub.py:221-241).

    Der Altcode setzt `form.felder = []` und appends neu; die Portierung
    ersetzt die Kind-Tabelle `Anmeldeformular Feld` ueber `_child_replace`
    (siehe `frappe_compat/api_helpers.py`).
    """
    _require_admin()

    form = get_doc("Anmeldeformular", formular_id)
    felder = _json.loads(felder_json) if isinstance(felder_json, str) else felder_json

    rows = [
        {
            "label": f.get("label", ""),
            "feldtyp": f.get("feldtyp", "Text"),
            "optionen": f.get("optionen", ""),
            "pflichtfeld": int(f.get("pflichtfeld", 0)),
            "fuer_gaeste": int(f.get("fuer_gaeste", 0)),
            "fuer_kinder": int(f.get("fuer_kinder", 0)),
        }
        for f in (felder or [])
    ]
    _child_replace("Anmeldeformular Feld", form.name, "felder", rows)
    _update_doc("Anmeldeformular", form.name, {})

    return {"success": True}


__all__ = [
    "FRAPPE_MODULE",
    "STATUS_KEY_MAP",
    "OFFENE_ANMELDESTATI",
    "create_anmeldeformular",
    "delete_anmeldeformular",
    "genehmige_anmeldung",
    "get_anmeldungen_hub",
    "get_anmeldeformular_felder",
    "get_anmeldeformulare",
    "get_dsgvo_uebersicht",
    "get_statistik",
    "lehne_anmeldung_ab",
    "update_anmeldeformular",
    "update_anmeldeformular_felder",
]
