"""Konto-Zuordnung (SEC1, TEIL A3 + TEIL B).

Aus einem externen Konto (OIDC-Ansprueche oder Forward-Auth-Kopfzeilen) wird ein
Diakronos-Benutzer. Die Regeln sind fuer beide Wege DIESELBEN — es gibt keine
zweite Wahrheit:

  * **Stabil ueber ``(issuer, sub)``.** Nur so bleibt die Zuordnung bestehen,
    wenn sich die E-Mail aendert. Der erste Treffer in `auth_oidc_identitaet`
    gewinnt.
  * **Erstzuordnung ueber E-Mail NUR wenn ``email_verified=true``.** Eine
    unverifizierte E-Mail ist ein Behauptung, kein Beweis — sie darf nie ein
    bestehendes Konto uebernehmen (sonst waere eine gefaelschte E-Mail ein
    Kontodiebstahl).
  * **Unbekannte Nutzer** werden nach der DB-Einstellung behandelt (Default
    sicher = ``abweisen``): abweisen | als Gast anlegen | anlegen + Rollen aus
    Gruppen.
  * **Gesperrte/deaktivierte Diakronos-Nutzer bleiben gesperrt.** Das Ergebnis
    traegt das mit; der Aufrufer setzt keine Sitzung fuer ein inaktives Konto.
  * **Administrator-Rolle NIE automatisch ueber Gruppen**, ausser die
    Einstellung erlaubt es ausdruecklich.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from diakronos_app.models.auth_oidc import (
    ANMELDEEINSTELLUNGEN_NAME,
    UNBEKANNT_ABWEISEN,
    UNBEKANNT_ANLEGEN,
    UNBEKANNT_GAST,
    Anmeldeeinstellungen,
    GruppenRolleZuordnung,
    OidcIdentitaet,
)

logger = logging.getLogger("diakronos_app.anmeldung.zuordnung")

__all__ = [
    "ExternesKonto",
    "ZuordnungsErgebnis",
    "loese_konto_auf",
    "AnmeldeEinstellungen",
    "hole_einstellungen",
    "merke_ablehnung",
    "merke_ablehnung_separat",
]

# Rollen, die ueber Gruppen NIEMALS ohne ausdruecklichen Schalter vergeben
# werden. Die Liste kommt aus EINER Quelle (der Compat-Schicht).
from diakronos_app.frappe_compat.permissions import ADMIN_ROLES as _ADMIN_ROLES


@dataclass(frozen=True)
class ExternesKonto:
    """Normalisiertes Konto aus OIDC oder Forward-Auth.

    ``quelle`` ist ``oidc`` oder ``proxy_header`` — nur fuer die Diagnose, nicht
    fuer die Zuordnung (die haengt an ``issuer``/``sub``).
    """

    issuer: str
    sub: str
    email: str = ""
    email_verified: bool = False
    name: str = ""
    gruppen: tuple[str, ...] = ()
    quelle: str = "oidc"


@dataclass
class ZuordnungsErgebnis:
    """Ergebnis der Zuordnung: entweder ein Benutzer oder eine Ablehnung."""

    erlaubt: bool
    user: str | None = None
    neu_angelegt: bool = False
    als_gast: bool = False
    grund: str = ""
    meldung: str = ""
    gruppen_rollen: list[str] = field(default_factory=list)


class AnmeldeEinstellungen:
    """Zugriff auf die DB-Einstellungen (Single-Zeile der Anmeldung)."""

    def __init__(self, unbekannte_nutzer: str, admin_ueber_gruppen: bool,
                 zuordnungen: list[GruppenRolleZuordnung]):
        self.unbekannte_nutzer = unbekannte_nutzer
        self.admin_ueber_gruppen = admin_ueber_gruppen
        self.zuordnungen = zuordnungen

    def rollen_fuer_gruppen(self, gruppen: tuple[str, ...]) -> list[str]:
        """Diakronos-Rollen zu den uebergebenen Gruppen.

        Die Administrator-Rolle wird nur zurueckgegeben, wenn
        ``admin_ueber_gruppen`` ausdruecklich an ist.
        """
        gewuenscht = set(gruppen)
        rollen: list[str] = []
        for z in self.zuordnungen:
            if z.gruppe in gewuenscht and z.rolle not in rollen:
                rollen.append(z.rolle)
        if not self.admin_ueber_gruppen:
            rollen = [r for r in rollen if r not in _ADMIN_ROLES]
        return rollen


def hole_einstellungen(sess) -> AnmeldeEinstellungen:
    """Liest die Anmeldeeinstellungen aus der DB.

    Fehlt die Zeile (Neuanlage/Altbestand), gilt der SICHERE Default:
    unbekannte Nutzer werden abgewiesen, Admin nie ueber Gruppen.
    """
    zeile = sess.get(Anmeldeeinstellungen, ANMELDEEINSTELLUNGEN_NAME)
    if zeile is None:
        return AnmeldeEinstellungen(UNBEKANNT_ABWEISEN, False, [])
    zuordnungen = (
        sess.query(GruppenRolleZuordnung)
        .filter(GruppenRolleZuordnung.parent == ANMELDEEINSTELLUNGEN_NAME)
        .order_by(GruppenRolleZuordnung.idx)
        .all()
    )
    modus = zeile.unbekannte_nutzer or UNBEKANNT_ABWEISEN
    if modus not in (UNBEKANNT_ABWEISEN, UNBEKANNT_GAST, UNBEKANNT_ANLEGEN):
        # Unbekannter Wert in der DB -> fail safe wie "nicht konfiguriert".
        modus = UNBEKANNT_ABWEISEN
    return AnmeldeEinstellungen(modus, bool(zeile.admin_ueber_gruppen), zuordnungen)


def _user_mit_email(sess, email: str):
    """Findet einen Benutzer ueber die E-Mail (case-insensitiv)."""
    from diakronos_app.models.core import User

    if not email:
        return None
    return (
        sess.query(User)
        .filter(func_lower_eq(User.email, email))
        .one_or_none()
    )


def func_lower_eq(spalte, wert: str):
    """Vergleich ``lower(spalte) == lower(wert)`` ohne Funktionsexplosion."""
    from sqlalchemy import func

    return func.lower(spalte) == wert.strip().lower()


def _erzeuge_benutzer(sess, konto: ExternesKonto, *, als_gast: bool) -> str:
    """Legt einen Diakronos-Benutzer an und gibt dessen Namen zurueck.

    Der Name ist die E-Mail, wenn vorhanden (Frappe-Konvention), sonst ein aus
    Issuer/Sub abgeleiteter stabiler Bezeichner. ``user_type`` ist ``Website
    User`` fuer Gaeste (Moderationsweg) bzw. ``System User`` fuer die
    automatische Anlage.
    """
    import uuid

    from diakronos_app.models.core import User

    email = (konto.email or "").strip()
    name = email or f"oidc-{uuid.uuid4().hex[:16]}"
    vorhanden = sess.get(User, name)
    if vorhanden is not None:
        # Name schon belegt (z. B. Benutzer ohne Passwort): wir uebernehmen ihn
        # NICHT automatisch, sondern haengen einen stabilen Suffix an.
        name = f"{name}+{konto.quelle}-{konto.sub[:8]}" if konto.sub else f"{name}+x"
    user = User(
        name=name,
        email=email or None,
        full_name=(konto.name or email or name),
        enabled=not als_gast,  # Gast-Konten sind bis zur Freischaltung inaktiv
        user_type="Website User" if als_gast else "System User",
    )
    sess.add(user)
    sess.flush()
    return name


def _setze_rollen(sess, user: str, rollen: list[str]) -> None:
    """Setzt die Rollen eines Benutzers in `Has Role` (idempotent).

    Nur die hier genannten Rollen werden ergaenzt; bestehende Rollen bleiben
    erhalten (der Sync entfernt keine manuell vergebenen Rollen). Die
    Administrator-Rolle ist hier nie dabei, wenn der Schalter aus ist (siehe
    `AnmeldeEinstellungen.rollen_fuer_gruppen`).
    """
    import uuid

    from diakronos_app.models.core import HasRole

    if not rollen:
        return
    vorhandene = {
        r.role
        for r in sess.query(HasRole).filter(HasRole.parent == user).all()
        if r.role
    }
    idx = len(vorhandene)
    for rolle in rollen:
        if rolle in vorhandene:
            continue
        idx += 1
        sess.add(
            HasRole(
                name=str(uuid.uuid4()),
                parent=user,
                parenttype="User",
                parentfield="roles",
                idx=idx,
                role=rolle,
            )
        )


def _mitglied_fuer_email(sess, konto):
    """Erstverknüpfung nur mit eindeutigem, verifiziertem Eigentumsnachweis."""
    from diakronos_app.models.diakonos import Mitglied
    if not konto.email:
        return None
    treffer = sess.query(Mitglied).filter(func_lower_eq(Mitglied.email, konto.email)).all()
    if not treffer:
        return None
    if konto.email_verified is not True or len(treffer) != 1 or treffer[0].ausgeschlossen:
        raise ValueError("Die Mitglied-Zuordnung muss von der Gemeindeleitung geprüft werden.")
    return treffer[0]


def _rollen_fuer_mitglied(mitglied) -> list[str]:
    """Diakronos-Rolle aus dem Mitgliedsstatus ableiten (R-N8; N10/M-2).

    Vorher bekam jede neu verknuepfte Person die Rolle ``Mitglied`` — auch
    ein Gast oder passives Mitglied. Die Rolle entscheidet ueber die Rechte;
    sie muss deshalb zum Status passen:

      * ``Mitglied``          -> ``Mitglied``
      * alle uebrigen Status  -> KEINE Diakronos-Rolle

    M-2 (R-N9b): Frueher wurde hier die Rolle ``Gast`` vergeben. Die gibt es
    aber nicht: sie steht in keiner Rollenliste (``ZUGANGS_ROLLEN``/
    ``_BEKANNTE_ROLLEN``), an sie ist KEINE Rechtepruefung gebunden (die
    Rechte laufen ueber ``Mitglied.status``), sie erscheint in keiner
    Rollenverwaltung und wurde beim spaeteren Statuswechsel nicht
    nachgezogen. Eine Rolle, die niemand kennt und die nichts bewirkt, ist
    eine Falle — deshalb sauber entfernt: ein Nicht-Mitglied traegt einfach
    keine Diakronos-Rolle. Wer spaeter Mitglied wird, bekommt beim naechsten
    Zuordnungsvorgang die Rolle ``Mitglied`` (derselbe Weg, kein Sonderweg).

    Der Status ist ein Freitext aus ``MITGLIED_STATUS``; ein unbekannter Wert
    traegt damit ebenfalls keine Rolle (die schwaechere Variante — fail safe).
    """
    status = str(getattr(mitglied, "status", "") or "").strip()
    return ["Mitglied"] if status == "Mitglied" else []


def _verbinde_mitglied(sess, mitglied, user):
    from diakronos_app.models.diakonos import Mitglied
    if mitglied is None:
        return
    if mitglied.user and mitglied.user != user:
        raise ValueError("Das Mitglied ist bereits mit einem anderen Konto verbunden.")
    andere = sess.query(Mitglied).filter(Mitglied.user == user, Mitglied.name != mitglied.name).first()
    if andere:
        raise ValueError("Das Konto ist bereits einem anderen Mitglied zugeordnet.")
    mitglied.user = user


def loese_konto_auf(sess, konto: ExternesKonto) -> ZuordnungsErgebnis:
    """Ordnet ein externes Konto einem Diakronos-Benutzer zu (oder lehnt ab).

    ``sess`` ist eine SQLAlchemy-Session; der Aufrufer committet. Diese Funktion
    fuehrt die Regeln oben durch und aendert ausserhalb der Zuordnungstabelle
    nur die `user`-/`has_role`-Tabellen.
    """
    from diakronos_app.frappe_compat import benutzer_status
    from diakronos_app.models.core import User

    einstellungen = hole_einstellungen(sess)

    # 1. Stabile Zuordnung ueber (issuer, sub).
    treffer = (
        sess.query(OidcIdentitaet)
        .filter(
            OidcIdentitaet.issuer == konto.issuer,
            OidcIdentitaet.sub == konto.sub,
        )
        .one_or_none()
    )
    if treffer is not None:
        benutzer = sess.get(User, treffer.user)
        if benutzer is None:
            # Zuordnung zeigt ins Leere (sollte durch CASCADE nicht vorkommen).
            sess.delete(treffer)
            sess.flush()
        else:
            treffer.email = konto.email or treffer.email
            treffer.zuletzt_gesehen = datetime.now()
            treffer.modified = datetime.now()
            if not benutzer_status.ist_aktiv(benutzer.name):
                return ZuordnungsErgebnis(
                    erlaubt=False,
                    grund="konto_gesperrt",
                    meldung="Dieses Konto ist gesperrt. Bitte wende dich an die "
                    "Gemeindeleitung.",
                )
            rollen = einstellungen.rollen_fuer_gruppen(konto.gruppen)
            _setze_rollen(sess, benutzer.name, rollen)
            return ZuordnungsErgebnis(erlaubt=True, user=benutzer.name,
                                      gruppen_rollen=rollen)

    # 2. Erstzuordnung ueber E-Mail — NUR wenn verifiziert. Auch Personen
    # ohne lokales Konto koennen vom Admin bereits eingetragen worden sein.
    try:
        mitglied = _mitglied_fuer_email(sess, konto)
    except ValueError as exc:
        return ZuordnungsErgebnis(erlaubt=False, grund="mitglied_zuordnung", meldung=str(exc))
    if konto.email and konto.email_verified is True:
        benutzer = _user_mit_email(sess, konto.email)
        neu = None
        if benutzer is None and mitglied is not None:
            neu = _erzeuge_benutzer(sess, konto, als_gast=False)
            benutzer = sess.get(User, neu)
            # R-N8: Rolle aus dem Mitgliedsstatus ableiten, nicht pauschal
            # "Mitglied" — ein Gast bleibt Gast.
            _setze_rollen(sess, neu, _rollen_fuer_mitglied(mitglied))
        if benutzer is not None:
            if not neu and not benutzer_status.ist_aktiv(benutzer.name):
                return ZuordnungsErgebnis(
                    erlaubt=False,
                    grund="konto_gesperrt",
                    meldung="Dieses Konto ist gesperrt. Bitte wende dich an die "
                    "Gemeindeleitung.",
                )
            try:
                _verbinde_mitglied(sess, mitglied, benutzer.name)
            except ValueError as exc:
                return ZuordnungsErgebnis(erlaubt=False, grund="mitglied_zuordnung", meldung=str(exc))
            _verknuepfe(sess, konto, benutzer.name)
            rollen = einstellungen.rollen_fuer_gruppen(konto.gruppen)
            _setze_rollen(sess, benutzer.name, rollen)
            return ZuordnungsErgebnis(erlaubt=True, user=benutzer.name,
                                      gruppen_rollen=rollen)

    # 3. Unbekannter Nutzer — Verhalten aus der Einstellung.
    modus = einstellungen.unbekannte_nutzer
    if modus == UNBEKANNT_ABWEISEN:
        return ZuordnungsErgebnis(
            erlaubt=False,
            grund="unbekannt_abgewiesen",
            meldung="Fuer dieses Konto gibt es keinen Zugang. Die Gemeindeleitung "
            "kann dich freischalten.",
        )

    if modus == UNBEKANNT_GAST:
        neu = _erzeuge_benutzer(sess, konto, als_gast=True)
        _verknuepfe(sess, konto, neu)
        return ZuordnungsErgebnis(
            erlaubt=True,
            user=neu,
            neu_angelegt=True,
            als_gast=True,
            meldung="Dein Konto wurde angelegt und wartet auf Freischaltung.",
        )

    # modus == UNBEKANNT_ANLEGEN: anlegen + Rollen aus Gruppen.
    neu = _erzeuge_benutzer(sess, konto, als_gast=False)
    _verknuepfe(sess, konto, neu)
    rollen = einstellungen.rollen_fuer_gruppen(konto.gruppen)
    _setze_rollen(sess, neu, rollen)
    return ZuordnungsErgebnis(erlaubt=True, user=neu, neu_angelegt=True,
                              gruppen_rollen=rollen)


def _verknuepfe(sess, konto: ExternesKonto, user: str) -> None:
    """Legt die Zuordnung ``(issuer, sub) -> user`` an."""
    sess.add(
        OidcIdentitaet(
            issuer=konto.issuer,
            sub=konto.sub,
            user=user,
            email=konto.email or None,
            zuletzt_gesehen=datetime.now(),
            created_by="system",
        )
    )
    sess.flush()


def merke_ablehnung(sess, konto: ExternesKonto, ergebnis: ZuordnungsErgebnis) -> None:
    """Haelt eine abgelehnte E-Mail-Zuordnung fuer die Verwaltung fest (R-N8).

    Nur der Fall ``mitglied_zuordnung`` (Treffer auf eine Person, aber nicht
    eindeutig/verifiziert/freigegeben) ist fuer die Verwaltung relevant — ein
    gesperrtes Konto oder ein abgewiesener Unbekannter braucht keine Zeile.
    Upsert ueber ``(issuer, sub)``: wiederholte Anmeldungen erzeugen keine
    neuen Zeilen, nur ``versuche``/``zuletzt`` wachsen. Der Aufrufer committet.
    """
    if ergebnis.grund != "mitglied_zuordnung":
        return
    from diakronos_app.models.auth_oidc import ZuordnungsAblehnung

    jetzt = datetime.now()
    zeile = (
        sess.query(ZuordnungsAblehnung)
        .filter(
            ZuordnungsAblehnung.issuer == konto.issuer,
            ZuordnungsAblehnung.sub == konto.sub,
        )
        .one_or_none()
    )
    if zeile is None:
        sess.add(
            ZuordnungsAblehnung(
                issuer=konto.issuer,
                sub=konto.sub,
                email=konto.email or None,
                name_anzeige=konto.name or None,
                grund=ergebnis.grund,
                meldung=ergebnis.meldung or None,
                versuche=1,
                zuletzt=jetzt,
                created=jetzt,
            )
        )
    else:
        zeile.email = konto.email or zeile.email
        zeile.name_anzeige = konto.name or zeile.name_anzeige
        zeile.meldung = ergebnis.meldung or zeile.meldung
        zeile.versuche = int(zeile.versuche or 0) + 1
        zeile.zuletzt = jetzt
    sess.flush()


def merke_ablehnung_separat(konto: ExternesKonto, ergebnis: ZuordnungsErgebnis) -> None:
    """Wie ``merke_ablehnung``, aber in EIGENER Transaktion (R-N8).

    Der Anmelde-Pfad rollt seine Transaktion bei einer Ablehnung zurueck.
    Damit die Notiz an die Verwaltung dabei nicht verloren geht, oeffnet diese
    Funktion eine eigene Sitzung. Fehler bleiben still — die Ablehnung selbst
    darf an einer misslungenen Notiz nicht scheitern.
    """
    if ergebnis.grund != "mitglied_zuordnung":
        return
    try:
        from diakronos_app.db import SessionLocal

        with SessionLocal() as sess:
            merke_ablehnung(sess, konto, ergebnis)
            sess.commit()
    except Exception:  # noqa: BLE001 — die Ablehnung darf nicht scheitern
        logger.warning("Abgelehnte Zuordnung konnte nicht vermerkt werden.")
