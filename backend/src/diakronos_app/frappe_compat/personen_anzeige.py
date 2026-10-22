"""Gekuerzte Anzeige ausgetretener Personen (AUSTRITT A3/A4, DSGVO-2d).

DIE FRAGE
---------
Wer die Gemeinde verlaesst, verschwindet nicht aus der Geschichte: er stand im
Chorplan, im Dienstplan, in der Gruppe. Diese Plaene bleiben lesbar, sonst
waere die Vergangenheit verfaelscht. Aber die Person soll dort nicht mehr mit
Klarnamen, E-Mail und Telefonnummer jedem Planleser entgegenstehen — nur noch
gekuerzt: ``Elvira D.`` und eine maskierte Adresse.

GELOESCHTE PERSON (DSGVO-2d)
----------------------------
Die Loeschung auf Antrag (``dsgvo_anonymisierung``) setzt ``status`` =
``geloescht`` und vergibt die neutrale Kennung ``geloescht-<hex>``. Fuer sie
gilt hier EINE Regel an DIESER Stelle, damit kein Auslieferungsweg sie
einzeln nachbauen muss: angezeigt wird ``Gelöschte Person`` — nie die
Kennung, nie ein Klarname, nie leere Klammern. Ein Rest des alten Namens (etwa
nach einem wiederhergestellten alten Sicherungsstand) wird NICHT
durchgereicht: was als geloescht markiert ist, ist personenbezogen nicht mehr
lesbar. Die Laenge des gespeicherten Vornamens bleibt dabei unerheblich —
deshalb vergibt ``kuerze_name`` fuer solche Zeilen genau diesen Text statt
einer Kurzform.

DIE REGEL — EINE STELLE
-----------------------
``PersonenSicht.aus(mapping)`` entscheidet einmal, WIE eine Person aussieht,
und ``kuerze``/``kuerze_zeile``/``kuerze_dict`` setzen das auf Daten um. Jeder
Auslieferungsweg (Mitgliederliste, Gruppenvorschlaege, Personenpool des
Plan-Rahmens, Abwesenheiten) benutzt dieselbe Funktion; so gibt es keine
zweite Fassung, die auseinanderlaufen koennte.

Wer alles sieht: ``Mitgliederadministrator`` und ``System Manager`` (dieselbe
Rollenliste wie ``api/mitglieder.ADMIN_ROLES``) sowie die betroffene Person
selbst — das eigene Profil bleibt vollstaendig. Alle anderen bekommen die
Kurzform, in der **kein** Klarname, **keine** Klar-E-Mail und **keine**
weiteren Kontaktdaten mehr stehen: die Kuerzung passiert im Backend, das Feld
traegt danach wirklich nur noch die Kurzform (kein Frontend-Trick).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .permissions import ADMIN_ROLES, _has_admin_role
from .session import session
from ..email_belegung import normalisiere

#: So viele Zeichen der Adresse bleiben stehen (Fachentscheidung Manuel).
EMAIL_KLARZEICHEN = 3

#: Status, den ``api/austritt.STATUS_AUSGETRETEN`` beim Austritt setzt.
#: Hier als Zeichenkette, weil ``personen_anzeige`` in der Schicht unter
#: ``api/`` liegt und nicht auf sie zurueckgreifen darf.
STATUS_AUSGETRETEN = "Ausgetreten"

#: Endstatus der Loeschung auf Antrag (``dsgvo_anonymisierung._mitglied_werte``,
#: ``api_helpers._verweigere_geloeschtes_mitglied``). Aus demselben Grund eine
#: Zeichenkette — und aus demselben Grund steht sie hier EINMAL.
STATUS_GELOESCHT = "geloescht"

#: Anzeigetext einer geloeschten Person (DSGVO-2d) — an ALLEN Anzeigeorten
#: derselbe Satz. Bewusst ein Nomen mit Artikel-Freiheit: er passt in Listen,
#: Chips, Formatvorlagen und Fliestext.
GELOESCHT_ANZEIGE = "Gelöschte Person"

#: Praefix der neutralen Kennung einer geloeschten Person
#: (``dsgvo_anonymisierung.GELOESCHT_PRAEFIX``). Hier eine eigene Konstante,
#: weil diese Schicht nicht auf ``dsgvo_anonymisierung`` zeigen darf; ein
#: Test (``test_dsgvo2d_geloeschte_person``) haelt beide zusammen.
GELOESCHT_PRAEFIX = "geloescht-"

#: Felder, die bei einer ausgetretenen Person GAR NICHT mehr ausgeliefert
#: werden — Kontaktdaten und alles, was die Person identifizierbar macht.
#: AUSTRITT-b (B2): Auch die Merkmale des Austritts selbst stehen hier. Die
#: Begruendung kann eine Krankheit nennen; sie gehoert niemandem ausser der
#: Person und den Administratoren — auch nicht als Feld NEBEN dem
#: `austritt`-Block der Detailantwort.
#: AUSTRITT-c (M1): ebenso der gemerkte Kontozustand — er nennt Kontonamen
#: (= Adressen) und ist reine Verwaltungsinformation.
AUSGETRETEN_LEEREN = (
    "nachname", "full_name", "telefonnummer", "geburtstag", "postleitzahl",
    "wohnort", "straße", "nummer", "user", "notiz", "logo", "bild",
    "foto", "geschlecht", "familienstand", "ehepartner", "elternteil",
    "adressbuch_sichtbarkeit", "austritt_grund", "vor_austritt_status",
    "vor_austritt_konto_aktiv",
)


@dataclass(frozen=True)
class PersonenSicht:
    """Ob und wie eine ausgetretene Person gekuerzt ausgeliefert wird."""

    vollstaendig: bool
    eigenes_mitglied: str | None = None

    @classmethod
    def aus(cls, mitglied_daten: Mapping[str, Any] | None = None) -> "PersonenSicht":
        """Sicht des aktuellen Aufrufers.

        ``mitglied_daten`` ist der eigene Datensatz (``None``, wenn das Konto
        keinem Mitglied zugeordnet ist). Ein Verwaltungskonto sieht alles,
        unabhaengig von der eigenen Mitgliedszeile.
        """
        if _has_admin_role(session.user):
            return cls(vollstaendig=True)
        name = (mitglied_daten or {}).get("name")
        return cls(vollstaendig=False, eigenes_mitglied=str(name) if name else None)

    def darf_vollstaendig(self, mitglied_id: Any) -> bool:
        """Ist DIESE Zeile fuer den Aufrufer vollstaendig?"""
        if self.vollstaendig:
            return True
        return bool(mitglied_id) and str(mitglied_id) == self.eigenes_mitglied


def ist_geloescht(datensatz: Mapping[str, Any] | Any) -> bool:
    """Ist die Person GELOESCHT (Loeschung auf Antrag, Art. 17)?

    DSGVO-2d: Diese Frage entscheidet ueber den Anzeigetext ``Gelöschte
    Person``. Getragen wird sie vom ENDSTATUS ``status='geloescht'`` — den
    setzt nur ``dsgvo_anonymisierung``, und ``api_helpers`` verweigert danach
    jede Aenderung. Die neutrale Kennung ``geloescht-<hex>`` ist der zweite
    Zeuge: nach einem zurueckgespielten alten Sicherungsstand kann der Status
    fehlen, waehrend Verweise schon auf die neue Kennung zeigen.
    """
    kennung = datensatz.get("name", datensatz.get("mitglied", "")) \
        if isinstance(datensatz, Mapping) else datensatz
    return _ist_geloescht(str(kennung or ""), datensatz)


def _ist_geloescht(kennung: str, datensatz: Mapping[str, Any] | None = None) -> bool:
    """``ist_geloescht`` auf Kennung + optionaler Zeile (ein Praedikat, zwei Eingaben)."""
    if isinstance(datensatz, Mapping) and str(
            datensatz.get("status") or "").strip().casefold() == STATUS_GELOESCHT.casefold():
        return True
    return kennung.strip().casefold().startswith(GELOESCHT_PRAEFIX)


def ist_ausgeschieden(datensatz: Mapping[str, Any]) -> bool:
    """Ist die Person AUSGETRETEN? — die Frage, die die Kuerzung entscheidet.

    AUSTRITT-c (N3, Fachentscheidung Operator): Gekuerzt wird NUR der
    Austritt. Ein Ausschluss (``ausgeschlossen`` ohne Austrittsmerkmal, Status
    „Passiver Gast“) laesst die Person voll sichtbar — wie in ``main``; sonst
    faende ein Administrator den Weg zum Aufheben („Status im Profil ändern“)
    nicht mehr.

    Getragen wird die Frage vom Austrittsmerkmal, nicht von der Marke: Status
    „Ausgetreten“ ODER ein gesetztes ``austritt_datum`` — beides setzt nur
    ``api/austritt.mitglied_austritt``.

    Die ZUTEILBARKEIT ist davon getrennt und fragt weiter die Marke
    (``planrahmen/datenquelle_db.py``): Ausgetretene UND Ausgeschlossene sind
    niemandem mehr als Kandidat angeboten.

    DSGVO-2d: Eine GELOESCHTE Person ist nicht „ausgetreten“ im Sinne dieser
    Frage — sie hat mit ``GELOESCHT_ANZEIGE`` ihren eigenen Text und keine
    Kurzform (``ist_geloescht``).
    """
    if _ist_geloescht("", datensatz):
        return False
    if str(datensatz.get("status") or "").strip().casefold() == STATUS_AUSGETRETEN.casefold():
        return True
    return bool(datensatz.get("austritt_datum"))


def maskiere_email(wert: Any) -> str | None:
    """Erste drei Zeichen + Sterne + Endung; ohne Adresse ``None``.

    Das Muster aus der Fachentscheidung: ``elvira@example.de`` wird zu
    ``elv*******.de``. Die in der Karte genannte Form
    (``elv*******.de``) nennt keine Laenge, deshalb werden die maskierten
    Zeichen auf eine feste Zahl gesetzt: so verraet die Laenge der Adresse
    nichts. Adressen mit weniger als drei Zeichen vor dem ``@`` behalten
    nur, was da ist.
    """
    adresse = normalisiere(wert)
    if not adresse or "@" not in adresse:
        return None
    lokal, _, domain = adresse.rpartition("@")
    if not lokal:
        return None
    endung = domain.rsplit(".", 1)[-1] if "." in domain else domain
    return f"{lokal[:EMAIL_KLARZEICHEN]}{'*' * 7}.{endung}"


def kuerze_name(vorname: Any, nachname: Any, fallback: Any = "") -> str:
    """``Vorname N.`` — der Nachname bleibt ein Buchstabe (Fachentscheidung).

    DSGVO-2d: Traegt die Zeile eine geloeschte Person, ist die Antwort
    ``Gelöschte Person`` — unabhaengig davon, was (etwa in einem alten
    Sicherungsstand) noch in Vor-/Nachname steht. Die Frage wird hier gestellt
    und nicht bei den Aufrufern, weil ALLE Auslieferungswege durch diese
    Funktion laufen.
    """
    if _ist_geloescht(str(fallback or "").strip()):
        return GELOESCHT_ANZEIGE
    vor = str(vorname or "").strip()
    nach = str(nachname or "").strip()
    if vor and nach:
        return f"{vor} {nach[0].upper()}."
    if vor:
        return vor
    if nach:
        return f"{nach[0].upper()}."
    rest = str(fallback or "").strip()
    return rest[0].upper() + "." if rest else "Ehemaliges Mitglied"


def kuerze(datensatz: Mapping[str, Any], *, email_feld: str = "email") -> dict[str, Any]:
    """Kurzform eines Personendatensatzes (neues dict, Eingabe bleibt heil).

    `email_feld` nennt die Spalte mit der ADRESSE. Vorgabe ist `email`; die
    Mitgliederliste uebergibt stattdessen die roh gelesene Adresse, weil die
    Adressbuch-Maskierung `email` vorher auf `None` setzt — die
    Fachentscheidung will aber auch fuer Nicht-Admins die Form
    „elv*******.de“ sehen und nicht ein leeres Feld.

    DSGVO-2d: Eine GELOESCHTE Person traegt an keinem Namensfeld mehr etwas
    anderes als ``Gelöschte Person`` — auch fuer Administratoren. Die
    Loeschung ist nicht rueckgaengig zu machen (Fachentscheidung 2026-10-20);
    ein „vollstaendiger“ Blick gibt es fuer sie nicht, nur die neutrale
    Kennung.
    """
    adresse = datensatz.get(email_feld) or datensatz.get("email")
    out = dict(datensatz)
    kennung = out.get("name") or out.get("mitglied") or out.get("kennung") or ""
    if _ist_geloescht(str(kennung), out):
        kurz = GELOESCHT_ANZEIGE
    else:
        kurz = kuerze_name(out.get("vorname"), out.get("nachname"), kennung)
    for feld in AUSGETRETEN_LEEREN:
        if feld in out:
            out[feld] = None
    # Der Anzeigename steht in ALLEN Namensspalten, die die Wege lesen — sonst
    # liefert die Mitgliederliste weiter `vorname`/`nachname` der geloeschten
    # Zeile, waehrend `full_name` schon neutral ist (zwei Antworten auf
    # dieselbe Frage, DSGVO-2d). `nachname` faellt dabei auf `None` (die
    # Spalte ist in der Antwort der Liste vorhanden), `vorname` traegt den
    # vollen Text, weil genau dieses Feld Frontends ohne `full_name` lesen.
    out["vorname"] = kurz
    out["nachname"] = None
    # DSGVO-2d: keine Maske aus der Adresse einer geloeschten Person. Die
    # Loeschung entfernt die Adresse; „elv*******.org“ wuerde sie neu aus der
    # Zeile ableiten (und in einem alten Sicherungsstand steht sie noch da).
    out["email"] = None if _ist_geloescht(str(kennung), out) else maskiere_email(adresse)
    if "full_name" in out:
        out["full_name"] = kurz
    if "anzeigename" in out:
        out["anzeigename"] = kurz
    if "anzeige" in out:
        out["anzeige"] = kurz
    return out


def kuerze_zeilen(
    zeilen: Iterable[Mapping[str, Any]], sicht: PersonenSicht,
    *, kennungsfeld: str = "name", email_feld: str = "email",
) -> list[dict[str, Any]]:
    """Liste von Personenzeilen, je Zeile nach derselben Regel gekuerzt.

    Gekuerzt werden AUSGETRETENE (nur fuer Nicht-Admins, ``ist_ausgeschieden``)
    und GELOESCHTE (immer — ``ist_geloescht``; die Loeschung ist endgueltig,
    DSGVO-2d). Die zweite Frage laeuft getrennt, weil ``ist_ausgeschieden``
    fuer eine geloeschte Person bewusst ``False`` sagt (sie ist nicht
    „ausgetreten“, sie hat ihren eigenen Text).
    """
    return [
        kuerze(z, email_feld=email_feld) if (
            ist_geloescht(z)
            or (ist_ausgeschieden(z) and not sicht.darf_vollstaendig(z.get(kennungsfeld)))
        ) else dict(z)
        for z in zeilen
    ]


def anzeigename(
    mitglied: Any,
    vorname: Any = None,
    nachname: Any = None,
    *, sicht: PersonenSicht | None = None,
) -> str:
    """DER Anzeigename einer Person — einmal, fuer alle Auslieferungswege.

    AUSTRITT-b (B1): Die Kuerzung galt nur fuer Mitgliederliste, Detail,
    Personenpool und Abwesenheiten. Gruppen-Historie, Kalender, Dienstplan,
    Planung, Verantwortliche und Organigramm bauten den Namen weiter selbst
    zusammen — und lieferten damit den Klarnamen einer ausgetretenen Person an
    jeden Leser. Diese Funktion ist die eine Stelle dafuer:

    * Wer die Person vollstaendig sehen darf (Administrator, die Person
      selbst), bekommt ``Elvira Dorn``,
    * alle anderen bei einer ausgetretenen Person ``Elvira D.``.

    ``mitglied`` ist entweder die Kennung oder die gelesene Zeile. Ist es eine
    Zeile (``Mapping``), entsteht daraus die Sicht-Zuordnung UNABHAENGIG von
    einer zweiten Abfrage; Vor- und Nachname kommen dann aus der Zeile, sofern
    nicht ausdruecklich uebergeben.

    ACHTUNG (AUSTRITT-d/NN1): Gekuerzt wird nach ``ist_ausgeschieden`` — das
    fragt ``status`` und ``austritt_datum``, nicht mehr die Marke
    ``ausgeschlossen``. Eine Zeile OHNE diese beiden Felder gilt deshalb als
    „nicht ausgetreten“, und der Klarname geht still heraus. Aufrufer, die die
    Felder nicht mitgelesen haben, muessen die Kennung uebergeben (dann wird
    sie nachgelesen), oder die Zeile vollstaendig lesen. Fail-closed waere hier
    nicht richtiger: eine Zeile ohne ``status`` ist ein Programmierfehler, kein
    Zustand — deshalb der laute Hinweis statt einer stillen Ersatzform.
    """
    sicht = sicht or PersonenSicht.aus()
    # DSGVO-2d: Die geloeschte Person hat GENAU EINEN Anzeigenamen — auch fuer
    # Administratoren und auch dann, wenn die Zeile (alter Sicherungsstand)
    # noch einen Namen traegt. Deshalb steht die Frage VOR der Sicht-Pruefung
    # und vor der Frage „ausgetreten“.
    geloescht = ist_geloescht(mitglied)
    if isinstance(mitglied, Mapping):
        zeile: Mapping[str, Any] = mitglied
        kennung = str(zeile.get("name") or zeile.get("mitglied") or "")
        vor = zeile.get("vorname") if vorname is None else vorname
        nach = zeile.get("nachname") if nachname is None else nachname
        ausgeschieden = ist_ausgeschieden(zeile)
    else:
        kennung = str(mitglied or "")
        vor, nach, ausgeschieden = vorname, nachname, False
        if kennung:
            ausgeschieden = _marke_ausgetreten(kennung)

    if geloescht:
        return GELOESCHT_ANZEIGE

    voll = _name_aus_teilen(vor, nach)
    if not ausgeschieden or sicht.darf_vollstaendig(kennung):
        return voll or kennung
    # Die Kurzform braucht den Vornamen; ohne ihn bleibt nur der Nachname-
    # Anfangsbuchstabe — nie die Kennung (die waere oft die Adresse).
    return kuerze_name(vor, nach, kennung) if (vor or nach) else _kurzform_nachlesen(kennung)


def _name_aus_teilen(vorname: Any, nachname: Any) -> str:
    zeilen = [str(x).strip() for x in (vorname, nachname) if str(x or "").strip()]
    return " ".join(zeilen)


def _marke_ausgetreten(kennung: str) -> bool:
    """``ist_ausgeschieden`` einer Kennung — EINE Abfrage je Kennung.

    AUSTRITT-c (N3): gelesen werden die Merkmale, nicht die Marke; die
    Kuerzungsfrage haengt am Austritt (siehe ``ist_ausgeschieden``).

    DSGVO-2d: Eine geloeschte Person ist hier NICHT „ausgetreten“ — sie hat
    einen eigenen Anzeigenamen (``GELOESCHT_ANZEIGE``) und keine Kurzform.
    Deshalb wird der Endstatus mitgelesen und ausgeschlossen.
    """
    from .query import get_value

    zeile = get_value(
        "Mitglied", kennung, ["status", "austritt_datum"], as_dict=True,
    )
    if isinstance(zeile, list):
        zeile = zeile[0] if zeile else None
    if not zeile:
        return False
    if _ist_geloescht(kennung, dict(zeile)):
        return False
    return ist_ausgeschieden(dict(zeile))


def _kurzform_nachlesen(kennung: str) -> str:
    """Kurzform, wenn der Aufrufer nur die Kennung und keine Namen hatte."""
    from .query import get_value

    zeile = get_value(
        "Mitglied", kennung, ["vorname", "nachname", "status"], as_dict=True,
    )
    if isinstance(zeile, list):
        zeile = zeile[0] if zeile else None
    if not zeile:
        return GELOESCHT_ANZEIGE if _ist_geloescht(kennung) else "Ehemaliges Mitglied"
    if _ist_geloescht(kennung, dict(zeile)):
        return GELOESCHT_ANZEIGE
    return kuerze_name(zeile.get("vorname"), zeile.get("nachname"), kennung)


def namen_map(
    kennungen: Iterable[Any], sicht: PersonenSicht | None = None,
) -> dict[str, str]:
    """Kennung -> Anzeigename fuer eine ganze Liste (eine Abfrage, nicht N).

    Der Ersatz fuer die handgebauten ``mitglied_name_map``-Schleifen in
    Kalender und Dienstplan (AUSTRITT-b, B1): gleiche Form, aber mit der
    Kuerzungsregel dieser Datei.
    """
    from .query import get_all

    ids = sorted({str(k) for k in kennungen if k})
    if not ids:
        return {}
    sicht = sicht or PersonenSicht.aus()
    zeilen = get_all(
        "Mitglied",
        filters={"name": ["in", ids]},
        fields=["name", "vorname", "nachname", "ausgeschlossen", "status",
                "austritt_datum"],
    ) or []
    return {
        str(z["name"]): anzeigename(z, sicht=sicht)
        for z in zeilen if isinstance(z, Mapping) and z.get("name")
    }


__all__ = [
    "ADMIN_ROLES",
    "AUSGETRETEN_LEEREN",
    "EMAIL_KLARZEICHEN",
    "GELOESCHT_ANZEIGE",
    "GELOESCHT_PRAEFIX",
    "PersonenSicht",
    "STATUS_AUSGETRETEN",
    "STATUS_GELOESCHT",
    "anzeigename",
    "ist_ausgeschieden",
    "ist_geloescht",
    "kuerze",
    "kuerze_name",
    "kuerze_zeilen",
    "maskiere_email",
    "namen_map",
]
