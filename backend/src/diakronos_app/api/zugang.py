"""P1-8 — Zugang pflegbar machen (OP-ADMIN-2, OP-ADMIN-3).

DER BEFUND
----------
Es gab keinen Weg vom Mitglied zum Zugang: keine Benutzerkonten, keine
Einladungen, keine Passwörter, keine Rollen in der Oberflaeche
(`api/nutzer.py` fehlte voellig). `create_mitglied` meldete trotzdem
`success`, obwohl es `mitglied_zu_nutzer` nur importierte und den ImportError
wegloggte (`api/mitglieder.py`, Kommentar „P3 offen").

Im Authentik-/OIDC-Modus entstehen Konten im Anbieter — das ist gewollt. Ohne
Authentik braucht die Gemeindeleitung aber sehr wohl einen Weg: Konto anlegen,
Rollen vergeben, Konto sperren/entsperren.

Dieses Modul ist dieser Weg. Es aendert AUSSCHLIESSLICH Konten und Rollen —
keine Mitgliederdaten, keine Passwoerter im Klartext.

OP-ADMIN-3 (Authentik-Modus „Als Gast anlegen"): im Modus `unbekannt_gast`
legt die Zuordnung Konten mit `enabled=False` an
(`anmeldung/zuordnung.py::_erzeuge_benutzer`). Freischalten konnte sie
NIEMAND — kein Endpunkt setzte `enabled=1`. `get_wartende_konten` und
`konto_freischalten` schliessen diese Luecke: die Liste zeigt Konten ohne
Zugang bzw. gesperrte Konten, die Freischaltung ist derselbe Schalter wie
`enabled`.
"""

from __future__ import annotations

from typing import Any

from diakronos_app.api.verantwortliche import _require_admin, ZUGANGS_ROLLEN
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat import benutzer_status
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    FrappeCompatError,
    PermissionError as FrappePermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.permissions import get_roles
from diakronos_app.frappe_compat.query import get_all, get_value
from diakronos_app.frappe_compat.personen_anzeige import kuerze_name
from diakronos_app.frappe_compat.session import session

# Rollen, die Verwaltungsrechte ueber Konten und Rollen geben. Der System
# Manager ist die oberste Stufe; der Mitgliederadministrator darf Mitglieder
# und einfache Rollen pflegen, aber niemanden hoeher stufen (BLD-R1).
SYSTEM_MANAGER_ROLLE = "System Manager"
ADMIN_ROLLEN = ("System Manager", "Mitgliederadministrator")


def _ist_system_manager() -> bool:
    """Hat der angemeldete Benutzer die Rolle System Manager?"""
    return SYSTEM_MANAGER_ROLLE in get_roles()


def _require_system_manager() -> str:
    """Nur System Manager — fuer Konten/Rollen mit Verwaltungsrechten (BLD-R1)."""
    user = str(session.user or "").strip()
    if not user or user == "Guest":
        throw("Anmeldung verweigert.", FrappePermissionError)
    if not _ist_system_manager():
        throw(
            "Nur System Manager dürfen Konten und Rollen mit Verwaltungsrechten ändern.",
            FrappePermissionError,
        )
    return user


def _konto_name(freitext: Any, konto: str, *, ausgeschieden: bool) -> str:
    """Anzeigename eines Kontos — gekuerzt, wenn das Mitglied ausgeschieden ist."""
    konto = str(konto or "")
    text = str(freitext or "").strip()
    if ausgeschieden:
        teile = text.split()
        if len(teile) >= 2:
            return kuerze_name(teile[0], teile[-1], konto)
        return kuerze_name(text, "", konto)
    return text or konto


def _rollen_von(user: str) -> set[str]:
    """Die Rollen eines KONTOS (nicht des Aufrufers) als Menge.

    R-N10 Punkt 7: Die `Has Role`-Tabelle ist mit Frappe gewachsen und enthaelt
    auch Zeilen fuer ANDERE Eltern-DocTypes (z. B. Seiten/Berichte wie `ToDo`,
    `backups`), deren `parent` zufaellig wie ein Benutzername aussehen kann.
    Ein Konto hat nur Rollen, deren Zeile ein Kind des DocType `User` ist —
    ohne diesen Filter zaehlte der Aussperrschutz fremde Zeilen mit.

    Altdaten ohne `parenttype` (NULL/leer) zaehlen als `User`
    (`permissions.ist_user_zeile`) — ein reiner `parenttype == "User"`-Filter
    wuerde diese legitimen Zeilen verwerfen.
    """
    from diakronos_app.frappe_compat.permissions import ist_user_zeile

    zeilen = get_all(
        "Has Role",
        filters={"parent": user},
        fields=["role", "parenttype"],
    ) or []
    return {str(z["role"]) for z in zeilen
            if z.get("role") and ist_user_zeile(z.get("parenttype"))}


def _hat_admin_rolle(user: str) -> bool:
    """Traegt das Konto eine der Verwaltungsrollen (System Manager/…admin)?"""
    return bool(_rollen_von(user) & set(ADMIN_ROLLEN))


def _verweigere_fremdes_admin_konto(ziel_user: str) -> None:
    """Ein Mitgliederadministrator darf kein Verwaltungskonto anfassen (B1).

    Reproduziert vom unabhaengigen Sicherheits-Review R-P1-8: ein
    Mitgliederadministrator konnte das Passwort eines System-Manager-Kontos
    setzen oder dieses sperren — volle Uebernahme. Er darf nur Konten OHNE
    Verwaltungsrolle pflegen.
    """
    if _ist_system_manager():
        return
    if _hat_admin_rolle(ziel_user):
        throw(
            "Konten mit Verwaltungsrechten darf nur ein System Manager ändern.",
            FrappePermissionError,
        )


def _aktive_system_manager(*, _mitglieder=None, _konten=None) -> set[str]:
    """Konten mit System-Manager-Rolle, die wirklich noch verwalten koennen.

    Zwei Bedingungen (P1-8d, Pflicht c): `User.enabled` UND das Konto ist nicht
    ueber ein wirksames Mitglied ausgeschlossen (`benutzer_status`). VORHER
    zaehlte nur `enabled` — ein ausgeschlossener System Manager galt weiter als
    aktiv, weshalb im Zwei-Schritt (A schliesst B aus, dann sich selbst) beide
    ausgeschlossen wurden und niemand mehr Administrator war.
    """
    from diakronos_app.db import lesesitzung
    from diakronos_app.models.core import HasRole, User
    from sqlalchemy import or_
    from diakronos_app.frappe_compat.benutzer_status import (
        _ausgeschlossene_konten, _kontozustand,
    )

    with lesesitzung() as sess:
        namen = {
            str(r.parent) for r in
            sess.query(HasRole).filter(
                HasRole.role == SYSTEM_MANAGER_ROLLE,
                # R-N10 Punkt 7: nur Zeilen, deren Elter ein User ist. Fremde
                # Has-Role-Zeilen (Frappe-Seiten/Berichte) haben einen anderen
                # `parenttype` und zaehlen hier nicht als Konto-Rolle.
                # Altdaten ohne `parenttype` (NULL/leer) zaehlen als `User`
                # (`permissions.ist_user_zeile`).
                or_(HasRole.parenttype.is_(None), HasRole.parenttype == "",
                    HasRole.parenttype == "User"),
            ).all()
            if r.parent
        }
        aktiv = _nur_aktive(sess, namen, User)
    if _mitglieder is None or _konten is None:
        _mitglieder, _konten = _kontozustand()
    return aktiv - _ausgeschlossene_konten(_mitglieder, _konten)


def _konto_ausgeschlossen(user: str) -> bool:
    """Dieselbe Ausschluss-Regel wie für Rollen und Sitzungen, ohne Ringbezug."""
    return benutzer_status._mitglied_ausgeschlossen(user)


def _konto_mitglieder(user: str) -> list[str]:
    """Mitglieder-Kennungen, die auf dieses Konto zeigen (`Mitglied.user`).

    Grundlage der Verknuepfungs-Regel (P1-8c, Pflicht 1c): ein Konto darf nur
    dann umgehaengt werden, wenn es noch keinem Mitglied gehoert — sonst
    wandert der Zugang still von einer Person zur anderen.

    SEC-d (B1): LESE-Helfer ueber `lesesitzung()` — im Import-Lauf also die
    Sitzung des Laufs. Vorher oeffnete die Funktion unbedingt eine ZWEITE
    `SessionLocal()` und schloss sie wieder. Auf einer Datenbank, die eine
    Verbindung je Engine teilt, reisst dieses `close()` die offene
    Transaktion des Aufrufers mit; im Import verschwand so der Speicherpunkt
    („no such savepoint“). Ausserdem sieht die zweite Sitzung die noch nicht
    committeten Zeilen des Laufs nicht.
    """
    from sqlalchemy import select

    from diakronos_app.db import lesesitzung
    from diakronos_app.models.diakonos import Mitglied

    with lesesitzung() as sess:
        return [
            str(n) for n in sess.scalars(
                select(Mitglied.name).where(Mitglied.user == user)
            ).all()
            if n
        ]


def _aktive_administratoren() -> set[str]:
    """Konten mit EINER Verwaltungsrolle (System Manager ODER Mitgliederadmin),
    die aktiv (enabled) sind — der Kreis, dessen letzter Vertreter nicht
    ausgesperrt werden darf (B2, R-P1-8: auch der Selbstentzug der eigenen
    Mitgliederadministrator-Rolle sperrte die Verwaltung aus).

    N12b (R-N10 Punkt 7): nur Kindzeilen des DocType `User`
    (`permissions.ist_user_zeile`) — sonst zaehlte eine Seite oder ein Bericht
    namens `backups` als Administrator mit und die Schranke liesse sich
    umgehen.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.permissions import ist_user_zeile
    from diakronos_app.models.core import HasRole, User

    sess = SessionLocal()
    try:
        namen = {
            str(r.parent) for r in
            sess.query(HasRole).filter(HasRole.role.in_(list(ADMIN_ROLLEN))).all()
            if r.parent and ist_user_zeile(r.parenttype)
        }
        return _nur_aktive(sess, namen, User)
    finally:
        sess.close()


def _nur_aktive(sess, namen: set[str], User) -> set[str]:
    """Aus Kontonamen die aktiven (`enabled`) herausfiltern."""
    aktiv: set[str] = set()
    for name in namen:
        konto = sess.get(User, name)
        if konto is not None and bool(konto.enabled):
            aktiv.add(name)
    return aktiv


def _verweigere_letzten_admin_verlust(ziel_user: str, grund: str) -> None:
    """Der letzte aktive System Manager darf nicht ausgesperrt werden (B2).

    Reproduziert von R-P1-8: der einzige System Manager konnte sein eigenes
    Konto sperren oder sich seine Rolle entziehen — danach kam man nur noch
    per Datenbankeingriff an die Verwaltung. Das gilt fuer Sperren, Rollen-
    entzug UND Ausschluss, auch wenn der Betroffene selbst handelt.
    """
    if ziel_user not in _aktive_system_manager():
        return
    if len(_aktive_system_manager()) <= 1:
        throw(
            f"Der letzte aktive System Manager kann nicht {grund} werden — "
            "sonst ist die Verwaltung ausgesperrt. Bitte zuerst einen weiteren "
            "System Manager benennen.",
            FrappePermissionError,
        )


def _verweigere_letzten_admin_verlust_alle(ziel_user: str, grund: str) -> None:
    """Kein aktives Verwaltungskonto darf der LETZTE Administrator bleiben (B2).

    Erweiterung zu `_verweigere_letzten_admin_verlust`: greift auch, wenn nur
    noch ein Mitgliederadministrator (ohne System Manager) uebrig ist. Ohne
    diese Schranke konnte sich der letzte Mitgliederadministrator per
    `setze_rollen(eigenes, ["Mitglied"])` die eigene Rolle entziehen — dann kam
    niemand mehr an die Rollenpflege.
    """
    if ziel_user not in _aktive_administratoren():
        return
    if len(_aktive_administratoren()) <= 1:
        throw(
            f"Der letzte aktive Administrator kann nicht {grund} werden — "
            "sonst ist die Verwaltung ausgesperrt. Bitte zuerst einen weiteren "
            "Administrator benennen.",
            FrappePermissionError,
        )


def _konto_zeile(user: str) -> dict[str, Any]:
    """Konto + zugehoeriges Mitglied fuer die Zugangsliste."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Mitglied

    sess = SessionLocal()
    try:
        konto = sess.get(User, user)
        if konto is None:
            raise DoesNotExistError("Benutzerkonto nicht gefunden.")
        rollen = [
            r.role for r in
            sess.query(HasRole).filter(HasRole.parent == user).all()
            if r.role
        ]
        mitglieder = [
            m for m in sess.query(Mitglied).filter(Mitglied.user == user).all()
        ]
        mitglied = mitglieder[0] if mitglieder else None
        return {
            "user": konto.name,
            "email": konto.email,
            "full_name": konto.full_name,
            "enabled": bool(konto.enabled),
            "hat_passwort": bool(konto.password_hash),
            "rollen": sorted(rollen),
            "mitglied": mitglied.name if mitglied else None,
            "mitglied_name": (
                " ".join(
                    p for p in (mitglied.vorname, mitglied.nachname) if p
                ) if mitglied else None
            ),
            "ausgeschlossen": bool(mitglied.ausgeschlossen) if mitglied else False,
        }
    finally:
        sess.close()


@whitelist(allow_guest=False)
def get_zugang(mitglied_id: str) -> dict[str, Any]:
    """Zugang (Konto + Rollen) eines Mitglieds zeigen (Admin).

    Liefert `konto=None`, wenn das Mitglied kein Konto hat — dann bietet die
    Oberflaeche „Konto anlegen" an. `rollen_waehlbar` ist die feste
    Diakronos-Liste; zugewiesene Rollen daraus markiert.
    """
    _require_admin()
    name = str(mitglied_id or "").strip()
    if not name or get_value("Mitglied", name, "name") is None:
        throw("Mitglied nicht gefunden.", DoesNotExistError)
    user = get_value("Mitglied", name, "user")
    konto = _konto_zeile(str(user)) if user else None
    from diakronos_app.anmeldung.konfiguration import oidc_aktiv
    return {
        "oidc_aktiv": oidc_aktiv(),
        "success": True,
        "mitglied": name,
        "email": get_value("Mitglied", name, "email") or None,
        "konto": konto,
        "rollen_waehlbar": list(ZUGANGS_ROLLEN),
    }


@whitelist(allow_guest=False)
def setze_rollen(mitglied_id: str, rollen: list[str] | None = None) -> dict[str, Any]:
    """Rollen eines Kontos setzen — nur aus der festen Diakronos-Liste (Admin).

    „Vollstaendig" wie in `verantwortliche.set_verantwortliche`: die Liste
    ersetzt den Bestand der DIAKRONOS-Rollen. Fremde Rollen (ERPNext-Erbe)
    werden NICHT angetastet — sie gehoeren nicht in diese Oberflaeche.
    """
    _require_admin()
    name = str(mitglied_id or "").strip()
    if get_value("Mitglied", name, "name") is None:
        throw("Mitglied nicht gefunden.", DoesNotExistError)
    user = get_value("Mitglied", name, "user")
    if not user:
        throw("Dieses Mitglied hat kein Benutzerkonto.", ValidationError)

    if rollen is None:
        rollen = []
    if isinstance(rollen, str):
        import json

        try:
            rollen = json.loads(rollen)
        except (TypeError, ValueError):
            rollen = [rollen]
    if not isinstance(rollen, list):
        throw("rollen muss eine Liste sein.", ValidationError)

    gewuenscht: list[str] = []
    for r in rollen:
        wert = str(r or "").strip()
        if not wert:
            continue
        if wert not in ZUGANGS_ROLLEN:
            throw(f"Unbekannte Rolle: {wert}", ValidationError)
        if wert not in gewuenscht:
            gewuenscht.append(wert)

    # B1 (R-P1-8): Admin-Rollen vergibt/entzieht NUR ein System Manager. Sonst
    # koennte sich ein Mitgliederadministrator zum System Manager machen oder
    # sich selbst einen Admin-Klon anlegen. Ein Mitgliederadministrator darf
    # ausserdem Konten mit Verwaltungsrechten gar nicht erst umrollen.
    _verweigere_fremdes_admin_konto(str(user))
    if not _ist_system_manager():
        neu_admin = set(gewuenscht) & {"Mitgliederadministrator"}
        alt_admin = _rollen_von(str(user)) & {"System Manager", "Mitgliederadministrator"}
        if neu_admin or alt_admin:
            throw(
                "Verwaltungsrollen darf nur ein System Manager vergeben oder entziehen.",
                FrappePermissionError,
            )

    # B2 (R-P1-8): kein Administrator darf der LETZTE bleiben, dem die eigene
    # Verwaltungsrolle entzogen wird — auch nicht durch sich selbst.
    #
    # P1-8c, Pflicht 2 (Falsch-Positiv): `ZUGANGS_ROLLEN` enthaelt gar keinen
    # "System Manager". Wer `["Mitglied", "Kalenderadministrator"]` sendet,
    # tastet die fremde Rolle also NICHT an. Der Schutz darf nur greifen, wenn
    # die behaltene Verwaltungsrolle tatsaechlich verschwindet — sonst kann
    # sich der einzige Administrator nicht einmal Zusatzrollen geben.
    behalten = set(gewuenscht) | (_rollen_von(str(user)) - set(ZUGANGS_ROLLEN))
    if (_rollen_von(str(user)) & set(ADMIN_ROLLEN)) and not (behalten & set(ADMIN_ROLLEN)):
        _verweigere_letzten_admin_verlust_alle(str(user), "seiner Verwaltungsrolle enthoben")

    _setze_diakronos_rollen(str(user), gewuenscht)
    return {"success": True, "konto": _konto_zeile(str(user))}


def _setze_diakronos_rollen(user: str, rollen: list[str]) -> None:
    """Nur Rollen aus `ZUGANGS_ROLLEN` ersetzen, fremde unberuehrt (eine Sache)."""
    import uuid

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import HasRole

    sess = SessionLocal()
    try:
        bestand = [
            r for r in sess.query(HasRole).filter(HasRole.parent == user).all()
        ]
        # Fremde Rollen behalten; nur die Diakronos-Rollen neu setzen.
        idx = len([r for r in bestand if r.role not in ZUGANGS_ROLLEN])
        for r in bestand:
            if r.role in ZUGANGS_ROLLEN:
                sess.delete(r)
        for rolle in rollen:
            idx += 1
            sess.add(HasRole(
                name=f"HR-{uuid.uuid4().hex[:10]}",
                parent=user,
                parenttype="User",
                parentfield="roles",
                role=rolle,
                docstatus=0,
                idx=idx,
            ))
        sess.commit()
    except FrappeCompatError:
        sess.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        sess.rollback()
        raise ValidationError(str(exc)) from exc
    finally:
        sess.close()


@whitelist(allow_guest=False)
def konto_anlegen(mitglied_id: str) -> dict[str, Any]:
    """Konto fuer ein Mitglied anlegen (Admin, OHNE Authentik).

    Ohne Authentik ist das der EINZIGE Weg zu einem Zugang. Das Konto wird
    MIT Passwort-Option angelegt; das Startpasswort selbst vergibt der
    naechste Schritt (Einladungslink/Passwort, Paket N5) — hier entsteht
    nur die Kontozeile mit der Rolle „Mitglied".

    Im Authentik-Modus ist dieser Weg NICHT vorgesehen (Entscheidung 5):
    `oidc_aktiv` -> Ablehnung mit klarem Hinweis, damit keine Konten
    entstehen, die der Anbieter nicht kennt.
    """
    _require_admin()
    from diakronos_app.anmeldung.konfiguration import oidc_aktiv

    name = str(mitglied_id or "").strip()
    if not name or get_value("Mitglied", name, "name") is None:
        throw("Mitglied nicht gefunden.", DoesNotExistError)
    if oidc_aktiv():
        throw(
            "Über Authentik entstehen Konten beim Anbieter — bitte dort anlegen. "
            "Die Zuordnung passiert beim ersten Login über die E-Mail.",
            ValidationError,
        )
    if get_value("Mitglied", name, "user"):
        throw("Dieses Mitglied hat bereits ein Benutzerkonto.", ValidationError)

    email = str(get_value("Mitglied", name, "email") or "").strip().lower()
    if not email:
        throw("Für ein Konto wird eine E-Mail-Adresse benötigt.", ValidationError)
    from diakronos_app.email_belegung import belegung
    if belegung(email, ohne_mitglied=name):
        throw("Es gibt bereits eine Person oder ein Konto mit dieser E-Mail-Adresse.", ValidationError)

    from datetime import datetime

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import HasRole, User

    sess = SessionLocal()
    try:
        sess.add(User(
            name=email,
            email=email,
            full_name=str(get_value("Mitglied", name, "vorname") or "") + " " +
            str(get_value("Mitglied", name, "nachname") or ""),
            enabled=True,
            password_hash=None,  # Startpasswort folgt (N5)
            user_type="Website User",
        ))
        sess.add(HasRole(
            name=f"HR-{email}-Mitglied",
            parent=email,
            parenttype="User",
            parentfield="roles",
            role="Mitglied",
            docstatus=0,
            idx=1,
        ))
        sess.commit()
    except FrappeCompatError:
        sess.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        sess.rollback()
        raise ValidationError(str(exc)) from exc
    finally:
        sess.close()

    # Mitglied und Konto verbinden — ueber dieselbe Naht wie die Zuordnung.
    from diakronos_app.frappe_compat.query import get_doc

    doc = get_doc("Mitglied", name)
    doc.db_set("user", email)
    _protokoll(name, "Benutzerkonto angelegt")
    return {"success": True, "konto": _konto_zeile(email)}


@whitelist(allow_guest=False)
def konto_sperren(mitglied_id: str, gesperrt: bool = True) -> dict[str, Any]:
    """Konto sperren (`enabled=False`) oder freischalten (Admin).

    Aktiver Widerruf: `widerrufe_sitzungen` beendet die Sitzungen sofort, der
    Status-Cache wird vergessen — dieselbe Funktion, die auch
    `delete_my_data` benutzt (B1).
    """
    _require_admin()
    name = str(mitglied_id or "").strip()
    if get_value("Mitglied", name, "name") is None:
        throw("Mitglied nicht gefunden.", DoesNotExistError)
    user = get_value("Mitglied", name, "user")
    if not user:
        throw("Dieses Mitglied hat kein Benutzerkonto.", ValidationError)

    wert = gesperrt
    if isinstance(wert, str):
        wert = wert.strip().lower() in ("true", "1", "yes")
    wert = bool(wert)

    # B1/B2 (R-P1-8): Sperren eines Verwaltungskontos nur durch System Manager,
    # und niemals den letzten aktiven System Manager aussperren (auch nicht
    # durch sich selbst).
    _verweigere_fremdes_admin_konto(str(user))
    if wert:
        _verweigere_letzten_admin_verlust(str(user), "gesperrt")

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import User

    sess = SessionLocal()
    try:
        konto = sess.get(User, str(user))
        if konto is None:
            raise DoesNotExistError("Benutzerkonto nicht gefunden.")
        konto.enabled = not wert
        sess.commit()
    except FrappeCompatError:
        sess.rollback()
        raise
    finally:
        sess.close()

    if wert:
        benutzer_status.widerrufe_sitzungen(str(user))
    else:
        benutzer_status.vergiss(str(user))
    _protokoll(name, "Konto gesperrt" if wert else "Konto freigeschaltet")
    return {"success": True, "konto": _konto_zeile(str(user))}


@whitelist(allow_guest=False)
def setze_passwort(mitglied_id: str, passwort: str, request=None) -> dict[str, Any]:
    """Startpasswort eines Kontos setzen (Admin, Argon2).

    N5: Vor der ersten Vollsitzung muss die Person ein eigenes Passwort
    setzen. Bestehende Sitzungen und Passwort-Links werden widerrufen.
    """
    _require_admin()
    _nur_post(request)
    name = str(mitglied_id or "").strip()
    if get_value("Mitglied", name, "name") is None:
        throw("Mitglied nicht gefunden.", DoesNotExistError)
    user = get_value("Mitglied", name, "user")
    if not user:
        throw("Dieses Mitglied hat kein Benutzerkonto.", ValidationError)
    from diakronos_app.anmeldung.passwortzugang import pruefe_passwort
    from diakronos_app.anmeldung.konfiguration import oidc_aktiv
    if oidc_aktiv():
        throw("Passwörter werden über Authentik verwaltet.", ValidationError)
    pruefe_passwort(passwort)

    # B1 (R-P1-8): ein Mitgliederadministrator darf kein Verwaltungskonto
    # uebernehmen, indem er dessen Startpasswort setzt.
    _verweigere_fremdes_admin_konto(str(user))

    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import User

    sess = SessionLocal()
    try:
        konto = sess.get(User, str(user), with_for_update=True)
        if konto is None:
            raise DoesNotExistError("Benutzerkonto nicht gefunden.")
        from diakronos_app.anmeldung.passwortzugang import startpasswort_markieren
        konto.password_hash = neuer_hash(passwort)
        startpasswort_markieren(sess, str(user))
        sess.commit()
    except FrappeCompatError:
        sess.rollback()
        raise
    finally:
        sess.close()
    benutzer_status.widerrufe_sitzungen(str(user))
    _protokoll(name, "Startpasswort gesetzt")
    return {"success": True}


@whitelist(allow_guest=False)
def konto_freischalten(user: str, freischalten: bool = True) -> dict[str, Any]:
    """Konto direkt ueber seinen Kontonamen sperren/freischalten (Admin).

    R-P1-8/W1: Gastkonten aus dem Modus „Als Gast anlegen"
    (`anmeldung/zuordnung.py::_erzeuge_benutzer`) entstehen mit
    `enabled=False` und OHNE Mitglied. `konto_sperren` adressiert ueber
    `mitglied_id` und ist damit fuer sie nicht erreichbar — sie warteten
    dauerhaft. Dieser Endpunkt schaltet ueber den Kontonamen, unabhaengig von
    einem Mitglied. Der Kontoname ist hier NICHT die E-Mail-Angabe, sondern
    exakt der `User.name` aus `get_wartende_konten`.

    Gesperrte Konten mit Verwaltungsrolle sind geschuetzt: `_verweigere_fremdes_admin_konto`
    laesst nur einen System Manager heran und `_verweigere_letzten_admin_verlust`
    verhindert, dass der letzte aktive System Manager gesperrt wird.
    """
    _require_admin()
    konto_name = str(user or "").strip()
    if not konto_name or konto_name == "Guest":
        throw("Bitte ein Konto angeben.", ValidationError)
    if get_value("User", konto_name, "name") is None:
        throw("Benutzerkonto nicht gefunden.", DoesNotExistError)

    # B1: nur ein System Manager darf Konten mit Verwaltungsrechten schalten.
    _verweigere_fremdes_admin_konto(konto_name)

    wert = freischalten
    if isinstance(wert, str):
        wert = wert.strip().lower() in ("true", "1", "yes")
    wert = bool(wert)
    if not wert:
        _verweigere_letzten_admin_verlust(konto_name, "gesperrt")

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import User

    sess = SessionLocal()
    try:
        konto = sess.get(User, konto_name)
        if konto is None:
            raise DoesNotExistError("Benutzerkonto nicht gefunden.")
        konto.enabled = wert
        sess.commit()
    except FrappeCompatError:
        sess.rollback()
        raise
    finally:
        sess.close()

    if wert:
        benutzer_status.vergiss(konto_name)
    else:
        benutzer_status.widerrufe_sitzungen(konto_name)
    _protokoll(konto_name, "Konto freigeschaltet" if wert else "Konto gesperrt")
    return {"success": True, "konto": _konto_zeile(konto_name)}


@whitelist(allow_guest=False)
def get_wartende_konten() -> dict[str, Any]:
    """Konten ohne Freischaltung (OP-ADMIN-3) — Admin.

    Im Authentik-Modus „Als Gast anlegen" entstehen Konten mit
    `enabled=False`. Diese Liste zeigt sie (samt Mitglied) und erlaubt die
    Freischaltung: Konten MIT Mitglied ueber `konto_sperren(gesperrt=False)`,
    Gastkonten OHNE Mitglied ueber `konto_freischalten(user, freischalten=True)`
    — dieselbe Zuordnung, die die Oberflaeche (Einstellungen → Anmeldung)
    benutzt.

    R-N8 (Punkt 2): zusaetzlich werden ABGELEHNTE E-Mail-Zuordnungen gezeigt
    (Anbieter-Konto trifft auf eine Person, deren Zuordnung nicht eindeutig/
    verifiziert/freigegeben ist). Sie stehen getrennt unter ``abgelehnt`` mit
    Grund und Meldung — so sieht die Verwaltung, wen sie pruefen muss.
    """
    _require_admin()
    zeilen = get_all(
        "User",
        filters={"enabled": False},
        fields=["name", "email", "full_name"],
        order_by="name asc",
    ) or []
    ergebnis: list[dict[str, Any]] = []
    for z in zeilen:
        daten = _konto_zeile(str(z.get("name")))
        ergebnis.append(daten)
    return {
        "success": True,
        "konten": ergebnis,
        "abgelehnt": _abgelehnte_zuordnungen(),
    }


def _abgelehnte_zuordnungen() -> list[dict[str, Any]]:
    """Abgelehnte E-Mail-Zuordnungen fuer die Verwaltung (R-N8, Punkt 2)."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.auth_oidc import ZuordnungsAblehnung

    sess = SessionLocal()
    try:
        zeilen = (
            sess.query(ZuordnungsAblehnung)
            .order_by(ZuordnungsAblehnung.zuletzt.desc())
            .all()
        )
        return [
            {
                "email": z.email,
                "name": z.name_anzeige,
                "grund": z.grund,
                "meldung": z.meldung,
                "versuche": int(z.versuche or 0),
                "zuletzt": z.zuletzt.isoformat() if z.zuletzt else None,
            }
            for z in zeilen
        ]
    finally:
        sess.close()


@whitelist(allow_guest=False)
def get_zugangsmodus():
    _require_admin()
    from diakronos_app.anmeldung.konfiguration import oidc_aktiv
    return {"oidc_aktiv": oidc_aktiv()}


@whitelist(allow_guest=False)
def einladungslink(mitglied_id: str, request=None):
    _require_admin()
    _nur_post(request)
    from diakronos_app.anmeldung.konfiguration import oidc_aktiv
    from diakronos_app.anmeldung.passwortzugang import link_erzeugen
    if oidc_aktiv():
        throw("Passwörter werden über Authentik verwaltet.", ValidationError)
    name = str(mitglied_id or "").strip()
    if get_value("Mitglied", name, "name") is None:
        throw("Mitglied nicht gefunden.", DoesNotExistError)
    user = get_value("Mitglied", name, "user")
    if not user:
        konto_anlegen(name)
        user = get_value("Mitglied", name, "user")
    _verweigere_fremdes_admin_konto(str(user))
    daten = link_erzeugen(str(user))
    _protokoll(name, "Passwort-Link erstellt (vorheriger Link ungültig)")
    return {"success": True, **daten}


@whitelist(allow_guest=False)
def get_rollen_uebersicht() -> dict[str, Any]:
    """Wer hat welche Rolle — die Lese-Tabelle des Abschnitts „Rollen & Rechte" (N10).

    Liefert je Person mit Konto: Mitglied-Kennung, Anzeigename, Kontoname
    (= E-Mail), die zugewiesenen DIAKRONOS-Rollen und den Kontozustand
    (aktiv/gesperrt/ausgeschlossen). Dazu die feste, waehlbare Rollenliste
    (`rollen_waehlbar`) und die Angabe, ob der Aufrufer ueberhaupt
    Verwaltungsrollen vergeben darf (`darf_verwalten`, `ist_system_manager`).

    Rechte: nur Administratoren (wie `get_zugang`). Die Anzeige folgt dem
    Server — die Oberflaeche blendet nur aus, was hier ohnehin fehlt.
    """
    _require_admin()
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Mitglied

    konten = get_all(
        "User",
        filters={"enabled": ["in", [0, 1]]},
        fields=["name", "email", "full_name", "enabled"],
        order_by="full_name asc",
    ) or []
    mitglieder = get_all(
        "Mitglied",
        filters={"user": ["is", "set"]},
        fields=["name", "vorname", "nachname", "user", "ausgeschlossen", "status"],
    ) or []
    nach_konto: dict[str, dict[str, Any]] = {}
    for m in mitglieder:
        u = str(m.get("user") or "")
        if u and u not in nach_konto:
            nach_konto[u] = m
    # AUSTRITT-d (NM2): Diese Tabelle steht nur Administratoren offen (siehe
    # oben), dort gilt „Administratoren sehen alles“ — keine Kuerzung. Der
    # Kontoname (Adresse) bleibt in jedem Fall, ohne ihn waere keine Zeile
    # bedienbar.

    zeilen: list[dict[str, Any]] = []
    for k in konten:
        konto = str(k.get("name") or "")
        if not konto:
            continue
        m = nach_konto.get(konto)
        anzeige = " ".join(
            p for p in ((m or {}).get("vorname"), (m or {}).get("nachname")) if p
        ).strip()
        zeilen.append({
            "user": konto,
            "email": k.get("email") or None,
            "full_name": k.get("full_name") or None,
            "mitglied": (m or {}).get("name"),
            "anzeige": anzeige or _konto_name(
                k.get("full_name"), konto, ausgeschieden=False),
            "status": (m or {}).get("status"),
            "enabled": bool(k.get("enabled")),
            "ausgeschlossen": bool((m or {}).get("ausgeschlossen")),
            "rollen": sorted(_rollen_von(konto)),
            # K2 (R-N10): Ein Konto ohne Mitglied kann keine Rollen bekommen
            # (die Rollen haengen am Mitglied). Die Tabelle nennt den Grund.
            "hinweis": None if m else "Ohne Mitglied — Rollen bitte unter „Anmeldung“ freischalten.",
        })

    ist_sm = _ist_system_manager()
    aktive_sm = _aktive_system_manager()
    return {
        "success": True,
        "konten": zeilen,
        "rollen_waehlbar": list(ZUGANGS_ROLLEN),
        # K3 (R-N10): NICHT konstant True. Ob Verwaltungsrollen vergeben werden
        # duerfen, entscheidet die System-Manager-Rolle (`setze_rollen` prueft
        # dasselbe). Ein Mitgliederadministrator darf KEINE Admin-Rolle
        # vergeben/entziehen — fuer ihn ist der Wert False.
        "darf_verwalten": ist_sm,
        "ist_system_manager": ist_sm,
        "aktive_system_manager": sorted(aktive_sm),
    }


def _nur_post(request):
    if request is not None and request.method != "POST":
        throw("Diese Aktion ist nur per POST erlaubt.", ValidationError)


@whitelist(allow_guest=True)
def passwort_uebernehmen(token: str, passwort: str, request=None):
    _nur_post(request)
    from fastapi.responses import JSONResponse
    from diakronos_app.frappe_compat import loginversuche
    from diakronos_app.request_context import zaehler_client_ip
    # Dieselbe IP-/Backoff-Bremse wie Login, vor Datenbank und Passwort-Hash.
    # Die Kennung ist ein Token, kein Konto; nur gehasht im Redis-Keyspace.
    erlaubt, _ = loginversuche.pruefe_und_merke(
        'passwort-link:' + str(token), zaehler_client_ip())
    if not erlaubt:
        return JSONResponse(status_code=429, content={
            'message': 'Zu viele Versuche. Bitte versuche es später erneut.'})
    from diakronos_app.anmeldung.passwortzugang import passwort_uebernehmen as uebernehmen
    return uebernehmen(token, passwort)


def _protokoll(mitglied_id: str, vorgang: str) -> None:
    """Audit-Log-Eintrag zu einer Zugangsänderung (nachvollziehbar, Art. 5)."""
    try:
        from diakronos_app.api.mitglieder import _log_profil_aenderung

        _log_profil_aenderung(mitglied_id, {"zugang": {"alt": "", "neu": vorgang}})
    except Exception:  # noqa: BLE001 — Audit darf den Vorgang nicht kippen
        from diakronos_app.frappe_compat.api_helpers import log_error

        log_error(f"Zugangs-Protokoll fehlgeschlagen: {vorgang}", "zugang")


@whitelist(allow_guest=False)
def get_konten_liste():
    """Alle Benutzerkonten für Auswahlfelder (P2-5, Kalender-Verwaltung).

    Die Kalenderverwaltung braucht eine Liste von PERSONEN, die als Moderator
    eines Kalenders eingetragen werden koennen — die Moderatorzeile zeigt auf
    `user.name` (`Kalender Moderator.user`), nicht auf ein Mitglied und nicht
    auf eine E-Mail. Die Mitgliederliste taugt dafuer nicht: sie liefert
    Mitglieder, und nicht jedes Mitglied hat ein Konto (und umgekehrt).

    Nur Administratoren (dieselbe Schranke wie der uebrige Zugangsbereich).
    Passwoerter oder Hashes sind nicht Teil der Antwort — nur Kennung, Name
    und die Rollen, die die Auswahl lesbar machen.
    """
    _require_admin()

    zeilen = get_all(
        "User",
        fields=["name", "email", "full_name", "enabled"],
        order_by="full_name asc",
    ) or []

    from diakronos_app.frappe_compat.permissions import get_roles

    # AUSTRITT-d (NM2): Dieser Endpunkt verlangt eine ADMIN-Rolle — dort gilt
    # „Administratoren sehen alles“ (N3). Die Kuerzung entfaellt hier ganz,
    # damit alle drei Personenlisten dieselbe Regel zeigen; sonst standen
    # `get_konten_liste` und `get_rollen_uebersicht` gegeneinander.
    konten = []
    for roh in zeilen:
        z = dict(roh)
        name = str(z.get("name") or "").strip()
        if not name:
            continue
        try:
            rollen = list(get_roles(name))
        except Exception:  # noqa: BLE001 — Rollen sind Beiwerk der Auswahl
            rollen = []
        konten.append({
            "user": name,
            "email": z.get("email") or "",
            "name": _konto_name(z.get("full_name"), name, ausgeschieden=False),
            "aktiv": bool(z.get("enabled", True)),
            "rollen": rollen,
        })
    return {"success": True, "konten": konten}


@whitelist(allow_guest=False)
def get_moderator_auswahl() -> dict[str, Any]:
    """Schmale Konto-Auswahl fuer Kalender-/Ressourcen-Moderatoren (R-P2-5, klein 4).

    `get_konten_liste` verlangt „Mitgliederadministrator“. Ein reiner
    KALENDERadministrator (ohne diese Rolle) konnte damit in der
    Kalender-Verwaltung keinen Moderator auswaehlen. Dieser Endpunkt liefert
    nur das, was die Auswahl braucht — Kennung und Anzeigename, KEINE Rollen —
    und verlangt nur eine der Verwaltungsrollen, die Moderatoren ueberhaupt
    pflegen duerfen.

    N12b (R-N12, klein): `user` ist `User.name` und damit in dieser
    Installation die E-Mail-ADRESSE — die Zusage „keine E-Mail“ stimmt nur
    formal. Die Auswahl ist trotzdem auf Verwaltungskonten beschraenkt, und
    DEAKTIVIERTE Konten werden nicht mehr angeboten: fuer die Auswahl eines
    Moderators sind sie ohne Nutzen, ihr Anzeigename waere aber eine
    Personenauskunft ohne Anlass. Fehlt `full_name`, bleibt als Anzeigename
    der Kontoname (die Adresse) stehen — dokumentiert, nicht versteckt.
    """
    user = str(session.user or "").strip()
    if not user or user == "Guest":
        throw("Anmeldung verweigert.", FrappePermissionError)
    from diakronos_app.frappe_compat.permissions import get_roles

    rollen = set(get_roles(user))
    if not rollen & {"System Manager", "Mitgliederadministrator",
                     "Kalenderadministrator", "Ressourcenmoderator"}:
        throw("Nur Verwaltungskonten dürfen Moderatoren auswählen.", FrappePermissionError)

    zeilen = get_all(
        "User",
        fields=["name", "full_name", "enabled"],
        order_by="full_name asc",
    ) or []
    # AUSTRITT-d (NM2): Hier stehen auch NICHT-Admins (Kalenderadministrator,
    # Ressourcenmoderator). Fuer sie gilt die Kuerzung — aber nur beim Austritt
    # (`ist_ausgeschieden`), nicht beim Ausschluss (N3) — und auch dann nur,
    # wenn sie die Person nicht selbst sind (``darf_vollstaendig``).
    from diakronos_app.frappe_compat.personen_anzeige import PersonenSicht

    sicht = PersonenSicht.aus()
    mitglieder, alle_konten = benutzer_status._kontozustand()
    mitglied_je_konto = {
        str(k): str(m.get("name") or "")
        for m in mitglieder
        for k in benutzer_status.wirksame_konten(
            m, _mitglieder=mitglieder, _konten=alle_konten)
        if m.get("name")
    }
    ausgetreten = benutzer_status.ausgetretene_konten(mitglieder, alle_konten)
    konten = []
    for roh in zeilen:
        z = dict(roh)
        name = str(z.get("name") or "").strip()
        if not name:
            continue
        # N12b: deaktivierte Konten gar nicht erst anbieten (siehe Docstring).
        if not bool(z.get("enabled", True)):
            continue
        kuerzen = name in ausgetreten and not sicht.darf_vollstaendig(
            mitglied_je_konto.get(name))
        konten.append({
            "user": name,
            "name": _konto_name(z.get("full_name"), name, ausgeschieden=kuerzen),
            "aktiv": True,
        })
    return {"success": True, "konten": konten}
