"""Der Notweg: gesperrte Konten ohne Web-Login freigeben (Karte A1c6).

Einstieg fuer

    docker compose exec app python -m diakronos_app.loginversuche --entsperren <user>

Der `__main__`-Block in `loginversuche.py` ruft `main()` hier auf. Die Logik
liegt in dieser Datei, damit `loginversuche.py` der reine Store bleibt — dort
gehoert nichts hinein, was HTTP oder `argparse` kennt.

WARUM ES DIESEN WEG GIBT
------------------------
Der Web-Endpunkt `api/entsperren.py` setzt eine Admin-Sitzung voraus. Ist der
**einzige** Administrator selbst gesperrt, gibt es niemanden, der ihn bedienen
kann — und auf die Sperrzeit warten kann auch niemand, weil niemand an sie
herankommt. Genau das ist der Ausfall, den diese Karte schliesst. Dieser Weg
braucht: keine Sitzung, keine Rolle, kein HTTP, kein Passwort. Nur Redis und
den Benutzernamen, den man eingibt.

DIE IP IST DER PUNKT, AN DEM DIE WEB-OBERFLAECHE ZU KURZ GREIFT
----------------------------------------------------------------
`zuruecksetzen_alles(user)` leert **nur das Konto**; die IP-Sperre bleibt. Fuer
den Web-Weg ist das richtig und bleibt unangetastet (Entscheidung aus A1c2:
wer ein Konto freigibt, will nicht ungefragt das halbe Buero ueber denselben
Gemeindesanschluss mitsperren).

Fuer den Notweg waere das die Sackgasse. Eine Gemeinde hat typischerweise
**einen** Internetanschluss, alle Benutzer teilen sich `REMOTE_ADDR`, und der
Admin sitzt hinter derselben Adresse wie der Angreifer. Dann hat der
**IP-Zaehler** ausgeloest, nicht der Benutzerzaehler: `zuruecksetzen_alles`
liefert dann "Konto frei, IP gesperrt", und jede Anmeldung bleibt 401. Genau
das ist die Messung aus der Gegenprobe des Orchestrators.

Deshalb kann `--ip` die IP mitfreigeben — und deshalb ist das **kein** stilles
Mitloeschen: der Aufruf sagt vorher im Klartext, dass das **alle** Konten
hinter derselben Adresse betrifft, und verlangt `--bestaetigen`. Ohne dieses
Flag passiert nichts, damit ein Skript, das die Frage nicht beantworten kann,
nicht ungefragt das halbe Buero freigibt.

WARUM ES KEIN `--mit-ip` GIBT
-----------------------------
Eine fruehere Fassung hatte `--mit-ip` ("die IP dieses Aufrufs mitfreigeben")
und wollte sie aus dem Store erraten. Das war eine erfundene Annahme: die
Schluessel im Redis sind gesalzen gehasht, es gibt keinen Klartext, und
`pruefe_und_merke` merkt sich die IP **nicht**. Die Shell im Container hat
ohnehin eine Container-IP und nicht die, unter der der Admin gesperrt wurde.
Ein `--mit-ip` haette also immer "Adresse nicht ermittelbar" gesagt oder —
schlimmer — eine geratenen geloescht. Der Schluss: **die Adresse wird
gefragt**, nicht geraten. Dafuer steht `--ip <adresse>`.

SICHERHEIT IM DETAIL
--------------------
* **Kein Passwort im Befehl.** Dieser Befehl entsperrt; er setzt kein
  Passwort. Es gibt kein `--passwort`, und es wird keins angenommen. Ein neues
  Passwort ist eine andere Karte.
* **Keine E-Mail und keine IP in der Ausgabe.** "Sperre fuer Login und CalDAV
  aufgehoben" statt "anna@example.org freigegeben". Die Konsole ist fuer
  Support-Faelle da und darf nicht zur Adressliste werden; der Audit-Eintrag
  traegt Pseudonyme, die Konsole denselben Standard.
* **Nur im Container.** Kein Port, kein ENV-Schalter, kein Router-Eintrag.
  Wer Zugang zum Container hat, hat ohnehin Shell auf der Maschine; die
  Sperre ist kein Geheimnis, sondern ein Zeitfenster.
* **Exitcode.** `0` heisst: es steht **keine Sperre mehr im Weg**, nicht
  bloss "das Konto ist frei". Das ist ein Unterschied, den die Konto- und
  die IP-Sperre getrennt erzwingen: das Konto kann frei sein und die
  Anmeldung trotzdem 401 geben, weil die **Adresse** weiter gesperrt ist
  (siehe oben). Wer auf `0` wartet — ein Skript, ein Health-Check — will
  wissen, ob die Anmeldung durchgeht, und nicht, ob ein Schluessel geloescht
  wurde. Steht noch eine IP-Sperre im Weg, ist das der Exitcode `2`
  ("Frage an den Menschen"), nicht `0`. Fuer einen unbekannten Benutzer,
  eine leere Angabe, widerspruechliche Schalter oder ein Redis ohne
  Antwort: **Exitcode != 0**, damit ein Skript nicht weiterlaeuft und denkt,
  es haette freigegeben. Auch das gilt hier: eine fehlende Antwort aus dem
  Store ist keine Entwarnung, sondern eine offene Frage.
"""

from __future__ import annotations

import argparse
import logging
import sys

logger = logging.getLogger("diakronos_app.loginversuche")

EXIT_OK = 0
EXIT_FEHLER = 1
EXIT_FRAGE = 2


# ── Hilfen ───────────────────────────────────────────────────────────────────


def _pseudo(wert: str) -> str:
    """Pseudonym einer Kennung fuer Ausgabe und Audit — `sha256:<hex>`.

    Dieselbe Form wie `api/auth.py::_pseudo` und
    `api/audit_policy/anonymize.py::_hash_identifier`, damit ein Eintrag aus
    dem Login, einer aus der Freigabe und einer aus dem DSGVO-Nachtjob nicht
    unterscheidbar sind.
    """
    from diakronos_app.api.audit_policy.anonymize import _hash_identifier

    return _hash_identifier(str(wert or "").strip().lower()) or "unbekannt"


def _konto_existiert(benutzer: str) -> bool:
    """Gibt es das Konto? — aus der Datenbank, nicht aus dem Redis.

    Der Store kann nur sagen, ob Schluessel stehen, nicht ob es das Konto
    gibt. Fuer die Fehlermeldung ("unbekannter Benutzer") und den Exitcode
    wird deshalb die **Datenbank** gefragt: eine Freigabe, die ins Leere
    laeuft, soll man unterscheiden koennen.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import User

    sess = SessionLocal()
    try:
        return sess.query(User).filter(User.name == benutzer.strip()).first() is not None
    finally:
        sess.close()


def _bereiche_text() -> str:
    """Die Bereichsnamen lesbar fuer den Support-Fall.

    Die `BEREICHE` sind Speicher-Namen (`"login"`, `"caldav"`) — in einer
    Fehlermeldung an der Konsole liest sich das nicht wie eine
    Benutzeroberflaeche. `BEREICH_ANZEIGE` traegt die lesbaren Namen; fuer
    einen Bereich, der dort (noch) nicht steht, bleibt der Rohname sichtbar
    statt still zu verschwinden.
    """
    from diakronos_app.frappe_compat.loginversuche import BEREICHE, BEREICH_ANZEIGE

    return " und ".join(BEREICH_ANZEIGE.get(name, name) for name in BEREICHE)


# ── Die Ausgabe ──────────────────────────────────────────────────────────────


def _sag_aufgehoben(benutzer: str, ip: str | None) -> None:
    zeile = (
        f"Sperre fuer {_bereiche_text()} aufgehoben "
        f"(Konto {_pseudo(benutzer)}"
    )
    if ip:
        zeile += f", zusaetzlich die IP {_pseudo(ip)}"
    print(zeile + ").")
    if ip:
        print(
            "Hinweis: mit der IP sind auch alle anderen Konten hinter "
            "derselben Adresse wieder durchgangig."
        )


def _sag_nichts_zu_tun(benutzer: str) -> None:
    print(f"War nicht gesperrt (Konto {_pseudo(benutzer)}).")


def _frage_ip(ip: str) -> None:
    print(
        f"Achtung: --ip loest die Sperre der Adresse {ip} mit auf.\n"
        "Das betrifft ALLE Konten hinter dieser Adresse — in einer Gemeinde\n"
        "typischerweise das ganze Buero ueber den gemeinsamen Anschluss.\n"
        "\n"
        "Wirklich freigeben? Dann erneut ausfuehren mit --bestaetigen:",
        file=sys.stderr,
    )


# ── Der Weg ──────────────────────────────────────────────────────────────────


def _audit(benutzer: str, bericht: dict[str, int], ip: str | None) -> None:
    """Audit-Eintrag — Pseudonyme, dasselbe Muster wie der Web-Weg.

    `actor` ist hier **leer**, und das ist der einzige ehrliche Wert:
    `audit_log.actor` ist ein echter Fremdschluessel auf `user.name`
    (siehe `models/diakonos.py::AuditLog`). Es gibt hier keine Sitzung und
    damit keinen Benutzer, der als Akteur eingetragen werden koennte. Eine
    erfundene Identitaet einzutragen waere doppelt falsch: sie zeigte
    einen Menschen, den es nicht gibt, und der Eintrag faege am
    Fremdschluessel scheitern — die Freigabe waere erfolgt und der
    Nachweis weg, ohne dass jemand etwas bemerkte.

    Wer freigegeben hat, steht deshalb im Text — pseudonymisiert, wie
    der Zielname. Wer Zugang zum Container hat, hat ohnehin Shell auf der
    Maschine; die Sperre ist kein Geheimnis, sondern ein Zeitfenster.
    """
    try:
        from diakronos_app.frappe_compat.api_helpers import _create, _now
        from diakronos_app.frappe_compat.loginversuche import BEREICHE

        ziel = _pseudo(benutzer)
        getan = "ja" if (bericht["u"] or bericht["ip"]) else "nein"
        _create(
            "Audit Log",
            {
                "zeitstempel": _now(),
                "action_typ": "Sonstiges",
                # Leer, nicht "Administrator": `actor` ist ein
                # Fremdschluessel auf `user.name` (siehe Docstring).
                "actor": None,
                "target_doctype": "User",
                "target_name": ziel,
                "begruendung": (
                    "Konto manuell freigegeben (CLI-Notweg, ohne Sitzung): "
                    f"Bereiche={', '.join(BEREICHE)}, "
                    f"hat_gesperrt_gehabt={getan}, "
                    f"ip_mitgeloest={'ja' if ip else 'nein'}, "
                    f"Ziel={ziel}"
                ),
                "ip_address": _pseudo(ip) if ip else None,
                "notification_gesendet": 0,
            },
        )
    except Exception as exc:  # noqa: BLE001 — die Freigabe darf nicht an der Logbuchhaltung haengen
        logger.warning(
            "Audit-Eintrag fuer CLI-Freigabe nicht moeglich: %s", exc.__class__.__name__
        )


def _status(benutzer: str) -> int:
    """Nur nachsehen, nichts loeschen."""
    from diakronos_app.frappe_compat import loginversuche as lv

    benutzer = str(benutzer or "").strip()
    if not benutzer:
        print("FEHLER: kein Benutzername angegeben.", file=sys.stderr)
        return EXIT_FEHLER

    try:
        bericht = lv.gib_bericht(benutzer, None)
    except Exception as exc:  # noqa: BLE001 — "nicht gesperrt" waere hier eine Luege
        print(
            f"FEHLER: der Sperrstore ist nicht erreichbar ({exc.__class__.__name__}). "
            "Ohne Antwort aus dem Store waere 'nicht gesperrt' eine Luege.",
            file=sys.stderr,
        )
        return EXIT_FEHLER

    if bericht["u"] or bericht["ip"]:
        print(f"Gesperrt (Konto {_pseudo(benutzer)}).")
    else:
        print(f"Nicht gesperrt (Konto {_pseudo(benutzer)}).")
    return EXIT_OK


def _entsperren(benutzer: str, ip: str | None, bestaetigt: bool) -> int:
    """Der eigentliche Aufraehrweg. Gibt einen Exitcode zurueck."""
    from diakronos_app.frappe_compat import loginversuche as lv

    benutzer = str(benutzer or "").strip()
    if not benutzer:
        print(
            "FEHLER: kein Benutzername angegeben.\n"
            "  Aufruf: python -m diakronos_app.loginversuche --entsperren <user>",
            file=sys.stderr,
        )
        return EXIT_FEHLER

    if not _konto_existiert(benutzer):
        print(
            f"FEHLER: kein Konto mit diesem Namen ({_pseudo(benutzer)}).\n"
            "  Der Benutzername ist die E-Mail-Adresse aus dem Anmeldeformular.",
            file=sys.stderr,
        )
        return EXIT_FEHLER

    # Die IP **vor** dem Loeschen bestaetigen lassen. Wer eine IP freigibt,
    # entsperrt moeglicherweise das halbe Buero; das muss der Aufrufer wissen,
    # bevor etwas passiert, nicht danach.
    if ip and not bestaetigt:
        _frage_ip(ip)
        return EXIT_FRAGE

    try:
        bericht = lv.gib_bericht(benutzer, ip or None)
    except Exception as exc:  # noqa: BLE001 — ein Store ohne Antwort ist kein "nichts zu tun"
        print(
            f"FEHLER: der Sperrstore ist nicht erreichbar ({exc.__class__.__name__}). "
            "Es wurde nichts freigegeben.",
            file=sys.stderr,
        )
        return EXIT_FEHLER

    lv.entsperre_konto_und_ip(benutzer, ip or None)
    _audit(benutzer, bericht, ip)

    if bericht["u"] or bericht["ip"]:
        _sag_aufgehoben(benutzer, ip)
    else:
        _sag_nichts_zu_tun(benutzer)

    # NACH der Freigabe nachsehen, ob die Anmeldung wirklich durchgeht.
    #
    # Das ist der Unterschied zwischen "die Schluessel sind geloescht" und
    # "die Person kann sich wieder anmelden" — und es sind nicht dasselbe.
    # Der haeufigste Fall: gesperrt war die **Adresse**, nicht das Konto
    # (eine Gemeinde hat einen Internetanschluss, alle Benutzer teilen
    # sich REMOTE_ADDR). Dann ist das Konto nach diesem Aufruf frei, die
    # IP bleibt gesperrt, und jede Anmeldung gibt weiter 401. Ohne diese
    # Pruefung meldet der Notweg "aufgehoben", der Betreiber probiert es
    # aus, es geht nicht, und er steht genau da, wo er vorher stand —
    # mit der zusaetzlichen Annahme, es gabe nur einen Weg.
    return _ip_hinweis(ip)


def _ip_hinweis(ip: str | None) -> int:
    """Sagt ehrlich, was nach der Konto-Freigabe **noch** sperrt.

    Nach dem Aufraehrweg des Kontos kann die **Adresse** weiter sperren. Das
    ist kein Restfehler, sondern der Regelfall hinter einem gemeinsamen
    Internetanschluss: der Benutzerzaehler und der IP-Zaehler werden getrennt
    gezaehlt, und welcher zuerst ausloest, haengt davon ab, von wo angegriffen
    wurde. Trifft es die IP, ist das Konto nach diesem Aufruf frei, die Adresse
    bleibt im Weg, und jede Anmeldung gibt weiter 401 — das ist der Messfall
    aus der Gegenprobe.

    Ohne diese Pruefung meldet der Notweg "aufgehoben", der Betreiber
    probiert es aus, es geht nicht, und er steht genau da, wo er vorher
    stand — mit der zusaetzlichen Annahme, es gabe nur einen Weg.

    WAS "STEHT NOCH IM WEG" HEISST (Karte A1c8)
    -------------------------------------------
    Die Frage ist **nicht** "steht ein Sperrschluessel im Store", sondern
    "gibt der naechste Anmeldeversuch dieser Adresse 401". Der Unterschied ist
    der haeufigste Fall ueberhaupt: EIN Benutzer, fuenf erlaubte
    Fehlversuche vom gemeinsamen Anschluss. Der Benutzerzaehler sperrt, der
    IP-Zaehler bleibt **auf der Schwelle** stehen, und im Store steht
    **keine** IP-Sperre. `zaehle_gesperrte_ips()` sagt da 0 — und der Befehl
    meldete daraufhin "alles erledigt" mit Exitcode 0, waehrend die naechste
    Anmeldung 401 gab. Genau das ist die Luege, die A1c7 abstreift, eine
    Ebene tiefer.

    Deshalb fragt dieser Aufruf `zaehle_adressen_im_weg()`: das zaehlt
    Adressen mit Sperre **und** mit Zaehler auf der Schwelle. Ein Zaehler
    kann nie ueber der Schwelle stehen — `pruefe_und_merke` sperrt bei
    `zaehler > schwelle` und loescht ihn dabei —, also ist `zaehler >=
    schwelle` exakt die Vorhersage "der naechste Versuch sperrt".

    **Exitcode:** ist die IP nicht mit freigegeben worden und steht noch eine
    Adresse im Weg, ist der Notfall **nicht** geloest. Dann Exitcode 2, damit
    ein Skript nicht "erfolgreich" weitermeldet, was beim naechsten
    Anmeldeversuch wieder 401 gibt. Dasselbe Argument wie beim unbekannten
    Benutzer. Der Alltagsfall (wer sich dreimal vertippt hat) bleibt still —
    die Grenze sitzt auf der Schwelle, nicht darueber.

    **Exitcode 0 heisst hier: es steht nichts mehr im Weg.** Nicht "das
    Konto ist frei" — das ist nach diesem Aufruf immer wahr, egal wie es
    ausgegangen ist. Ein Skript, das auf `0` wartet, will wissen, ob die
    Anmeldung wieder durchgeht.

    Und wenn der Store **keine Antwort** gibt, ist die Frage nicht
    beantwortet: "ich habe nicht nachgesehen" ist nicht "es ist nichts im
    Weg". Dann Exitcode 1 mit dem Hinweis, dass die Konto-Freigabe
    erfolgt ist, ihr Ende aber unbekannt ist — dieselbe Regel wie an
    jeder anderen Stelle dieser Datei.

    Warum das ein **Hinweis** ist und kein Fehler: der Store kann nicht
    sagen, **welche** Adresse gesperrt ist — die Schluessel sind gesalzen
    gehasht, und `pruefe_und_merke` merkt sich die Herkunft nicht. Ob die
    gesperrte Adresse die des Aufrufers ist, weiss nur der Betreiber
    (Router/NAT). Deshalb wird gemeldet, nicht geraten: mit einer
    geratenen IP wuerde der Notweg ins Leere laufen und niemand wuesste es.
    """
    from diakronos_app.frappe_compat import loginversuche as lv

    if ip:
        # Die IP wurde ausdruecklich mit freigegeben — nichts offen.
        return EXIT_OK

    try:
        offen = lv.zaehle_adressen_im_weg()
    except Exception as exc:  # noqa: BLE001 — "ich habe nicht nachgesehen" ist nicht "nichts im Weg"
        # Die Konto-Sperre ist zu diesem Zeitpunkt bereits geloest, und das
        # wird auch gemeldet. Was der Befehl **nicht** weiss, ist, ob noch
        # etwas im Weg steht. Ohne Antwort aus dem Store ist die Frage
        # nicht beantwortet — die Frage, nicht der Zustand. Genau das ist
        # die Luege, die die Karte A1c7 abstreift, nur eine Ebene tiefer:
        # in der Fassung davor stand hier ein `return EXIT_OK`.
        #
        # An jeder anderen Stelle derselben Datei ist derselbe Fall genau
        # so behandelt (`_status`, `_entsperren`): Store ohne Antwort ist
        # `EXIT_FEHLER`, mit derselben Begruendung im Wortlaut. Diese eine
        # Stelle war der einzige Fail-open in der Datei.
        print(
            f"FEHLER: der Sperrstore ist nicht erreichbar ({exc.__class__.__name__}). "
            "Das Konto ist freigegeben, aber ob noch eine IP-Sperre im Weg "
            "steht, laesst sich nicht sagen.\n"
            "  Es wurde kein Erfolg gemeldet, weil ein Skript nach Exitcode 0 "
            "annimmt, dass die Anmeldung wieder durchgeht.",
            file=sys.stderr,
        )
        return EXIT_FEHLER

    if not offen:
        return EXIT_OK

    print(
        f"ACHTUNG: Das Konto ist frei, aber eine Client-Adresse steht noch im Weg.\n"
        f"  Zwei Zustaende sind das, und welcher vorliegt, laesst sich aus dem\n"
        f"  Store nicht unterscheiden:\n"
        f"    GESPERRT       die Adresse traegt eine Sperre.\n"
        f"    AUF DER SCHWELLE  die Adresse hat so viele Fehlversuche, dass der\n"
        f"                   naechste Versuch sie sperrt.\n"
        f"  Beide machen die Anmeldung zu einem 401 — nicht das Konto. Bei einem\n"
        f"  gemeinsamen Internetanschluss trifft das das ganze Buero.\n"
        f"  Der Exitcode 2 sagt: die Anmeldung kann noch scheitern. Nur ein\n"
        f"  Anmeldeversuch sagt, ob sie es wirklich tut.\n"
        f"  Zweiter Schritt:\n"
        f"    --entsperren <user> --ip <adresse> --bestaetigen\n"
        f"  Das gibt alle Konten hinter dieser Adresse frei, deshalb fragt\n"
        f"  es der Befehl nach.\n"
        f"  (Welche Adresse es ist laesst sich aus dem Sperrstore nicht auslesen —\n"
        f"  sie steht im Router/NAT des Anschlusses.)",
        file=sys.stderr,
    )
    return EXIT_FRAGE


# ── Argumente ────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m diakronos_app.loginversuche",
        description=(
            "Gibt ein durch Brute-Force-Schutz gesperrtes Konto frei. Ohne "
            "HTTP, ohne Rolle, ohne Sitzung — der Notweg fuer den Fall, dass "
            "der einzige Administrator selbst gesperrt ist."
        ),
        epilog=(
            "Beispiele:\n"
            "  --entsperren anna@example.org\n"
            "  --entsperren anna@example.org --ip 203.0.113.5 --bestaetigen\n"
            "  --entsperren anna@example.org --status\n"
            "\n"
            "Exitcodes:\n"
            "  0  Es steht nichts mehr im Weg: das Konto ist frei und keine\n"
            "     Client-Adresse sperrt oder steht auf der Schwelle. Nur dann\n"
            "     geht die Anmeldung wieder durch. Auch dann, wenn das Konto\n"
            "     schon frei war.\n"
            "  1  Fehler: unbekannter Benutzer, leere Angabe, widerspruechliche\n"
            "     Schalter, oder der Sperrstore antwortet nicht.\n"
            "  2  Offen bzw. nicht gelöst: --ip ohne --bestaetigen (es passiert\n"
            "     nichts), oder das Konto ist frei, aber eine Client-Adresse\n"
            "     steht noch im Weg — gesperrt oder mit dem Fehlversuchszaehler\n"
            "     auf der Schwelle. Der naechste Anmeldeversuch kann dann\n"
            "     weiterhin 401 geben; ein Anmeldeversuch zeigt es.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--entsperren", metavar="<user>",
                   help="Benutzername (= E-Mail) des gesperrten Kontos freigeben.")
    p.add_argument("--ip", metavar="<adresse>", default=None,
                   help="Zusaetzlich die Sperre dieser IP loesen. Wirkt auf ALLE "
                        "Konten hinter derselben Adresse; verlangt --bestaetigen. "
                        "Loest auch einen Fehlversuchszaehler auf der Schwelle, "
                        "der die naechste Anmeldung sonst sperren wuerde.")
    p.add_argument("--bestaetigen", action="store_true",
                   help="Die Freigabe einer IP bestaetigen. Ohne dieses Flag "
                        "passiert bei --ip nichts.")
    p.add_argument("--status", action="store_true",
                   help="Nur anzeigen, ob das Konto gesperrt ist — aendert nichts.")
    return p


def main(argv: list[str] | None = None) -> int:
    """Einstieg fuer `python -m diakronos_app.loginversuche`."""
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    if not args.entsperren:
        print(
            "FEHLER: nichts zu tun — es wird --entsperren <user> erwartet.\n"
            "  Hilfe: python -m diakronos_app.loginversuche --help",
            file=sys.stderr,
        )
        return EXIT_FEHLER

    if args.bestaetigen and not args.ip:
        print(
            "FEHLER: --bestaetigen ohne --ip ergibt keinen Sinn.\n"
            "  Es bestaetigt nur die Freigabe einer IP-Adresse.",
            file=sys.stderr,
        )
        return EXIT_FEHLER

    if args.status:
        return _status(args.entsperren)

    return _entsperren(args.entsperren, args.ip, args.bestaetigen)


if __name__ == "__main__":  # pragma: no cover — Einstieg `python -m …cli_entsperren`
    sys.exit(main())
