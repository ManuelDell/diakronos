"""Brute-Force-Zaehler fuer die Anmeldung — Karte A1c1.

`/api/method/login` war bis hierher unbegrenzt durchprobierbar. Die
Antwortzeit war zwar gemessen konstant (Verhaeltnis bekannt/unbekannt 1,07),
aber es gab kein Limit fuer die Zahl der Versuche. Dieses Modul ist die
Datenschicht dafuer: zwei unabhaengige Zaehler in Redis, die Sperre greift,
sobald **einer** von beiden die Schwelle ueberschreitet.

  * **pro Benutzer** — der E-Mail-Name, kleingeschrieben.
  * **pro Client-IP** — `request_context.get_client_ip()`.

Warum zwei und nicht einer: ein Benutzerzaehler allein stoppt keinen
Angriff, der viele Konten durchprobiert (Credential Stuffing); ein
IP-Zaehler allein trifft jeden, der hinter einem NAT sitzt. Nur einer der
beiden muss ausloesen, damit beide Angriffsrichtungen gedeckt sind.

SICHERHEITSWIRKUNG (das ist der eigentliche Zweck):

  * Ein gesperrter Versuch bekommt **exakt dieselbe Antwort** wie ein
    falsches Passwort: HTTP 401, gleicher Body, gleiche Kopfzeilen. Kein
    429, kein Feld, kein Hinweis auf "gesperrt". Wer das sichtbar macht,
    gibt einem Angreifer eine Information, die er sonst nicht haette — und
    liefert ihm obendrein eine schnellere Erfolgschance, weil jede weitere
    Pruefung entfaellt.
  * Auch die **Antwortzeit** bleibt im Gleichen: der Zaehler wird VOR der
    Passwortpruefung abgefragt und der gesperrte Zweig fuehrt dieselbe
    Dummy-Hash-Pruefung aus wie der unbekannte Benutzer. Wer die Sperre an
    der Antwortzeit erkennt, hat sie an der Antwortform erkannt.
  * Ein Eintrag fuer einen **unbekannten** Benutzer hat dieselbe Form,
    dieselbe TTL und dieselbe Schluessellaenge wie ein bekannter. Der
    Schluessel traegt **kein Klartext** der E-Mail, sondern ein Salt
    (`settings.secret_key`) ueber SHA-256: jemand mit Zugriff auf den
    Keyspace sieht keine Adressen, und der Schluessel selbst laesst sich
    nicht zurueckrechnen.
  * Zurueckgesetzt wird nur nach einem **erfolgreichen** Login. Sonst waere
    ein Benutzer, der sich zweimal vertippt hat, fuer immer ausgesperrt.

ZAEHLER GETRENNT, SPERRE GEMEINSAM (Karte A1c2, CalDAV):

CalDAV ist der zweite Zugang zu denselben Konten. Es zaehlt deshalb in einem
EIGENEN Bereich (`bereich="caldav"`), teilt sich mit dem Login aber die
Sperre. Beides ist Absicht, und beides hat einen Grund:

  * **Eigene Zaehler**: wer sich dreimal im Browser vertippt, hat seinen
    Kalender damit noch nicht blockiert — und wer dreimal am Kalender
    scheitert, ist dadurch noch nicht aus der SPA ausgesperrt. Beide
    Alltagsfaelle bleiben sauber getrennt.
  * **Gemeinsame Sperre**: die Sperre ist die *Sanktion*, nicht der
    Zaehler. Wer ueber CalDAV gegen dieselben Konten brute-forcet, ist
    derselbe Angreifer mit demselben Werkzeug — er darf durch den zweiten
    Zugang nicht an der Sperre des ersten vorbeikommen. Deshalb liegen die
    Sperr-Keys NICHT im Bereichs-Praefix, sondern unter
    `diakronos:anmeldesperre:` und gelten damit fuer jede Benutzeroberflaeche.
    Wer in einem Bereich gesperrt wird, ist es in beiden.

Damit gilt fuer beide Bereiche dieselbe Schwelle und dieselbe Backoff-Kurve
(`settings.login_*`); die ENV-Variablen heissen weiter so, weil es EIN
Mechanismus mit zwei Zaehlern ist.

SCHLUESSELRAUM (Redis). Zaehler je Bereich, Sperre und Stufe global:

    diakronos:loginversuche:u:<sha256>   -> "3"      (Fehlversuche, Benutzer, Login)
    diakronos:caldaversuche:u:<sha256>   -> "2"      (Fehlversuche, Benutzer, CalDAV)
    diakronos:anmeldesperre:u:<sha256>   -> "300"    (gesperrt bis, epoch) — beide Bereiche
    diakronos:anmeldesperre:ip:<sha256>  -> "600"    (gesperrt bis, epoch) — beide Bereiche
    diakronos:anmeldesperre:u:<sha256>:sperre:stufe -> "1"  (Backoff-Stufe)

Die Praefixe der Bereiche entstehen aus dem Bereichsnamen
(`diakronos:<bereich>versuche:`); `login` bleibt aus Kompatibilitaet
unveraendert. Der alte Aufbau (Sperr-Key unter dem Zaehler-Praefix) gilt
nicht mehr — die Sperre ist Bereich-uebergreifend.

Ein Eintrag fuer die Sperre zu loeschen waere ein Fehler: die Sperre MUSS
den Ablauf ueberleben (TTL), sonst waere sie per Timing trivial umgehbar.

ABNAHMESCHNITTSTELLE — CalDAV (Karte A1c2) baut hierauf auf:

    erlaubt, grund = loginversuche.pruefe_und_merke(user, ip, bereich="caldav")
    ...
    loginversuche.entlaste(user, ip, bereich="caldav")

ZWEITE SCHWELLE, EINE PROXY-REGEL (Karte A1c10)
-------------------------------------------------
Bis hierher galt EINE Schwelle fuer BEIDE Zaehler, und damit war sie an
genau einer Stelle falsch: am Konto war sie richtig, an der Adresse ein
Ausfall. Jetzt gilt `_max_versuche(art)` — 5 am Konto, 25 an der Adresse.

Warum getrennt: fuenf Fehlversuche sind am Konto genau richtig (sie treffen
den, der sich vertippt hat). An einer **Adresse** sperren dieselben fuenf
das ganze Buero — eine Gemeinde hat typischerweise einen Internetanschluss,
hinter einem Reverse-Proxy ist die Adresse die des Proxies, im LAN die des
Routers — und der Zustand laesst sich nicht einmal einem Benutzer zuordnen.
25 ist die Sammelsperre gegen jemanden, der viele Konten durchprobiert
(Credential Stuffing): fuer einen Angreifer kostet das fast nichts, fuer
Menschen hinter einem gemeinsamen Anschluss praktisch nie.

Zusaetzlich gilt seit A1c10: **eine Adresse, die nach eigener Infrastruktur
aussieht, wird nie gesperrt und nicht mal gezaehlt** — Loopback, privat,
link-local, unspecified. Das entscheidet **eine** Funktion,
`_ist_eigene_adresse()`, aufgerufen aus `_kennungen()`. Weil dort, kann kein
Aufrufer die Ausnahme umgehen: auch nicht ueber `X-Forwarded-For`, denn die
Pruefung gilt fuer jede hereinkommende Adresse. Die Kontosperre bleibt
davon unberuehrt — sie greift ja trotzdem.

Warum das die richtige Richtung ist, und nicht die bequeme: hinter einem
Reverse-Proxy sieht die App ohnehin die Proxy-Adresse (privat). Sie zu
sperren hiesse, dass der naechste Versuch eines *beliebigen* Nutzers
abgewiesen wird. Im LAN gilt dasselbe fuer die Routeradresse. Im Internet
dagegen — direkt oder per korrekt gesetztem `X-Forwarded-For` — ist die
Adresse des Angreifers eine **oeffentliche**, und die wird gezaehlt und ab
25 gesperrt, genau wie gewollt. Der Schutz existiert also dort, wo er
etwas nuetzt, und nicht dort, wo er nur Buero aussperrt.

EINE QUELLE DER WAHRHEIT (A1c3-Lehre)
-------------------------------------
"`_max_versuche()` wird zu zwei Funktionen oder einer mit Argument — aber
eine Quelle der Wahrheit, keine zwei kopierten Konstanten." Genau das ist
das Muster, das A1c3 bei `ADMIN_ROLES` gemessen hat, und es ist hier die
dritte Kopie, die jemand machen koennte. Es gibt deshalb nur diese eine
Funktion — und `test_a1c10_sperren.py` haelt fest, dass sie die einzige
Stelle ist, an der Schwellen und Proxy-Regel gelesen werden.

AUFRÄUMWEG (Karte A1c6) — EIN Aufruf fuer ALLE Bereiche:

    loginversuche.zuruecksetzen_alles(user)          # nur das Konto
    loginversuche.entsperre_konto_und_ip(user, ip)   # Konto UND IP (Notweg)
    loginversuche.gib_bericht(user, ip)              # was waere zu loeschen?

Gesperrte Konten kommen sonst nur ueber die Zeit wieder herein, und ist der
einzige Administrator selbst gesperrt, gibt es niemanden, der warten kann.
Da Zaehler je Bereich getrennt sind und die Sperre nicht, muss der
Aufraehrweg beides kennen — er steckt deshalb in EINER oeffentlichen
Funktion ueber `BEREICHE` und nicht in einer Liste, die ein Aufrufer pflegen
muss. Siehe den Docstring von `pruefe_und_merke`.

DREI Funktionen, nicht eine, und der Unterschied ist der Kern von A1c6:

  * `zuruecksetzen_alles(user)` loest **nur das Konto**. Die IP-Sperre
    gehoert dem Absender, nicht dem Konto; ein Admin, der sein eigenes Konto
    freigibt, will nicht ungefragt das halbe Buero mitentsperren. Das ist die
    Entscheidung aus A1c2 und sie bleibt hier unangetastet.
  * `entsperre_konto_und_ip(user, ip)` loest zusaetzlich die IP — als
    AUSDRUECKLICHER zweiter Schritt des Aufrufers, weil an einer IP alle
    Konten desselben Anschlusses haengen. Bei einem Gemeindeanschluss ist das
    das halbe Buero; das muss der Aufrufer wissen und bestaetigen koennen,
    es darf nicht als Nebenwirkung mitlaufen.
  * `gib_bericht(user, ip)` sagt, **ob** es etwas zu tun gab, ohne etwas zu
    tun und ohne den Bestand preiszugeben. Nur je Kennungsart eine Anzahl von
    Schluesseln, nie Zaehlerstaende oder Sperrzeiten: der Aufraehrweg soll
    bestaetigen koennen, ohne ein Auskunftswerkzeug ueber den Bestand zu sein.

Das Entschperren selbst ist ein **Privileg** und deshalb begrenzt:
`pruefe_werkzeugbudget()` zaehlt je Benutzer und Zeitfenster, damit ein
uebernommenes Administrator-Konto nicht der Knopfdruck fuer die
Wiederfreigabe ist. Auch dieser Zaehler traegt nur einen gesalzenen Hash —
der Keyspace bleibt ueberall ohne Klartext.

`pruefe_und_merke` ist absichtlich **benutzer + IP** und nicht nur
`user`: derselbe Store, dieselbe Schwelle, derselbe Backoff-Mechanismus.
Der Aufrufer entscheidet danach selbst ueber die Antwort — fuer CalDAV ist
das `unauthorized_response()` aus `caldav/auth.py`, fuer den Login die
`AuthenticationError` aus `api/auth.py`. Beides ist derselbe 401.

Die Client-IP liefert `request_context.zaehler_client_ip()`, das
`X-Forwarded-For` nur auswertet, wenn `settings.behind_proxy` gesetzt ist
(fail closed, siehe dort).
"""

from __future__ import annotations

import hashlib
import json
import logging
from ipaddress import ip_network
from typing import Any

from diakronos_app.ip_adressen import parse_ip
from diakronos_app.settings import settings

logger = logging.getLogger("diakronos_app.auth")

__all__ = [
    "SCHLUESSEL_PRAEFIX",
    "SPERRE_PRAEFIX",
    "BEREICH_LOGIN",
    "BEREICH_CALDAV",
    "BEREICHE",
    "BEREICH_ANZEIGE",
    "pruefe_und_merke",
    "entlaste",
    "zaehler_stand",
    "zuruecksetzen",
    "zuruecksetzen_alles",
    "gib_bericht",
    "entsperre_konto_und_ip",
    "zaehle_gesperrte_ips",
    "zaehle_adressen_im_weg",
    "pruefe_werkzeugbudget",
    "ist_gesperrt",
    "WERKZEUGLIMIT_PRAEFIX",
    "EIGENE_ADRESSEN",
]

# Eigener Praefix, damit der Store weder mit den Sitzungen (`sitzungen.py`)
# noch mit der RQ-Queue kollidiert.
SCHLUESSEL_PRAEFIX = "diakronos:loginversuche:"

# Praefix der **Sperre**. Bewusst NICHT unter `SCHLUESSEL_PRAEFIX`: die
# Sperre gilt bereichsuebergreifend (siehe Modulkopf, Karte A1c2), die
# Fehlversuchszaehler sind je Bereich getrennt.
SPERRE_PRAEFIX = "diakronos:anmeldesperre:"

# Praefix der Werkzeug-Budgets (Karte A1c6). Eigener Namensraum, damit das
# Rate-Limit des Entschperr-Werkzeugs weder mit den Fehlversuchszaehlern noch
# mit den Sperren kollidiert. Der Wert traegt nur einen Bezeichner des
# Werkzeugs und einen gesalzenen Hash — keine Adresse (siehe `_limit_key`).
WERKZEUGLIMIT_PRAEFIX = "diakronos:werkzeuglimit:"

# Die beiden Bereiche (Benutzeroberflaechen) mit eigenen Zaehlern.
BEREICH_LOGIN = "login"
BEREICH_CALDAV = "caldav"

# Alle Bereiche als eine Liste — die einzige Stelle, an der eine neue
# Benutzeroberflaeche eingetragen werden muss. `zuruecksetzen_alles()`
# (Karte A1c6) laeuft hier drueber; ein Aufraehrweg, der nur einen Bereich
# kennt, wuerde die andere Oberflaeche stillschweigend stehen lassen.
BEREICHE: tuple[str, ...] = (BEREICH_LOGIN, BEREICH_CALDAV)

# Anzeigenamen der Bereiche — fuer Menschen, nicht fuer Schluessel. Die
# `BEREICHE` selbst sind Speichernamen (`"caldav"`), die in einer Ausgabe an
# der Konsole nicht wie eine Benutzeroberflaeche lesen. Der Notweg (A1c6)
# nimmt sie daher von hier statt die Rohnamen zu formatieren.
BEREICH_ANZEIGE: dict[str, str] = {
    BEREICH_LOGIN: "Login",
    BEREICH_CALDAV: "CalDAV",
}

# Untergrenze fuer die Backoff-Deckelung in Sekunden. Alles darunter macht
# den Mechanismus fuer den Angreifer billiger, statt ihn zu bremsen.
_MIN_BACKOFF = 30


def _max_versuche(art: str = "u") -> int:
    """Schwelle: wie viele Fehlversuche bis zur Sperre — **je Art** (A1c10).

    Vor A1c10 gab es EINE Zahl fuer beide Zaehler, und damit war sie an
    beiden Stellen falsch: am Konto war sie richtig, an der Adresse eine
    Katastrophe (siehe `settings.py`).

    Zwei Schwellen aus zwei ENV-Variablen, aber **eine** Quelle der Wahrheit:
    diese Funktion ist der einzige Ort, an dem gelesen wird — dieselbe Lehre
    wie bei `ADMIN_ROLES` (A1c3). Zwei kopierte Konstanten an zwei
    Aufrufstellen waeren die Vorlage fuer den naechsten Fehler.

    `art` ist `"u"` (Konto) oder `"ip"` (Adresse). Alles andere gilt als
    Konto — ein Tippfehler im Aufrufer darf deshalb nicht dazu fuehren, dass
    die Adressschwelle durchfaellt.
    """
    if art == "ip":
        return max(1, int(getattr(settings, "login_max_versuche_ip", 25)))
    return max(1, int(settings.login_max_versuche))


# Einzige Infrastruktur-Policy (A1c12), mit echten Netzgrenzen statt Praefixen.
# Nicht `is_private`: das nimmt auch die Dokumentationsnetze 203.0.113/24
# und 2001:db8::/32 aus, die hier wie bisher sperrbar bleiben muessen.
EIGENE_ADRESSEN = tuple(ip_network(netz) for netz in (
    "0.0.0.0/32", "10.0.0.0/8", "127.0.0.0/8", "169.254.0.0/16",
    "172.16.0.0/12", "192.168.0.0/16",
    "::/128", "::1/128", "fc00::/7", "fe80::/10",
))


def _ist_eigene_adresse(ip: str | None) -> bool:
    """Gehoert die Adresse zur eigenen Infrastruktur? (Karte A1c10)

    **Diese eine Funktion entscheidet, ob eine Adresse ueberhaupt gezaehlt
    und gesperrt werden darf.** Es gibt keine zweite Pruefung und keine
    Kopie in einem anderen Modul: XFF ausgewertet oder nicht, der Aufrufer
    ruft immer hierher.

    Warum das die richtige Richtung ist, und nicht die bequeme:

      * **Hinter einem Reverse-Proxy** sieht die App ohnehin die Proxy-Adresse
        (privat). Sie zu sperren hiesse: der naechste Versuch eines *beliebigen*
        Nutzers wird abgewiesen, und der Zustand ist nicht mal mehr einem
        Benutzer zuzuordnen. Das ist kein Schutz, das ist Selbstbeschaedigung.
      * **Im LAN** ohne Proxy gilt dasselbe: alle Geraete teilen sich die
        private Adresse des Routers. Eine Adresssperre waere dort reines Glueck.
      * **Im Internet hinter einem korrekt konfigurierten Proxy**
        (`BEHIND_PROXY=1`, `X-Forwarded-For`) ist die Adresse des Angreifers
        eine **oeffentliche** — die wird gezaehlt und ab 25 gesperrt,
        genau wie gewollt.
      * Ohne Proxy direkt im Internet: die App sieht die oeffentliche Adresse
        direkt, sie wird gesperrt. Der Schutz existiert also dort, wo er
        etwas nuetzt.

    Die Regel gilt auch fuer IPv6 und fuer Adressen aus XFF. Validitaet
    bedeutet NICHT Vertrauen: `BEHIND_PROXY=1` setzt einen Proxy voraus,
    der fremdes XFF ueberschreibt, und keinen direkten Zugang zur App.
    Sonst kann ein Client eine private Adresse behaupten und den IP-Zaehler
    umgehen. Ungueltiges XFF faellt im Request-Kontext auf den Peer zurueck;
    ungueltige Werte hier sind nicht eigen, bekommen aber keinen IP-Key.

    `LOGIN_IP_SPERRE_AUCH_PRIVAT=1` hebt die Regel ausdruecklich auf. Wer das
    tut, sperrt damit praktisch das ganze Buero — siehe `settings.py`.
    """
    adresse = parse_ip(ip)
    if adresse is None:
        return False
    if bool(getattr(settings, "login_ip_sperre_auch_privat", False)):
        return False
    return any(adresse in netz for netz in EIGENE_ADRESSEN)


def _sperrzeit() -> int:
    """Grunddauer der Sperre in Sekunden."""
    return max(_MIN_BACKOFF, int(settings.login_sperre_sekunden))


def _client() -> Any:
    """Redis-Client (patchbar fuer Tests, siehe `tests/conftest.py`).

    Bewusst ein eigener Zugriff wie in `sitzungen.py`: der Healthcheck-Client
    aus `main.py` setzt ein Zeitbudget fuer Verbindungstests, hier wird
    normal gearbeitet.
    """
    from redis import Redis

    return Redis.from_url(settings.redis_url, decode_responses=True)


def _hash(rohdaten: str) -> str:
    """Schluessel-Anteil aus `rohdaten` — ohne Klartext im Redis-Key.

    Gesalzen mit `settings.secret_key`: ohne das Salt waere der Key ein
    Rainbow-Angriff auf den Adressraum (E-Mails sind vorhersagbar), mit dem
    Salt des Stack-Betreibers nicht. Aus dem Key laesst sich die E-Mail
    nicht zurueckrechnen; `_klartext_pruefen()` in den Tests belegt, dass
    sie nirgends im Keyspace auftaucht.
    """
    salz = str(getattr(settings, "secret_key", "") or "")
    return hashlib.sha256(f"{salz}|{rohdaten}".encode()).hexdigest()[:32]


def _key_benutzer(user: str, bereich: str = BEREICH_LOGIN) -> str:
    return f"{_zaehler_praefix(bereich)}u:{_hash(user.strip().lower())}"


def _key_ip(ip: str, bereich: str = BEREICH_LOGIN) -> str:
    return f"{_zaehler_praefix(bereich)}ip:{_hash(ip.strip())}"


def _zaehler_praefix(bereich: str = BEREICH_LOGIN) -> str:
    """Der Zaehler-Praefix eines Bereichs — `diakronos:<bereich>versuche:`.

    Der Bereichsname ist ein interner Bezeichner (Konstante), kein
    Benutzereingang; trotzdem wird er auf das erlaubte Alphabet
    zurueckgebracht, damit `bereich="../../x"` keinen Key ausserhalb des
    Store-Namensraums bauen kann.
    """
    roh = str(bereich or BEREICH_LOGIN).strip().lower()
    erlaubt = "".join(z for z in roh if z.isalnum())
    if erlaubt == BEREICH_LOGIN:
        return SCHLUESSEL_PRAEFIX
    return f"diakronos:{erlaubt or BEREICH_LOGIN}versuche:"


def _kennungen(
    user: str | None,
    ip: str | None,
    bereich: str = BEREICH_LOGIN,
) -> list[tuple[str, str, str]]:
    """Die (Art, Zaehler-Key, Sperr-Key)-Tripel fuer diesen Versuch.

    Beide Keys entstehen aus **derselben** Art und demselben Hash — nur der
    Praefix unterscheidet sich:

      * der Zaehler-Key traegt den Bereich (`diakronos:caldaversuche:u:<h>`),
        damit CalDAV und Login getrennt zaehlen, und
      * der Sperr-Key traegt ihn **nicht** (`diakronos:anmeldesperre:u:<h>`),
        damit die Sperre bereichsuebergreifend gilt (Modulkopf, A1c2).

    Leere Kennungen fallen weg: ein leerer Benutzername darf keinen
    gemeinsam genutzten Zaehler hochzaehlen, sonst koennte ein Aufruf
    ohne `usr` den IP-Zaehler aller Anfragen desselben Absenders
    verbrauchen. Der IP-Zaehler greift trotzdem — der Absender ist ja da.

    **Eigene Adressen fallen hier ebenfalls weg** (Karte A1c10): fuer
    die geparsten IPv4-/IPv6-Infrastrukturnetze in `EIGENE_ADRESSEN`
    entsteht damit **kein** Zaehler-Key und **kein** Sperr-Key. Diese Filterung
    ist der Grund, warum die Regel an *einer* Stelle sitzt: jeder Aufrufer
    (Zaehlen, Sperrenpruefen, Entlasten, Bericht, Freigeben) geht ueber
    `_kennungen`, und keiner kann die Ausnahme umgehen. Wer hier die Filterung
    entfernt, sperrt das halbe Buero — der Proxy waere wieder angreifbar.
    """
    praefix = _zaehler_praefix(bereich)
    paare: list[tuple[str, str, str]] = []
    if user and user.strip():
        kurz = _hash(user.strip().lower())
        paare.append(("u", f"{praefix}u:{kurz}", f"{SPERRE_PRAEFIX}u:{kurz}"))
    # Validitaet ist NICHT Vertrauen: Muell erzeugt keinen IP-Key. Der
    # Request-Kontext faellt bei kaputtem XFF auf den echten Peer zurueck;
    # die Kontokennung bleibt auch bei fehlender/privater Peer-IP erhalten.
    adresse = parse_ip(ip)
    if adresse is not None and not _ist_eigene_adresse(str(adresse)):
        kurz = _hash(str(adresse))
        paare.append(("ip", f"{praefix}ip:{kurz}", f"{SPERRE_PRAEFIX}ip:{kurz}"))
    return paare


def _werkzeug_name(werkzeug: str) -> str:
    """Bezeichner eines Werkzeugs auf das erlaubte Alphabet zurueckbringen.

    Wie `bereich` in `_zaehler_praefix`: interner Bezeichner, kein
    Benutzereingang. Der Filter haelt den Key trotzdem im eigenen
    Namensraum — `werkzeug="../../x"` darf keinen Schluessel ausserhalb
    des Store-Namensraums bauen.
    """
    roh = str(werkzeug or "unbekannt").strip().lower()
    return "".join(z for z in roh if z.isalnum() or z in "_-") or "unbekannt"


def _limit_key(werkzeug: str, kennung: str) -> str:
    """Budget-Key eines Werkzeugs je Benutzer.

    Die Kennung laeuft durch denselben gesalzenen Hash wie die Zaehler-Keys
    (Modulkopf): **kein Klartext** des Benutzernamens im Keyspace, auch nicht
    beim Rate-Limit. Wer den Keyspace liest, sieht keine Adressen.
    """
    return f"{WERKZEUGLIMIT_PRAEFIX}{_werkzeug_name(werkzeug)}:{_hash(str(kennung).strip().lower())}"


def pruefe_werkzeugbudget(
    werkzeug: str,
    kennung: str,
    max_anzahl: int,
    fenster_sekunden: int,
    client: Any = None,
) -> tuple[bool, int]:
    """Budget fuer ein **Privileg** — je Benutzer und Zeitfenster.

    Gebraucht fuer Werkzeuge, die auf den Sperrstore zugreifen: das
    Entschperren ist ein Verwaltungsakt, und ein uebernommenes
    Administrator-Konto darf davon nicht der Knopfdruck fuer die
    Wiederfreigabe sein (Karte A1c6).

    Warum je **Benutzer** und nicht je Sitzung: der Aufrufer dieser
    Funktion nennt die Identitaet, und ein Angreifer mit gestohlenem
    Admin-Konto bekommt seine eigene Sitzung geschenkt — ein
    Sitzungsbudget ließe sich also durch einen simplen Relog umgehen.
    Genau der Angriff, gegen den das Budget steht, wuerde ihn nutzen.

    Rueckgabe `(erlaubt, verbleibend)`. Der Zaehler startet bei 1 fuer den
    aktuellen Aufruf; das Fenster beginnt beim ERSTEN Aufruf und laeuft
    bei jedem weiteren NICHT weiter — sonst verschiebt Dauerlast das Ende
    und die Grenze waere nie erreicht.

    `max_anzahl <= 0` heisst: unlimited. Das ist bewusst **nicht** der
    Defaultpfad — die Settings erzwingen `>= 1`, und ein Aufrufer, der das
    ausser Kraft setzen will, muss es ausdruecklich tun.
    """
    if max_anzahl <= 0:
        return True, -1
    client = client or _client()
    key = _limit_key(werkzeug, kennung)
    anzahl = int(client.incr(key))
    try:
        rest = int(client.ttl(key))
    except Exception:  # noqa: BLE001 — Redis ohne TTL-Support
        rest = -1
    if rest < 0:
        client.expire(key, max(1, int(fenster_sekunden)))
    return anzahl <= int(max_anzahl), max(0, int(max_anzahl) - anzahl)


def _gelesen(client: Any, key: str) -> int:
    """Zaehlerstand als int. Beschaedigter Inhalt zaehlt als 0."""
    roh = client.get(key)
    if roh is None:
        return 0
    try:
        return int(roh)
    except (TypeError, ValueError):
        return 0


def _bis(client: Any, key: str) -> float:
    """Sekunden, bis der Schluessel ablaeuft. 0.0 = kein Eintrag."""
    try:
        ttl = client.ttl(key)
    except Exception:  # noqa: BLE001 — Redis ohne TTL-Support
        return 0.0
    try:
        return max(0.0, float(ttl))
    except (TypeError, ValueError):
        return 0.0


def ist_gesperrt(
    user: str | None,
    ip: str | None,
    client: Any = None,
    bereich: str = BEREICH_LOGIN,
) -> bool:
    """True, wenn Benutzer- ODER IP-Kennung gerade gesperrt ist.

    Nur lesend — der Aufrufer kann das Ergebnis in eigene Logik einbauen.
    `bereich` wird hier bewusst NICHT ausgewertet: die Sperre ist
    bereichsuebergreifend, eine Abfrage aus dem einen Bereich sieht sie
    genauso wie eine aus dem anderen (Modulkopf, A1c2).
    """
    client = client or _client()
    for _art, _zaehler, sperr_key in _kennungen(user, ip, bereich):
        if client.exists(sperr_key):
            return True
    return False


def zaehle_gesperrte_ips(client: Any = None) -> int:
    """Wie viele **Adressen** sind gerade gesperrt? — nur die Zahl.

    **ABNAHMESCHNITTSTELLE FUER DEN NOTWEG (Karte A1c6).**

    ACHTUNG, Karte A1c8: diese Funktion zaehlt **Sperren**, nicht das, was
    nach dem Aufraehrweg noch **sperrt**. Der Unterschied ist der haeufigste
    Fall einer Gemeinde ueberhaupt — ein Benutzer, fuenf erlaubte Fehlversuche
    vom gemeinsamen Anschluss: der Benutzerzaehler sperrt, der IP-Zaehler
    bleibt **auf der Schwelle** stehen, und im Store steht keine IP-Sperre.
    Diese Funktion sagt da `0`, und der Notweg meldete daraufhin "alles
    erledigt" mit Exitcode 0, waehrend die naechste Anmeldung 401 gab.

    **Fuer die Frage "steht noch etwas im Weg" ist deshalb
    `zaehle_adressen_im_weg()` da, nicht diese.** Diese bleibt fuer alles
    stehen, was ausdruecklich nach *Sperren* fragt (Bericht des Notwegs,
    Diagnose, Tests) — und wird dort nicht ersetzt, sondern benutzt.

    Warum es diese Funktion geben muss: nach dem Aufraehrweg des Kontos
    kann die **Adresse** weiter gesperrt sein. Das ist kein Restfehler,
    sondern der Regelfall hinter einem gemeinsamen Internetanschluss —
    eine Gemeinde hat typischerweise **einen** Internetzugang, alle
    Benutzer teilen sich `REMOTE_ADDR`, und der Benutzerzaehler und der
    IP-Zaehler werden getrennt gezaehlt. Welcher zuerst ausloest, haengt
    davon ab, von wo angegriffen wurde. Trifft es die IP, liefert
    `zuruecksetzen_alles(user)` "Konto frei, IP gesperrt" — und jede
    Anmeldung bleibt 401.

    Genau das hat die Gegenprobe des Orchestrators gemessen (Konto frei,
    IP gesperrt, weiter 401), und genau das ist der Grund, warum der
    Notweg die IP mitfreigeben muss. **Dieses Wissen muss aber auch
    erreichbar sein**, sonst meldet der Notweg "aufgehoben", der
    Betreiber probiert es aus, es geht nicht, und er weiss nicht, warum.

    Der Rueckgabewert sagt bewusst nur, dass **mindestens eine** Adresse
    gesperrt ist — nicht welche. Das ist kein Informationsleck: die
    Schluessel sind gesalzen gehasht, aus ihnen laesst sich keine Adresse
    zurueckrechnen, und ein Angreifer koennte sich aus dieser Zahl keinen
    Vorteil verschaffen, die ihm nicht ohnehin schon tausend misslungene
    Logins zeigen. Der Aufrufer muss die Adresse aus seinem Router/NAT
    lesen — das ist ein Schritt, den kein Befehl ersetzen kann.

    Nur lesend.
    """
    client = client or _client()
    # Die Sperre ist bereichsuebergreifend und liegt genau einmal im
    # Keyspace (Modulkopf, A1c2) — deshalb wird hier bewusst NICHT ueber
    # `BEREICHE` gezaehlt. Das wuerde dieselbe Sperre je Bereich einmal
    # treffen und sie vervielfachen; genau diesen Fehler hat es hier
    # zuerst gegeben.
    return len(_sperr_hash_anteile(client))


def _sperr_hash_anteile(client: Any) -> set[str]:
    """Die Hash-Anteile aller **gesperrten IP**-Schluessel — ohne `:stufe`.

    Ein Satz statt einer Liste, weil der Aufrufer nur die Zahl braucht und
    `:stufe` (die Backoff-Stufe derselben Sperre) nicht als eigene Sperre
    zaehlen darf — genau das war der erste Fehler in dieser Zaehlschleife.

    **Der Anteil ist der nackte Hash, nicht der ganze Schluessel** — genau
    derselbe Wert, den der Zaehlerpfad in `zaehle_adressen_im_weg()` liefert.
    Das ist keine Feinheit, sondern der ganze Zweck der Vereinigung: es
    geht darum, dass eine Adresse *einmal* gezaehlt wird, egal ob sie ueber
    ihre Sperre oder ueber ihren Zaehlerstand im Weg ist. Liefe der
    Schluessel mit `diakronos:anmeldesperre:ip:` vorn, koennten die beiden
    Mengen nie ueberlappen, und eine Adresse, die **beides** hat (gesperrt
    *und* Zaehler auf der Schwelle — moeglich, weil `pruefe_und_merke` die
    Bereiche nacheinander abarbeitet), wuerde **zweimal** gezaehlt. Genau
    das stand in der ersten Fassung, und die Beide-Faelle-Pruefung haelt es
    jetzt fest.
    """
    praefix = f"{SPERRE_PRAEFIX}ip:"
    return {
        text[len(praefix) :]
        for text in _scan_texte(client, f"{praefix}*")
        if text != praefix and not text.endswith(":stufe")
    }


def _scan_texte(client: Any, praefix: str) -> set[str]:
    """Alle Schluessel unter `praefix` — **dekodiert**, als Text.

    `scan_iter` liefert je nach `decode_responses` `str` **oder** `bytes`.
    `str(b"…:stufe")` endet nicht auf `:stufe` — der Vergleich faellt durch,
    und die Stufe wird mitgezaehlt. Genau das ist im echten Keyspace
    passiert. Deshalb wird hier einmal aufgeloest, statt es an jeder
    Stelle neu zu erinnern.

    `scan_iter` statt `keys`: `KEYS` blockiert den Server. Der
    Namensraum ist klein (das sind die Zaehler der gesperrten und der
    ueber der Schwelle liegenden Adressen einer Gemeinde, keine Millionen),
    ein COUNT je Durchgang genuegt.
    """
    return {
        (schluessel.decode() if isinstance(schluessel, bytes) else str(schluessel))
        for schluessel in client.scan_iter(match=f"{praefix}*", count=100)
    }


def zaehle_adressen_im_weg(client: Any = None) -> int:
    """Wie viele Client-Adressen stehen **so** weit, dass der naechste
    Versuch sie sperrt? — Sperren **und** Zaehler auf der Schwelle.

    **ABNAHMESCHNITTSTELLE FUER DEN NOTWEG (Karte A1c8).** Das ist die
    ehrliche Form von `zaehle_gesperrte_ips()`: sie zaehlt Adressen, die dem
    Anmeldepfad **jetzt** etwas im Weg tun, und nicht nur die, deren
    Sperrschluessel schon im Store liegt.

    WARUM DER ZAEHLER MITZAENHLT — und warum nicht jeder
    ---------------------------------------------------------
    `pruefe_und_merke` sperrt, wenn `zaehler > schwelle`, und **loescht den
    Zaehler dabei** (`_setze_sperre`). Ein Zaehler kann deshalb nie *ueber*
    der Schwelle stehen: er erreicht sie, und der naechste Versuch dieser
    Adresse sperrt sie. Damit ist `zaehler >= schwelle` exakt die Vorhersage
    "die naechste Anmeldung von dieser Adresse gibt 401" — und das ist die
    Frage, die ein Notfallwerkzeug beantworten muss.

    Die Grenze sitzt **inklusiv** auf der Schwelle. Genau ein Versuch
    darunter ist der Alltagsfall (wer sich dreimal vertippt) und darf keinen
    Alarm ausloesen; ein Versuch darueber kann nicht vorkommen, weil der
    Zaehler dort bereits in eine Sperre umgewandelt wurde. Live gemessen
    (echter Redis, DB 14): 1, 2, 3, 4, 5 Versuche -> Zaehler 1…5, kein
    Sperrschluessel; der 6. Versuch -> Sperre, Zaehler geloescht.

    Zwei Fehler, die dieser Aufbau verhindert:

      * **Jeden Zaehler mitzaehlen** (die naheliegende Loesung, und die
        Karte warnt zu Recht davor). Der Store hat **einen** Zaehler-Key
        je Bereich und Adresse — zwei heute, nicht "Dutzende bis Tausende",
        wie im Kartentext vermutet (gemessen, siehe Testdatei). Zaehlte man
        sie, waere die Zahl von der Liste der Bereiche abhaengig statt vom
        Bestand. Deshalb wird **je Adresse** gezaehlt: die Hash-Anteile
        aller Bereiche werden zu einer Menge vereinigt.
      * **Den Kontenzaehler mitzaehlen.** Er wird vom Aufraehrweg in allen
        Bereichen geloescht (`zuruecksetzen_alles`, `BEREICHE`) und kann
        danach nichts mehr blockieren. Ein Kontenzaehler hier zu zaehlen
        hiesse Alarm ohne Ursache.

    **Was das nicht beantworten kann — gemessen, nicht vermutet.** Ob eine
    gesperrte Adresse zu *diesem* Konto gehoert, laesst sich aus dem
    Keyspace nicht herstellen: die Schluessel sind gesalzen gehasht, der
    Benutzerschluessel traegt den Hash des Namens, der Adressschluessel den
    der Adresse, und es gibt keinen Eintrag, der beides verbindet
    (vollstaendiger Keyspace des Messfalls: drei Keys, keiner davon
    verbindend). Die Frage ist global gestellt — "steht **irgendeine**
    Adresse im Weg" — und damit eine **ueber**-Naeherung in die sichere
    Richtung: im Zweifel Exitcode 2 statt eines falschen 0. Das ist genau
    die Näherung, die die README fuer A1c7 bereits beschreibt.

    Nur lesend.
    """
    client = client or _client()
    # **Die Adressschwelle**, nicht die Kontoschwelle (A1c10). Vor dieser
    # Karte stand hier `_max_versuche()` und damit 5 — dieselbe Zahl, an der
    # auch gesperrt wird. Mit getrennten Schwellen waere das die dritte
    # Kopie derselben Wahrheit und damit garantiert irgendwann die falsche.
    schwelle = _max_versuche("ip")

    # Fall 1 — die Adresse ist gesperrt. Der Sperrschluessel liegt genau
    # einmal im Keyspace (bereichsuebergreifend, Modulkopf, A1c2), also je
    # Adresse und nicht je Bereich.
    im_weg = _sperr_hash_anteile(client)

    # Fall 2 — der Zaehler steht auf der Schwelle. Je Bereich ein Key;
    # dieselbe Adresse in mehreren Bereichen ist dieselbe Adresse und wird
    # deshalb **einmal** gezaehlt.
    for bereich in BEREICHE:
        # Der Anteil ist der **nackte Hash** — dieselbe Form wie im
        # Sperrpfad, damit die beiden Mengen ueberlappen koennen. Ein
        # `ip:`-Rest im Anteil waere die ganze Vereinigung wertlos: die
        # Mengen kaemen nie zur Deckung, und eine Adresse, die gesperrt
        # **und** auf der Schwelle ist, wuerde zweimal gezaehlt. Genau das
        # ist gemessen worden (Test `…zaehlt_einmal`).
        praefix = f"{_zaehler_praefix(bereich)}ip:"
        for schluessel in _scan_texte(client, f"{praefix}*"):
            hash_anteil = schluessel[len(praefix) :]
            if hash_anteil and _gelesen(client, schluessel) >= schwelle:
                im_weg.add(hash_anteil)

    return len(im_weg)


def _sperr_dauer(client: Any, sperr_key: str) -> int:
    """Dauer der aktuellen Sperre mit Backoff — verdoppelt je Stufe, gedeckelt.

    Ohne Backoff reicht ein Rhythmus von `Sperrzeit` Sekunden fuer einen
    endlosen Durchlauf: alle 5 Minuten ein Versuch, 12 Versuche pro Stunde
    und ueber Nacht ein vollstaendiger Durchlauf. Jeder weitere Versuch
    waehrend einer Sperr verdoppelt die naechste Sperrzeit (bis zur Deckel),
    sodass der Durchlauf exponentiell unattraktiv wird.

    Die Stufe selbst liegt in Redis (Praefix `:stufe:`) und ueberlebt damit
    auch einen Worker-Neustart. Sie wird nur zurueckgesetzt, wenn die
    Sperrzeit tatsaechlich abgelaufen ist — nicht bei jedem Login, sonst
    koennte ein Angreifer mit einem einzigen gültigen (z. B. gestohlenen)
    Passwort den Backoff zuruecksetzen und im Rhythmus weiterlaufen.
    """
    stufen_key = f"{sperr_key}:stufe"
    stufe = _gelesen(client, stufen_key)
    grund = _sperrzeit()
    gedeckelt = grund * _backoff_max_faktor()
    # `min` als Deckel auf die Exponent-Stufe: die Sperrzeit waechst
    # exponentiell, aber nicht unbegrenzt — nach 8 Stufen ist sie das
    # `login_sperre_max_faktor`-Fache der Grunddauer und bleibt dort.
    dauer = grund * (2 ** min(stufe, _BACKOFF_MAX_EXPONENT))
    return int(min(dauer, gedeckelt))


# Deckel der Backoff-Kurve als Potenz von 2. 2^8 = 256, das verhindert einen
# Overflow, wenn `stufe` durch Manipulation hochlaeuft.
_BACKOFF_MAX_EXPONENT = 8


def _backoff_max_faktor() -> int:
    """Deckel der Backoff-Kurve aus den Settings (>= 1, Default 16)."""
    return max(1, int(settings.login_sperre_max_faktor))


def pruefe_und_merke(
    user: str | None,
    ip: str | None,
    client: Any = None,
    bereich: str = BEREICH_LOGIN,
) -> tuple[bool, str]:
    """Prueft die Sperre und zaehlt den Versuch. **ABNAHMESCHNITTSTELLE.**

    Rueckgabe `(erlaubt, grund)`:
      * `erlaubt=True`  — der Versuch darf geprueft werden.
      * `erlaubt=False` — gesperrt. `grund` ist `"benutzer"` oder `"ip"` und
        dient NUR der internen Diagnose/Auditierung; nach aussen wird daraus
        nichts.

    Ablauf pro Versuch:
      1. Sperre pruefen (bereichsuebergreifend, siehe Modulkopf). Gesperrt ->
         zurueck, **nicht** gezaehlt (die Sperrzeit laeuft ja schon, ein
         weiterer Versuch soll sie nur verlaengern).
      2. Zaehler erhoehen (mit TTL = Sperrzeit als Fenstergroesse). Der
         Zaehler gehoert zum `bereich` — Login und CalDAV zaehlen getrennt.
      3. Ueberschreitet einer die Schwelle: Sperre setzen (TTL = Backoff-
         Dauer), Zaehler auf 0 zurueck, zurueckgeben.

    DIE SCHWELLE HAENGT AN DER ART (Karte A1c10): 5 am Konto, 25 an der
    Adresse. Vorher galt eine Zahl fuer beide, und die war an der Adresse
    der Grund fuer den Betriebsausfall. Ausserdem erzeugt `_kennungen()`
    fuer eine **eigene** Adresse (privat/Loopback/link-local) gar keine
    Kennung — sie wird also weder gezaehlt noch gesperrt. Beides ist
    `_max_versuche(art)` bzw. `_ist_eigene_adresse()` zu verdanken: zwei
    Funktionen, zwei Orte, keine Kopien.

    Aufrufer (in dieser Reihenfolge, siehe `api/auth.py::login`):
      * `allowed=False` -> **denselben** `AuthenticationError` werfen wie bei
        einem falschen Passwort, aber vorher die Zeit mit dem Dummy-Hash
        verbrauchen, damit die Sperre nicht an der Antwortzeit hängt.
      * `allowed=True`  -> normal pruefen; bei Erfolg `entlaste(user, ip)`.

    CalDAV (Karte A1c2) ruft exakt diese Funktion auf, mit
    `bereich=BEREICH_CALDAV` — gleicher Store, gleiche Schwelle, gleiche
    Backoff-Kurve, keine zweite Implementierung.

    AUFRÄUMWEG FUER ALLE BEREICHE — siehe `zuruecksetzen_alles()`.

    Wer gesperrt ist, kommt derzeit nur über die Zeit wieder herein. Ist der
    einzige Administrator selbst gesperrt, gibt es niemanden, der das auf
    löst — und einen Passwort-Reset gibt es bewusst nicht. Das ist im Betrieb
    ein Ausfall, kein Schutz. Der manuelle Aufraehrweg liegt deshalb in EINER
    oeffentlichen Funktion: **`zuruecksetzen_alles(user)`**. Sie leert Zaehler
    UND Sperre in *allen* bekannten Bereichen — die Folgekarte muss weder
    `BEREICH_LOGIN`/`BEREICH_CALDAV` kennen noch eine Liste pflegen, und eine
    dritte Benutzeroberflaeche wird nicht stillschweigend vergessen. Fuer den
    Notfallweg reicht die Kennung: der Aufrufer gibt die Adresse an, die der
    Administrator eingetippt hat, und der Store leitet daraus dieselben
    Schluessel ab wie der Anmeldepfad. Nichts wird geraten, nichts geraten
    werden *muessen*.
    """
    client = client or _client()
    kennungen = _kennungen(user, ip, bereich)
    if not kennungen:
        # Weder Benutzer noch IP bekannt — nichts zu zaehlen, nichts zu
        # sperren. Ein Aufruf ganz ohne Kontext darf keinen gemeinsam
        # genutzten Zaehler verbrauchen.
        return True, ""

    for art, _zaehler, sperr_key in kennungen:
        if client.exists(sperr_key):
            # `client` ist hier derselbe Stub; kein zweiter Roundtrip noetig,
            # `_sperr_dauer` liest nur die Stufe fuer die Verlaengerung.
            _verlaengere_sperre(client, sperr_key)
            return False, _grund(art)

    for art, zaehler_key, sperr_key in kennungen:
        schwelle = _max_versuche(art)
        client.incr(zaehler_key)
        # TTL = Sperrzeit: das ist das FENSTER, in dem die Versuche gezaehlt
        # werden. Ohne TTL waeren die Fehlversuche ewig gespeichert und
        # jemand, der langsam genug bleibt, wuerde irgendwann trotzdem
        # gesperrt — die Sperre muessen wir selbst steuern, nicht der Zufall.
        client.expire(zaehler_key, _sperrzeit())

        # `>` und nicht `>=`: `login_max_versuche=5` heisst "5 Fehlversuche
        # sind erlaubt, der 6. wird gesperrt" — so, wie es Frappes
        # `max_consecutive_login_failures` auch zaehlt. Wer die Schwelle auf
        # 1 stellt, sperrt damit sofort beim ersten Fehlversuch.
        #
        # **Die Schwelle haengt an der Art** (A1c10): Konto 5, Adresse 25.
        # Frueher stand hier EINE Zahl fuer beides, und die war an der
        # Adresse genau die Katastrophe, die die Karte behebt.
        if _gelesen(client, zaehler_key) > schwelle:
            _setze_sperre(client, zaehler_key, sperr_key)
            return False, _grund(art)

    return True, ""


def _verlaengere_sperre(client: Any, sperr_key: str) -> None:
    """Verlaengert eine bestehende Sperre um die (verdoppelte) Backoff-Dauer.

    Jeder weitere Versuch waehrend der Sperr setzt die Ablaufzeit neu — mit
    dem Faktor der aktuellen Stufe. Ein Angreifer, der alle 10 Sekunden
    klopft, haelt sich damit nicht nur draussen, er verliessert sich selbst
    in eine immer laengere Sperre. Genau das ist der Zweck des Backoffs.
    """
    if not client.exists(sperr_key):
        return
    dauer = _sperr_dauer(client, sperr_key)
    client.set(sperr_key, str(int(dauer)), ex=dauer)
    _erhoehe_stufe(client, sperr_key, dauer)


def _erhoehe_stufe(client: Any, sperr_key: str, dauer: int) -> None:
    """Zaehlt die Backoff-Stufe hoch — **mit** TTL.

    Ohne TTL waechst der Keyspace unbegrenzt: jeder jemals gesperrte
    Benutzer und jede IP hinterliesse einen Key FUER IMMER. Das ist im Live-
    Test aufgefallen (`ttl` stand auf -1) und waere bei einer Gemeinde mit
    wechselnden Angreifer-IPs ein echtes Leck.

    Die Stufe lebt jetzt so lange wie die Sperre selbst und faellt danach auf
    0 zurueck. Das ist gewollt: nach dem Ende einer Sperrserie beginnt die
    naechste Serie wieder bei der Grunddauer. Wer sich an einem Tag
    vertippt, wird nicht mit einer 80-Minuten-Sperre bestraft.
    """
    stufen_key = f"{sperr_key}:stufe"
    client.incr(stufen_key)
    client.expire(stufen_key, max(int(dauer), _sperrzeit()))


def _setze_sperre(client: Any, zaehler_key: str, sperr_key: str) -> None:
    """Setzt die Sperre, zaehlt die Backoff-Stufe hoch und leert den Zaehler."""
    dauer = _sperr_dauer(client, sperr_key)
    client.set(sperr_key, str(int(dauer)), ex=dauer)
    _erhoehe_stufe(client, sperr_key, dauer)
    # Der Fehlversuchszaehler des ausloesenden Bereichs beginnt nach der
    # Sperr neu. Sonst waere der Benutzer direkt nach dem Ablaufen der Sperr
    # schon wieder bei der Schwelle und kaeme nie hinein.
    client.delete(zaehler_key)


def entlaste(
    user: str | None,
    ip: str | None,
    client: Any = None,
    bereich: str = BEREICH_LOGIN,
) -> None:
    """Setzt Zaehler und Sperre nach einem **erfolgten** Zugang zurueck.

    Ohne das waere ein Benutzer, der sich zweimal vertippt und sich dann
    richtig anmeldet, kurz danach ausgesperrt. Aufgerufen wird NUR nach
    bestandenem Erfolgspfad (gueltiges Passwort, aktiviertes Konto) — ein
    Angreifer kann sich die Sperre also nicht durch Raten wegkaufen.

    Zwei Dinge werden geloescht, aus zwei verschiedenen Gruenden:

      * der **Zaehler des Bereichs**, in dem der Erfolg passierte — wer
        sich am Kalender anmeldet, hat nichts darueber gesagt, wie viele
        Fehlversuche er im Browser gemacht hat;
      * die **Sperre** — und die ist bereichsuebergreifend. Eine Sperre, die
        der Login gesetzt hat, sperrt auch den Kalender; sie muss deshalb
        durch einen Erfolg in **beiden** Bereichen geloescht werden, sonst
        waere ein Benutzer, den ein Angreifer per IP gesperrt hat, dauerhaft
        draussen, auch wenn er sich am Kalender korrekt anmeldet.

    Der IP-Zaehler wird mit zurueckgesetzt: dieselbe IP, dieselbe Person
    hinter dem Rechner. (Ein Angreifer, der EIN gueltiges Passwort hat,
    gewinnt damit genau einen Zaehler zurueck — vertretbar, denn er hat
    das Passwort bereits.)
    """
    client = client or _client()
    for _art, zaehler_key, sperr_key in _kennungen(user, ip, bereich):
        client.delete(zaehler_key)
        client.delete(sperr_key, f"{sperr_key}:stufe")


def zaehler_stand(
    user: str | None,
    ip: str | None,
    client: Any = None,
    bereich: str = BEREICH_LOGIN,
) -> dict[str, int]:
    """Liest beide Zaehler OHNE sie zu veraendern. Fuer Tests/Diagnose.

    Liest den Zaehler des angegebenen `bereich` — die Sperre ist ja global
    (siehe Modulkopf) und laesst sich ohnehin nur ueber `ist_gesperrt`
    abfragen.

    Der Rueckgabewert enthaelt absichtlich **keinen** Schluessel: wer diesen
    Wert in ein Log schreibt, hat keine Adressen und keine IPs ausgegeben.
    """
    client = client or _client()
    stand = {"benutzer": 0, "ip": 0, "benutzer_ttl": 0, "ip_ttl": 0}
    for art, zaehler_key, _sperr in _kennungen(user, ip, bereich):
        if art == "u":
            stand["benutzer"] = _gelesen(client, zaehler_key)
            stand["benutzer_ttl"] = int(_bis(client, zaehler_key))
        else:
            stand["ip"] = _gelesen(client, zaehler_key)
            stand["ip_ttl"] = int(_bis(client, zaehler_key))
    return stand


def zuruecksetzen(
    user: str | None,
    ip: str | None,
    client: Any = None,
    bereich: str = BEREICH_LOGIN,
) -> None:
    """Loescht Zaehler, Sperre und Backoff-Stufe — fuer Tests und Notfall.

    NICHT Teil des Anmeldepfads. Im Betrieb loest man eine Sperre durch
    Warten (sie ist genau dafuer zeitlich begrenzt) oder durch die
    Erstinstallation, nicht ueber diesen Aufruf.
    """
    client = client or _client()
    for _art, zaehler_key, sperr_key in _kennungen(user, ip, bereich):
        client.delete(zaehler_key, sperr_key, f"{sperr_key}:stufe")


def zuruecksetzen_alles(
    user: str | None,
    client: Any = None,
) -> None:
    """Loescht Zaehler, Sperre und Backoff-Stufe eines Kontos in **allen**
    Bereichen. **ABNAHMESCHNITTSTELLE FUER DEN AUFRÄUMWEG (Karte A1c6).**

    Der manuelle Aufraehrweg, wenn ein gesperrtes Konto *jetzt* freigegeben
    werden muss — insbesondere wenn der einzige Administrator selbst gesperrt
    ist (dann gibt es niemanden, der auf die Sperrzeit warten koennte, und
    einen Passwort-Reset gibt es bewusst nicht: das waere im Betrieb ein
    Ausfall, kein Schutz).

    Warum EINE Funktion und nicht zwei (`zuruecksetzen(..., bereich="login")`
    und `... bereich="caldav"`):

      * Die **Sperre** ist ohnehin bereichsuebergreifend (Modulkopf, A1c2) —
        sie liegt unter `SPERRE_PRAEFIX`, nicht im Bereichs-Praefix. Sie wird
        hier also genau einmal geloescht, egal welcher Bereich sie gesetzt hat.
      * Die **Zaehler** sind je Bereich getrennt. Sie werden hier ueber
        `BEREICHE` alle geleert, damit nach dem Aufraeumen nicht im anderen
        Zugang noch eine halbe Serie steht, die sofort wieder sperrt. Wer
        nur einen Bereich leert, raeumt die Haelfte auf und wundert sich
        ueber den naechsten 401.
      * Eine dritte Benutzeroberflaeche (es wird weitere geben) muss nur in
        `BEREICHE` eingetragen werden — hier kann sie nicht vergessen werden.

    `ip` ist bewusst **kein** Parameter: freigegeben wird, wen der
    Administrator benannt hat. Die IP-Sperre gehoert dem Absender, nicht
    dem Konto; ein Admin, der sein eigenes Konto freigibt, will nicht
    ungefragt das halbe Buero mitentsperren.

    Der Aufrufer gibt die Adresse an, die der Administrator eingetippt hat
    (`user`, optional mit `ip=None`). Die Schluessel leitet der Store daraus
    ab — **dieselbe** Normalisierung wie im Anmeldepfad (`_hash` ueber
    `user.strip().lower()`), damit die Freigabe auch dann trifft, wenn die
    Anmeldung mit `Foo@Beispiel.Org` kam. Was der Store zurueckmeldet, ist
    nur, OB etwas geloescht wurde — keine E-Mail, kein Klartext, kein
    Bestand. Das ist Absicht: die Zuordnung entsteht aus der vom
    Administrator genannten Adresse, nicht aus einem Blick in den Keyspace.

    `client` ist wieder der Test-Stub; im Betrieb ist es `None`.
    """
    client = client or _client()
    for bereich in BEREICHE:
        for _art, zaehler_key, sperr_key in _kennungen(user, None, bereich):
            client.delete(zaehler_key, sperr_key, f"{sperr_key}:stufe")


def gib_bericht(user: str | None, ip: str | None = None, client: Any = None) -> dict[str, int]:
    """Was waere jetzt zu loeschen — **rein lesend**, ohne irgendetwas zu tun.

    Gehoert zum manuellen Aufraehrweg (Karte A1c6): bevor ein Werkzeug eingreift,
    will es sagen koennen, OB es etwas zu tun gibt. Nicht der Bestand selbst,
    sondern je **Kennungsart** die Anzahl der Schluessel:

        {"u": 3, "ip": 1}   -> drei Konto-Schluessel, ein IP-Schluessel

    Warum ueberhaupt: der CLI-Notweg muss beide Faelle unterscheidbar machen —
    "Sperre fuer Login und CalDAV aufgehoben" gegenueber "war nicht gesperrt" —
    und zwar OHNE dem Aufrufer zu sagen, wie viele Fehlversuche es gab. Eine
    Zahl ueber die Konto-Art ist das Minimum an Information, das diese
    Auskunft ueberhaupt traegt; Zaehlerstände, Sperrzeiten und Trefferzahlen
    werden bewusst NICHT zurueckgegeben (Modulkopf, Enumerationsschutz).

    Die IP zaehlt nur, wenn `ip` genannt ist — sie wird nie geraten. Wer keine
    IP nennt, bekommt `{"u": n, "ip": 0}`, auch wenn unter derselben Adresse
    gerade ein Konto gesperrt waere; das ist der Unterschied zwischen "ich habe
    nachgesehen" und "ich weiss es".
    """
    client = client or _client()
    bericht: dict[str, int] = {"u": 0, "ip": 0}
    for art, zaehler_key, sperr_key in _kennungen(user, ip, BEREICH_LOGIN):
        # Ein Schluessel zaehlt als "da", wenn Zaehler ODER Sperre ODER
        # Backoff-Stufe existieren. Die Sperre ist bereichsuebergreifend und
        # liegt nur einmal im Keyspace; ein Aufrufer darf sie deshalb nicht
        # je Bereich doppelt zaehlen.
        if any(client.exists(key) for key in (zaehler_key, sperr_key, f"{sperr_key}:stufe")):
            bericht[art] = bericht.get(art, 0) + 1
    return bericht


def entsperre_konto_und_ip(
    user: str | None,
    ip: str | None = None,
    client: Any = None,
) -> dict[str, int]:
    """Der Notfallweg: loest Konto **und** IP in allen Bereichen.

    Rueckgabe ist derselbe Bericht wie `gib_bericht` — diesmal fuer den Stand
    **vor** dem Aufraeumen, damit der Aufrufer sagen kann, ob es etwas zu tun
    gab. Die Identitaet des Kontos entsteht aus dem, was der Aufrufer genannt
    hat; sie wird nicht aus dem Keyspace erschlossen.

    Warum die IP ein eigener, ausdruecklicher Parameter ist und kein
    Mitloeschen im Hintergrund: an einer IP haengen **alle** Konten desselben
    Anschlusses. Eine Gemeinde hat typischerweise einen Internetanschluss —
    wer eine IP freigibt, entsperrt damit potenziell das halbe Buero. Das ist
    eine Entscheidung des Aufrufers und keine stillschweigende Nebenwirkung
    seines Auftrags. Der Web-Weg nimmt darum `ip=None` und loest NUR das Konto
    (die Entscheidung aus A1c2 bleibt dort unangetastet); die CLI muss es
    anbieten koennen, weil im Notfall niemand mehr wartet.

    `ip=None` verhaelt sich wie `zuruecksetzen_alles(user)` plus Bericht — der
    Aufraehrweg bleibt damit fuer beide Wege derselbe Code.
    """
    bericht = gib_bericht(user, ip, client)
    loesche = client or _client()
    for bereich in BEREICHE:
        for _art, zaehler_key, sperr_key in _kennungen(user, ip, bereich):
            loesche.delete(zaehler_key, sperr_key, f"{sperr_key}:stufe")
    return bericht


def _grund(art: str) -> str:
    """Kurzes Kuerzel, welcher Zaehler ausgeloest hat (nur intern/Log)."""
    return {"u": "benutzer", "ip": "ip"}.get(art, art)


# Der Audit-Eintrag schreibt keinen Klartextnamen — siehe
# `api/auth.py::login`. Hier steht bewusst nur, dass es passiert ist.
def logge_gesperrt(grund: str, benutzer_pseudo: str | None = None, bereich: str = BEREICH_LOGIN) -> None:
    """Logzeile fuer einen abgewiesenen Versuch — nur die Tatsache.

    `grund` ist `"benutzer"`/`"ip"`, `benutzer_pseudo` ist der
    Audit-Pseudonym-Wert (bereits ein Hash). **Niemals** die E-Mail, das
    Passwort, `sid` oder ein CSRF-Token hier hinein.

    `bereich` steht in der Meldung, weil die Sperre bereichsuebergreifend
    ist: nur so laesst sich spaeter sagen, WO der Angriff lief.
    """
    logger.warning(
        "Anmeldeversuch abgewiesen (Sperre aktiv, Bereich=%s, Grund=%s).",
        bereich or BEREICH_LOGIN,
        grund or "unbekannt",
    )
    if benutzer_pseudo:
        logger.debug("Login-Sperre fuer Pseudonym %s.", benutzer_pseudo)


__all__ += [
    "logge_gesperrt",
    "_hash",
    "_key_benutzer",
    "_key_ip",
    "_zaehler_praefix",
    "_limit_key",
    "_werkzeug_name",
    "_max_versuche",
    "_ist_eigene_adresse",
]
