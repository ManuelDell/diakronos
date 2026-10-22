"""Austritt / Deaktivieren und Reaktivieren (Karte AUSTRITT, A1-A4).

FACHENTSCHEIDUNG (Manuel, 2026-10-20)
------------------------------------
* „Austritt / Deaktivieren“ macht ein ADMINISTRATOR. Es ist UMKERHBAR
  (Reaktivieren). Die Person bleibt in alten Plaenen sichtbar, aber gekuerzt
  (``frappe_compat/personen_anzeige.py``).
* Der Austritt setzt die vorhandene Marke ``Mitglied.ausgeschlossen`` mit
  Status „Ausgetreten“ — bewusst keine zweite Marke neben dem Ausschluss.

WARUM KEIN ZWEITES FELD („Austritt neben Ausschluss“)
----------------------------------------------------
Ein zweites Feld waere ein zweiter Weg mit halb gleicher Wirkung: Sitzungen,
Login, CalDAV, Rollen, Personenkandidaten und der Plan-Rahmen fragen heute
alle ``ausgeschlossen`` (``benutzer_status``, ``permissions.get_roles``,
``planrahmen/rechte.py``, ``gruppen_auswahl``). Ein neues Feld muesste an
JEDER dieser Stellen mitgeprueft werden — eine vergessene Stelle ist eine
ausgetretene Person mit Zugang. Deshalb: eine Marke, zwei Tatbestaende.

Was den Austritt vom Ausschluss unterscheidet, ist die ABSICHT und was daraus
folgt:

  * Status „Ausgetreten“ statt „Passiver Gast“ — und der vorherige Status
    wird gespeichert (``vor_austritt_status``), damit „Reaktivieren“ ihn
    zurueckgibt (A4: „vorheriger Status (gespeichert) bzw. Mitglied“).
  * Datum ist Pflicht, die Begruendung ist FREIWILLIG (A1: „optionale
    Begruendung“) — sie kann eine Krankheit nennen und ist damit ein
    Datum, das niemandem ausser der Person und den Administratoren gehoert.
  * „Ausschliessen“ bleibt fuer den harten Fall (Fehlverhalten): es setzt
    weiterhin „Passiver Gast“, zeigt in der Oberflaeche „Ausgeschlossen“
    und bietet KEIN „Reaktivieren“ an — die Aufhebung laeuft dort ueber den
    Status (``set_mitglied_status``), wie bisher.

DIE SCHRANKE
------------
Dieselbe wie bei Ausschluss und Kontosperre (P1-8*/SEC-*):
``_verweigere_fremdes_admin_konto`` (ein Mitgliederadministrator fasst kein
Verwaltungskonto an) und ``_verweigere_letzten_admin_verlust*`` (der letzte
Administrator darf nicht verschwinden). Geprueft wird VOR dem Schreiben; das
Schreiben selbst laeuft ueber den zentralen Weg ``_update_doc``, der den
NACHHER-Zustand gegenprueft (``_pruefe_mitglied_schreibzugriff``). Ein zweiter
Riegel ist nicht noetig — und es gibt keinen.

WAS „REAKTIVIEREN“ NICHT ZURUECKBRINGT
--------------------------------------
Der Kontozustand wird je Konto wiederhergestellt (AUSTRITT-c, M1): beim
Austritt merkt ``vor_austritt_konto_aktiv``, ob ein Konto aktiv oder gesperrt
war, und „Reaktivieren“ setzt genau diesen Wert zurueck. Eine VOR dem Austritt
gesetzte Kontosperre bleibt damit bestehen — der Austritt ist kein Weg, sie
aufzuheben (dafuer gibt es ``api/zugang.konto_sperren`` mit seinen Schranken
und seinem Protokoll). Die Oberflaeche sagt das dem Administrator. Ein Status
„geloescht“ (DSGVO-Anonymisierung) laesst sich gar nicht zuruecknehmen.
"""
from __future__ import annotations

FRAPPE_MODULE = "diakronos.diakonos.api.austritt"

from datetime import datetime
from typing import Any

from diakronos_app.frappe_compat.api_helpers import _today, _update_doc, log_error
from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.query import get_value
from diakronos_app.frappe_compat import permissions, session, whitelist
from diakronos_app.models.diakonos import Mitglied
from diakronos_app.api.gruppen_auswahl import AUSGESCHIEDEN

#: Status einer ausgetretenen Person. Steht in ``AUSGESCHIEDEN``
#: (``api/gruppen_auswahl.py``) und ist damit aus jeder Auswahlliste raus.
STATUS_AUSGETRETEN = "Ausgetreten"

#: So lange darf eine Begruendung hoechstens sein (Spalte ist Text, aber eine
#: unbegrenzte Eingabe in ein Protokollfeld ist eine Einladung).
BEGRUENDUNG_MAX = 500

#: So lange darf eine gespeicherte Statusmarke sein (``mitglied.status``).
_STATUS_MAX = 140

#: Endzustaende aus ``api/gruppen_auswahl.AUSGESCHIEDEN`` OHNE „ausgetreten“:
#: aus diesen kommt niemand zurueck (Anonymisierung ist endgueltig).
_ENDSTATUS = frozenset(AUSGESCHIEDEN - {STATUS_AUSGETRETEN.lower()})


def _ist_admin() -> bool:
    """Dieselbe Rollenliste wie in ``api/mitglieder.py`` (eine Wahrheit)."""
    from diakronos_app.api.mitglieder import ADMIN_ROLES

    return any(permissions.has_role(r) for r in ADMIN_ROLES)


def _kein_admin_melden(was: str) -> None:
    throw(f"Nur Administratoren dürfen {was}.", FrappePermissionError)


def _konto_pruefen(mitglied_id: str, grund: str) -> str:
    """Konto-Schranken (Verwaltungskonto, letzter Administrator).

    Rueckgabe: der verknuepfte Benutzername (leer, wenn es kein Konto gibt).
    """
    from diakronos_app.api.zugang import (
        _verweigere_fremdes_admin_konto,
        _verweigere_letzten_admin_verlust,
        _verweigere_letzten_admin_verlust_alle,
    )

    ziel_user = str(get_value("Mitglied", mitglied_id, "user") or "")
    if not ziel_user:
        return ""
    # Ein Mitglied mit Verwaltungskonto darf nur ein System Manager anfassen.
    _verweigere_fremdes_admin_konto(ziel_user)
    # Und das letzte Netz darf nicht reissen — auch nicht durch sich selbst.
    _verweigere_letzten_admin_verlust(ziel_user, grund)
    _verweigere_letzten_admin_verlust_alle(ziel_user, grund)
    return ziel_user


def _begruendung(begruendung: Any) -> str:
    text = str(begruendung or "").strip()
    if len(text) > BEGRUENDUNG_MAX:
        throw(
            f"Die Begründung darf höchstens {BEGRUENDUNG_MAX} Zeichen lang sein.",
            ValidationError,
        )
    return text


def _datum(datum: Any) -> str:
    """ISO-Datum des Austritts (Vorgabe: heute)."""
    text = str(datum or "").strip()
    if not text:
        return str(_today())
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        throw("Das Austrittsdatum bitte als JJJJ-MM-TT angeben.", ValidationError)
    return ""  # unerreichbar: `throw` wirft immer


def _protokoll(mitglied_id: str, eintrag: dict[str, Any]) -> None:
    """Audit wie bei jedem anderen Statuswechsel — nie den Vorgang verlieren."""
    from diakronos_app.api.mitglieder import _log_profil_aenderung

    try:
        _log_profil_aenderung(mitglied_id, eintrag)
    except Exception as e:  # noqa: BLE001 — Protokoll ist Beiwerk, der Austritt gilt
        log_error(f"Austritts-Protokoll fehlgeschlagen: {e}", "mitglied_austritt")


def _marke_setzen(mitglied_id: str, an: bool, *, status: str, seit: str | None,
                  grund: str = "") -> None:
    """Die Marke schreiben (Austritt und Reaktivieren benutzen nur diesen Weg)."""
    werte: dict[str, Any] = {
        "ausgeschlossen": 1 if an else 0,
        "ausgeschlossen_seit": seit,
        "status": status,
    }
    if an:
        werte["austritt_grund"] = grund or None
        werte["austritt_datum"] = seit
    else:
        werte["austritt_grund"] = None
        werte["austritt_datum"] = None
    _update_doc(
        "Mitglied",
        mitglied_id,
        werte,
        # Ein leerer Wert muss auch als NULL ankommen — sonst bliebe der alte
        # Begruendungstext an der Zeile stehen.
        explizite_null={"ausgeschlossen_seit", "austritt_grund", "austritt_datum"},
    )


def _konten_schalten(mitglied_id: str, aus: bool) -> list[str]:
    """Konto deaktivieren/aktivieren und Sitzungen sofort widerrufen.

    Benutzt die vorhandenen Bausteine: ``benutzer_status.wirksame_konten``
    (user-Link UND eindeutige E-Mail), ``widerrufe_sitzungen`` (aktiver
    Widerruf, Cache + Sitzungen) und ``vergiss`` beim Reaktivieren. Zusaetzlich
    wird ``User.enabled`` geschaltet — das ist der Riegel fuer Login, CalDAV
    und OIDC (alle drei pruefen ``enabled``); die Ausschluss-Marke allein
    liesse die Anmeldung zu und wiese erst die Sitzung ab.

    AUSTRITT-c (M1): Beim Austritt wird der Zustand JEDES wirksamen Kontos
    gemerkt (``vor_austritt_konto_aktiv``, „Kontoname -> true/false“), beim
    Reaktivieren genau darauf zurueckgesetzt. Vorher schaltete „Reaktivieren“
    jedes Konto ein — „Austritt + Reaktivieren“ war damit ein Seiteneingang an
    ``konto_sperren`` vorbei (samt dessen Schranken und Protokoll).
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat import benutzer_status
    from diakronos_app.models.core import User

    daten = get_value("Mitglied", mitglied_id, ["user", "email"], as_dict=True)
    konten = sorted(benutzer_status.wirksame_konten(dict(daten) if daten else None))
    if not konten:
        return []

    gemerkt: dict[str, bool] | None = None
    if not aus:
        # Nur beim Reaktivieren gelesen: der Austritt ueberschreibt den Wert
        # gleich mit dem tatsaechlichen Zustand von jetzt.
        roh = get_value("Mitglied", mitglied_id, "vor_austritt_konto_aktiv")
        gemerkt = dict(roh) if isinstance(roh, dict) else None

    sess = SessionLocal()
    try:
        zustand: dict[str, bool] = {}
        for name in konten:
            konto = sess.get(User, name)
            if konto is None:
                continue
            if aus:
                zustand[name] = bool(konto.enabled)
                konto.enabled = False
            else:
                # Altdaten (Austritt vor dieser Karte) tragen keinen Wert: ihr
                # Konto wurde nach der alten Regel ausgeschaltet, mehr sagen
                # die Daten nicht her. Dann gilt „wieder aktiv“.
                #
                # AUSTRITT-d (NN2, Operator-Entscheidung „so lassen“): Ein
                # EINZELNES Konto ohne gemerkten Wert wird ebenfalls aktiv
                # gestellt (`gemerkt.get(name, True)`). Die Begruendung: Ein
                # solches Konto kann nur aus einem Austritt stammen, der VOR der
                # Spalte erfasst wurde — dessen Ausschalten war die alte Regel,
                # nicht eine Entscheidung des Administrators. Es „unveraendert
                # zu lassen“ hiesse, den Austritt dauerhaft als Sperre
                # fortzuschreiben; genau das soll „Reaktivieren“ aufheben.
                # Bleibt eine Sperre wirklich gewollt, setzt der Administrator
                # sie nach dem Reaktivieren neu (`konto_sperren`, mit Schranken
                # und Protokoll) — der Hinweis in der Oberflaeche sagt das.
                konto.enabled = True if gemerkt is None else bool(gemerkt.get(name, True))
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()

    if aus:
        _update_doc(
            "Mitglied", mitglied_id, {"vor_austritt_konto_aktiv": zustand or None},
            explizite_null={"vor_austritt_konto_aktiv"},
        )
    else:
        _update_doc(
            "Mitglied", mitglied_id, {"vor_austritt_konto_aktiv": None},
            explizite_null={"vor_austritt_konto_aktiv"},
        )

    for name in konten:
        if aus:
            benutzer_status.widerrufe_sitzungen(name)
        else:
            benutzer_status.vergiss(name)
    return konten


@whitelist(allow_guest=False)
def mitglied_austritt(mitglied_id: str, begruendung: str = "", datum: str = "") -> dict[str, Any]:
    """„Austritt / Deaktivieren“ (A1/A2): Person ausgetreten, Konto aus, Sitzungen weg.

    Der vorherige Status wird gespeichert (``vor_austritt_status``), damit
    ``mitglied_reaktivieren`` ihn wiederherstellen kann. Keine Daten werden
    geloescht; die Person bleibt in alten Plaenen gekuerzt sichtbar.
    """
    if not _ist_admin():
        _kein_admin_melden("einen Austritt erfassen")

    # AUSTRITT-b (N1): Die Begruendung ist FREIWILLIG (A1: „optionale
    # Begruendung“). Austritt und Ausschluss unterscheidet der STATUS
    # („Ausgetreten“ vs. „Passiver Gast“) und `vor_austritt_status` — nicht
    # das Vorhandensein eines Freitexts.
    grund = _begruendung(begruendung)
    since = _datum(datum)

    zeile = get_value(
        "Mitglied", mitglied_id,
        ["name", "status", "ausgeschlossen", "ausgeschlossen_seit",
         "vor_austritt_status", "austritt_grund", "austritt_datum"],
        as_dict=True,
    )
    if not zeile:
        throw("Mitglied nicht gefunden.", ValidationError)
    zeile = dict(zeile)
    if zeile.get("status") == STATUS_AUSGETRETEN or (
        zeile.get("ausgeschlossen") and (
            zeile.get("austritt_grund") or zeile.get("austritt_datum"))
    ):
        throw("Diese Person ist bereits ausgetreten.", ValidationError)
    # AUSTRITT-d (NH1): Ein AUSGESCHLOSSENER wird nicht „ausgetragen“.
    # „Austritt → Reaktivieren“ setzt `ausgeschlossen=0`; der Weg
    # Ausschluss → Austritt → Reaktivieren hoebe den Ausschluss damit still auf
    # (und am Status-Weg samt dessen Schranken und Protokoll vorbei). Rechte
    # hin oder her — der Ausschluss wird zuerst aufgehoben oder bleibt.
    if zeile.get("ausgeschlossen"):
        throw(
            "Das Mitglied ist ausgeschlossen. Hebe zuerst den Ausschluss auf.",
            ValidationError,
        )

    ziel_user = _konto_pruefen(mitglied_id, "ausgetragen")

    # ACHTUNG Reihenfolge: die Schranke oben prueft den Zustand VOR dem
    # Schreiben. `_verweigere_letzten_admin_verlust*` liest live, greift also
    # nur, wenn das Konto schon ausgeschlossen ist. Deshalb wird das
    # Schreiben ueber den zentralen Schreibweg (`_update_doc`) gefahren —
    # der prueft den NACHHER-Zustand (`_pruefe_mitglied_schreibzugriff`).
    vorher = str(zeile.get("status") or "").strip()
    _marke_setzen(
        mitglied_id, True, status=STATUS_AUSGETRETEN, seit=since, grund=grund,
    )
    # A4: den Status merken, in den „Reaktivieren“ zurueckfuehrt.
    merke = vorher[:_STATUS_MAX] if vorher and vorher != STATUS_AUSGETRETEN else ""
    _update_doc(
        "Mitglied", mitglied_id, {"vor_austritt_status": merke or None},
        explizite_null={"vor_austritt_status"},
    )

    konten = _konten_schalten(mitglied_id, aus=True)

    eintrag: dict[str, Any] = {
        "ausgeschlossen": {"alt": "0", "neu": "1"},
        "status": {"alt": vorher, "neu": STATUS_AUSGETRETEN},
        "austritt_grund": {"alt": str(zeile.get("austritt_grund") or ""), "neu": grund},
        "austritt_datum": {
            "alt": str(zeile.get("ausgeschlossen_seit") or ""), "neu": since,
        },
    }
    if merke:
        eintrag["vor_austritt_status"] = {"alt": "", "neu": merke}
    _protokoll(mitglied_id, eintrag)

    return {
        "success": True,
        "message": "Austritt erfasst. Das Konto ist deaktiviert und alle Sitzungen wurden beendet.",
        "status": STATUS_AUSGETRETEN,
        "austritt_seit": since,
        "vor_austritt_status": merke or None,
        "konten": konten,
        "konto_deaktiviert": bool(konten),
        "ziel_user": ziel_user,
    }


@whitelist(allow_guest=False)
def mitglied_reaktivieren(mitglied_id: str) -> dict[str, Any]:
    """„Reaktivieren“ (A4): Austritt zuruecknehmen, Konto wieder aktiv.

    Rechteregeln wie beim Austritt: nur Administratoren, Verwaltungskonten
    nur durch einen System Manager (``_verweigere_fremdes_admin_konto`` —
    die Schranke greift unabhaengig von der Richtung).
    """
    if not _ist_admin():
        _kein_admin_melden("einen Austritt zurücknehmen")

    zeile = get_value(
        "Mitglied", mitglied_id,
        ["name", "status", "ausgeschlossen", "ausgeschlossen_seit",
         "vor_austritt_status", "austritt_grund", "austritt_datum"],
        as_dict=True,
    )
    if not zeile:
        throw("Mitglied nicht gefunden.", ValidationError)
    zeile = dict(zeile)
    # AUSTRITT-b (M2): „Reaktivieren“ ist ausschliesslich die Umkehr eines
    # Austritts. Zwei Faelle werden deshalb HART abgelehnt:
    #   * ein Endstatus („geloescht“/„verstorben“) — die DSGVO-Anonymisierung
    #     ist nicht umkehrbar, das Konto darf nie wieder aufgehen;
    #   * ein Ausschluss ohne Austrittsmerkmale — dafuer gibt es den
    #     Status-Weg im Profil, nicht diesen Endpunkt.
    status_klein = str(zeile.get("status") or "").strip().lower()
    if status_klein in _ENDSTATUS:
        throw(
            "Diese Person hat den Status „" + str(zeile.get("status")) + "“. "
            "Ein Austritt lässt sich dafür nicht zurücknehmen.",
            ValidationError,
        )
    if not zeile.get("ausgeschlossen"):
        # AUSTRITT-e (NR5): Der Altbestand „Ausgetreten“ OHNE Marke darf
        # reaktiviert werden (die Oberflaeche bietet es an, `art='austritt'`).
        # „Reaktivieren“ stellt dort „Mitglied“ her.
        if status_klein != STATUS_AUSGETRETEN.casefold():
            throw("Diese Person ist nicht ausgetreten — es gibt nichts zurückzunehmen.",
                  ValidationError)
    elif not (zeile.get("austritt_grund") or zeile.get("austritt_datum")
              or zeile.get("vor_austritt_status")
              or zeile.get("status") == STATUS_AUSGETRETEN):
        throw(
            "Diese Person ist ausgeschlossen, nicht ausgetreten. Bitte hebe den "
            "Ausschluss über den Status im Profil auf.",
            ValidationError,
        )

    from diakronos_app.api.zugang import _verweigere_fremdes_admin_konto

    ziel_user = str(get_value("Mitglied", mitglied_id, "user") or "")
    if ziel_user:
        _verweigere_fremdes_admin_konto(ziel_user)

    vorher = str(zeile.get("status") or "")
    zurueck = str(zeile.get("vor_austritt_status") or "").strip()
    if not zurueck or zurueck == STATUS_AUSGETRETEN:
        zurueck = "Mitglied"

    _marke_setzen(mitglied_id, False, status=zurueck, seit=None)
    _update_doc(
        "Mitglied", mitglied_id, {"vor_austritt_status": None},
        explizite_null={"vor_austritt_status"},
    )
    konten = _konten_schalten(mitglied_id, aus=False)

    _protokoll(mitglied_id, {
        "ausgeschlossen": {"alt": "1", "neu": "0"},
        "status": {"alt": vorher, "neu": zurueck},
        "austritt_grund": {"alt": str(zeile.get("austritt_grund") or ""), "neu": ""},
        "austritt_datum": {
            "alt": str(zeile.get("ausgeschlossen_seit") or ""), "neu": "",
        },
    })

    return {
        "success": True,
        "message": "Person ist wieder aktiv. Die Anzeige ist wieder vollständig.",
        "status": zurueck,
        "konten": konten,
        "konto_aktiv": bool(konten),
        "ziel_user": ziel_user,
    }


__all__ = ["BEGRUENDUNG_MAX", "STATUS_AUSGETRETEN", "mitglied_austritt", "mitglied_reaktivieren"]
