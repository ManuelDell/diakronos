"""Admin-Endpunkte fuer die Anmeldeeinstellungen (SEC1, TEIL A3).

Diese Endpunkte verwalten das Verhalten fuer UNBEKANNTE Nutzer sowie die
Zuordnung Authentik-Gruppe -> Diakronos-Rolle. Sie liegen in der DB (nicht in
der .env), damit sie in der Oberflaeche pflegbar sind.

Sicherheit:
  * ALLE Endpunkte sind **nur fuer Administratoren** (`_require_admin`).
  * Die Administrator-Rolle NIE automatisch ueber Gruppen, ausser der Schalter
    ``admin_ueber_gruppen`` ist ausdruecklich an — die Oberflaeche zeigt dann
    einen Warnhinweis.
  * Unbekannte Modi werden abgewiesen (nur die drei bekannten Werte).
"""

from __future__ import annotations

FRAPPE_MODULE = "diakronos.anmeldung"

import logging
from typing import Any

from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import PermissionError, ValidationError
from diakronos_app.models.auth_oidc import (
    ANMELDEEINSTELLUNGEN_NAME,
    UNBEKANNT_MODI,
    Anmeldeeinstellungen,
    GruppenRolleZuordnung,
)

logger = logging.getLogger("diakronos_app.anmeldung.einstellungen")

__all__ = [
    "anmeldung_get_einstellungen",
    "anmeldung_speichern",
    "anmeldung_get_rollen",
    "anmeldung_setze_unbekannte_nutzer",
    "anmeldung_setze_rollen_zuordnung",
]

# Rollen, die in der Gruppen->Rollen-Zuordnung waehlbar sind, WENN die
# Datenbank (Tabelle `role`) keine eigenen Zeilen fuehrt (Befund 5, P0-4b).
# Vorher stand die Liste fest in `Anmeldung.vue` — und lief damit
# zwangslaeufig auseinander: "System Manager" fehlte, "Kalenderadministrator"
# wirkte wie ein Tippfehler. Die Liste gehoert zur Anwendung, nicht in die
# Oberflaeche.
#
# Die Namen sind mit dem Backend abgeglichen (Auswahl der Rollen, auf die sich
# Rechtepruefungen beziehen): `ADMIN_ROLES`, `IMPORT_ROLES`, `DESK_ROLES`.
#
# Sie ist nur der FALLBACK. Fuehrt die Installation echte `role`-Zeilen, haben
# die Vorrang (siehe `_rollen_aus_db`) — eine Gemeinde kann eigene Rollen
# ergaenzen, ohne dass die Oberflaeche sie verschluckt.
_BEKANNTE_ROLLEN = (
    "Mitglied",
    "Mitgliederadministrator",
    "Kalenderadministrator",
    "Ressourcenmoderator",
    "Tester",
)

# Rollen, die als Administrator gelten (aus `permissions.ADMIN_ROLES`) — hier
# nicht doppelt gepflegt, sondern EINMAL importiert. Eine zweite Kopie waere
# genau der Fehler, den Befund 5 beschreibt.
def _admin_rollen() -> tuple[str, ...]:
    from diakronos_app.frappe_compat.permissions import ADMIN_ROLES

    return tuple(ADMIN_ROLES)


def _rollen_aus_db(sess) -> list[str]:
    """Alle Rollen aus der `role`-Tabelle (falls die Installation eine fuehrt).

    Leere/dublettenfreie Namen, alphabetisch. Ist die Tabelle leer, greift der
    Fallback `_BEKANNTE_ROLLEN`.
    """
    from diakronos_app.models.core import Role

    namen = {
        str(r.name).strip()
        for r in sess.query(Role).all()
        if getattr(r, "name", None) and str(r.name).strip()
    }
    return sorted(namen)


def _rollen_liste(sess) -> list[str]:
    """Die waehlbaren Rollen fuer die Oberflaeche (Befund 5, P0-4b).

    Reihenfolge: Administrator-Rollen zuerst, dann die uebrigen — die fuer die
    Vergabe wichtigsten stehen dadurch oben. Grundlage sind die Rollen der
    Installation; ist die Tabelle leer, der dokumentierte Fallback.
    """
    aus_db = _rollen_aus_db(sess)
    basis = aus_db if aus_db else list(_BEKANNTE_ROLLEN)
    admin = set(_admin_rollen())
    # Administrator-Rollen immer anbieten, auch wenn die DB sie (noch) nicht
    # fuehrt — sonst waere "System Manager" nicht waehlbar.
    alle = list(dict.fromkeys([r for r in basis] + [r for r in _admin_rollen() if r not in basis]))
    return sorted(alle, key=lambda r: (r not in admin, r))


def _require_admin() -> str:
    """Stellt sicher, dass der Aufrufer Administrator ist. Gibt den Namen zurueck."""
    from diakronos_app.frappe_compat import permissions
    from diakronos_app.frappe_compat.session import session

    user = session.user
    if not user or user == "Guest":
        raise PermissionError("Anmeldung verweigert.")
    if not permissions.is_admin(user):
        raise PermissionError("Nur Administratoren duerfen die Anmeldung einstellen.")
    return user


def _hole_oder_erzeuge(sess) -> Anmeldeeinstellungen:
    """Liest die Single-Zeile; legt sie mit sicheren Defaults an, falls noetig."""
    from datetime import datetime

    zeile = sess.get(Anmeldeeinstellungen, ANMELDEEINSTELLUNGEN_NAME)
    if zeile is None:
        zeile = Anmeldeeinstellungen(
            name=ANMELDEEINSTELLUNGEN_NAME,
            unbekannte_nutzer="abweisen",
            admin_ueber_gruppen=False,
            aktiv=False,
            created=datetime.now(),
        )
        sess.add(zeile)
        sess.flush()
    return zeile


@whitelist()
def anmeldung_get_einstellungen() -> dict[str, Any]:
    """Liefert die Anmeldeeinstellungen (Admin)."""
    from diakronos_app.db import SessionLocal

    _require_admin()
    sess = SessionLocal()
    try:
        zeile = _hole_oder_erzeuge(sess)
        zuordnungen = (
            sess.query(GruppenRolleZuordnung)
            .filter(GruppenRolleZuordnung.parent == ANMELDEEINSTELLUNGEN_NAME)
            .order_by(GruppenRolleZuordnung.idx)
            .all()
        )
        from diakronos_app.anmeldung.konfiguration import oidc_aktiv

        return {
            "unbekannte_nutzer": zeile.unbekannte_nutzer or "abweisen",
            "admin_ueber_gruppen": bool(zeile.admin_ueber_gruppen),
            "oidc_aktiv": oidc_aktiv(),
            "modi": list(UNBEKANNT_MODI),
            # Befund 5 (P0-4b): die waehlbaren Rollen kommen vom Server, nicht
            # mehr aus einer festen Liste in der Oberflaeche.
            "rollen": _rollen_liste(sess),
            "rollen_zuordnung": [
                {"gruppe": z.gruppe, "rolle": z.rolle, "idx": z.idx} for z in zuordnungen
            ],
        }
    finally:
        sess.rollback()  # ein beim Lesen angelegter Default soll nicht kleben
        sess.close()


@whitelist()
def anmeldung_get_rollen() -> dict[str, Any]:
    """Die waehlbaren Diakronos-Rollen (Admin, Befund 5/P0-4b).

    Eigener Endpunkt, damit die Oberflaeche die Rollenliste unabhaengig von
    den uebrigen Einstellungen nachladen kann (und der Vertrag klar ist).
    """
    from diakronos_app.db import SessionLocal

    _require_admin()
    sess = SessionLocal()
    try:
        return {"rollen": _rollen_liste(sess)}
    finally:
        sess.close()


def _pruefe_admin_gruppen(sess, schalter, zuordnungen, modus=None):
    """Gruppen duerfen kein Umweg um die Konten-/Rollenrechte sein.

    R-N8 (Punkt 3): der Modus „unbekannte Nutzer anlegen“ legen Konten mit den
    Rollen aus den Gruppen an — das ist ein Zugangsweg wie „Admin ueber
    Gruppen“ und deshalb ebenfalls nur fuer System Manager. Ebenso darf ein
    Mitgliederadministrator einen bereits gespeicherten „anlegen“-Modus nicht
    stillschweigend umstellen.
    """
    from diakronos_app.api.zugang import _require_system_manager
    from diakronos_app.models.auth_oidc import UNBEKANNT_ANLEGEN

    if schalter or any(z.get("rolle") in _admin_rollen() for z in zuordnungen):
        _require_system_manager()
    if modus == UNBEKANNT_ANLEGEN:
        _require_system_manager()
    bestand = sess.query(GruppenRolleZuordnung).filter(
        GruppenRolleZuordnung.parent == ANMELDEEINSTELLUNGEN_NAME).all()
    zeile = sess.get(Anmeldeeinstellungen, ANMELDEEINSTELLUNGEN_NAME)
    if (zeile and zeile.admin_ueber_gruppen) or any(z.rolle in _admin_rollen() for z in bestand):
        _require_system_manager()
    # R-N8 (Punkt 3): ist der „anlegen“-Modus gespeichert, darf ihn nur ein
    # System Manager aendern (sonst koennte ein Mitgliederadministrator den
    # Zugangsweg heimlich abschalten oder weiter oeffnen).
    if zeile is not None and zeile.unbekannte_nutzer == UNBEKANNT_ANLEGEN:
        _require_system_manager()


def _pruefe_zuordnungen(sess, zuordnungen):
    import json
    if isinstance(zuordnungen, str):
        try:
            zuordnungen = json.loads(zuordnungen)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Zuordnungen sind kein gültiges JSON.") from exc
    if not isinstance(zuordnungen, list):
        raise ValidationError("Zuordnungen müssen eine Liste sein.")
    erlaubt = set(_rollen_liste(sess))
    ergebnis = []
    gesehen = set()
    for idx, z in enumerate(zuordnungen, 1):
        if not isinstance(z, dict):
            raise ValidationError(f"Zeile {idx}: Gruppe und Rolle angeben.")
        gruppe, rolle = str(z.get("gruppe") or "").strip(), str(z.get("rolle") or "").strip()
        if not gruppe or not rolle:
            raise ValidationError(f"Zeile {idx}: Gruppe und Rolle sind Pflichtfelder.")
        if len(gruppe) > 255 or rolle not in erlaubt:
            raise ValidationError(f"Zeile {idx}: Gruppe zu lang oder unbekannte Rolle.")
        if (gruppe, rolle) in gesehen:
            raise ValidationError(f"Zeile {idx}: Diese Zuordnung ist doppelt vorhanden.")
        gesehen.add((gruppe, rolle))
        ergebnis.append({"gruppe": gruppe, "rolle": rolle})
    return ergebnis


@whitelist()
def anmeldung_speichern(modus: str, admin_ueber_gruppen: bool = False,
                        zuordnungen: Any = None, request=None) -> dict:
    """N8: Modus, Sicherheitsschalter und Rollen in EINER Transaktion speichern."""
    from datetime import datetime
    from diakronos_app.db import SessionLocal
    benutzer = _require_admin()
    if request is not None and request.method != "POST":
        raise ValidationError("Speichern ist nur per POST erlaubt.")
    if modus not in UNBEKANNT_MODI or not isinstance(admin_ueber_gruppen, bool):
        raise ValidationError("Bitte einen gültigen Modus und einen Ja/Nein-Schalter angeben.")
    with SessionLocal() as sess:
        zeilen = _pruefe_zuordnungen(sess, [] if zuordnungen is None else zuordnungen)
        _pruefe_admin_gruppen(sess, admin_ueber_gruppen, zeilen, modus)
        zeile = _hole_oder_erzeuge(sess)
        zeile.unbekannte_nutzer = modus
        zeile.admin_ueber_gruppen = admin_ueber_gruppen
        zeile.modified = datetime.now()
        zeile.created_by = zeile.created_by or benutzer
        sess.query(GruppenRolleZuordnung).filter(
            GruppenRolleZuordnung.parent == ANMELDEEINSTELLUNGEN_NAME).delete(synchronize_session=False)
        for idx, z in enumerate(zeilen, 1):
            sess.add(GruppenRolleZuordnung(parent=ANMELDEEINSTELLUNGEN_NAME,
                parenttype="Anmeldeeinstellungen", parentfield="rollen_zuordnung",
                idx=idx, **z, created=datetime.now(), modified_by=benutzer))
        sess.commit()
    return {"gespeichert": True}


@whitelist()
def anmeldung_setze_unbekannte_nutzer(modus: str, admin_ueber_gruppen: bool = False) -> dict:
    """Setzt das Verhalten fuer unbekannte Nutzer (Admin)."""
    from datetime import datetime

    from diakronos_app.db import SessionLocal

    benutzer = _require_admin()
    wert = str(modus or "").strip()
    if wert not in UNBEKANNT_MODI:
        raise ValidationError("Unbekannter Modus: " + wert)
    # bool kann als String/JSON kommen.
    admin_schalter = admin_ueber_gruppen
    if isinstance(admin_schalter, str):
        admin_schalter = admin_schalter.strip().lower() in ("true", "1", "yes")

    sess = SessionLocal()
    try:
        _pruefe_admin_gruppen(sess, bool(admin_schalter), [], wert)
        zeile = _hole_oder_erzeuge(sess)
        zeile.unbekannte_nutzer = wert
        zeile.admin_ueber_gruppen = bool(admin_schalter)
        zeile.modified = datetime.now()
        zeile.created_by = zeile.created_by or benutzer
        sess.commit()
        logger.info("Anmeldeeinstellungen geaendert (Modus=%s).", wert)
        return {
            "unbekannte_nutzer": zeile.unbekannte_nutzer,
            "admin_ueber_gruppen": bool(zeile.admin_ueber_gruppen),
        }
    finally:
        sess.close()


@whitelist()
def anmeldung_setze_rollen_zuordnung(zuordnungen: Any = None) -> dict:
    """Ersetzt die Gruppen->Rollen-Zuordnung (Admin).

    ``zuordnungen`` ist eine Liste von ``{"gruppe": ..., "rolle": ...}``. Die
    Liste wird vollstaendig ersetzt (Loeschen und Neuanlegen), damit die
    Oberflaeche keinen Diff bilden muss.
    """
    from datetime import datetime

    from diakronos_app.db import SessionLocal

    benutzer = _require_admin()
    if zuordnungen is None:
        zuordnungen = []
    if isinstance(zuordnungen, str):
        import json

        try:
            zuordnungen = json.loads(zuordnungen)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Zuordnungen sind kein gueltiges JSON.") from exc
    if not isinstance(zuordnungen, list):
        raise ValidationError("Zuordnungen muessen eine Liste sein.")

    sess = SessionLocal()
    try:
        _pruefe_admin_gruppen(sess, False, [z for z in zuordnungen if isinstance(z, dict)])
        _hole_oder_erzeuge(sess)
        sess.query(GruppenRolleZuordnung).filter(
            GruppenRolleZuordnung.parent == ANMELDEEINSTELLUNGEN_NAME
        ).delete(synchronize_session=False)
        idx = 0
        for eintrag in zuordnungen:
            if not isinstance(eintrag, dict):
                raise ValidationError("Jeder Eintrag muss ein Objekt sein.")
            gruppe = str(eintrag.get("gruppe") or "").strip()
            rolle = str(eintrag.get("rolle") or "").strip()
            if not gruppe or not rolle:
                raise ValidationError("Gruppe und Rolle sind Pflichtfelder.")
            idx += 1
            sess.add(
                GruppenRolleZuordnung(
                    parent=ANMELDEEINSTELLUNGEN_NAME,
                    parenttype="Anmeldeeinstellungen",
                    parentfield="rollen_zuordnung",
                    idx=idx,
                    gruppe=gruppe,
                    rolle=rolle,
                    created=datetime.now(),
                    modified_by=benutzer,
                )
            )
        sess.commit()
        logger.info("Gruppen->Rollen-Zuordnung ersetzt (%d Eintraege).", idx)
        return {"anzahl": idx}
    finally:
        sess.close()
