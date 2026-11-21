"""``Nextcloud`` — Ablage ueber WebDAV (SPEICHER-1, Entscheidung Manuel 17.11.).

Diakronos haelt Dateien dann NICHT mehr im eigenen Volume, sondern in einem
Ordner der Gemeinde-Nextcloud. Der Zugang ist ein **App-Passwort** eines
Dienstkontos (``NEXTCLOUD_BENUTZER`` + ``NEXTCLOUD_APP_PASSWORT``) — kein
Kontopasswort, nichts mit 2FA, nichts, was beim ersten Verdacht gesperrt wird.

Adressen
--------
WebDAV-Basis ist ``<NEXTCLOUD_URL>/remote.php/dav/files/<BENUTZER>/``, darunter
kommt ``NEXTCLOUD_ORDNER`` (Default ``/Diakronos``) und dann der Schluessel::

    https://cloud.example.org/remote.php/dav/files/diakronos/Diakronos/<schluessel>

Die Adresse wird ausschliesslich HIER gebaut. Kein Aufrufer bildet eine
WebDAV-URL, und keine WebDAV-Adresse verlaesst je das Backend in Richtung
Browser (Kartenvorgabe 4): das Ausliefern bleibt bei Diakronos, inklusive
Rechtepruefung.

Verhalten im Fehlerfall
-----------------------
``401``/``403``  -> :class:`NichtErlaubt` — Zugangsdaten falsch oder Recht
                    fehlt. Keine Wiederholung (ein falsches Passwort wird
                    durch Wiederholen nicht richtig).
``404``          -> :class:`NichtGefunden` (nur beim Lesen; beim Loeschen
                    ``False``, beim Schreiben wird der Elternordner angelegt).
``507``          -> :class:`AblageFehler` mit „Speicher voll“. **Keine**
                    Wiederholung: der Speicher wird in den naechsten 2
                    Sekunden nicht groesser, und der Upload war teuer.
``429``          -> Wiederholung mit Wartezeit (``Retry-After``, sonst Backoff).
``5xx``/Netz/Zeit -> :class:`SpeicherNichtErreichbar` nach
                    ``NEXTCLOUD_VERSUCHE`` Versuchen.

Zeitlimits
----------
Zwei getrennte Budgets, weil zwei verschiedene Dinge passieren:
``NEXTCLOUD_TIMEOUT_SEKUNDEN`` (Default 10) fuer Abfragen (Kopf, Groesse,
Ordnerliste), ``NEXTCLOUD_TRANSFER_TIMEOUT_SEKUNDEN`` (Default 300) fuer
Dateien bis 50 MB (Audio-Material). Ein 300-Sekunden-Limit fuer ein HEAD waere
ein haengender Benutzer-Request; ein 10-Sekunden-Limit fuer 50 MB ueber eine
langsame Leitung waere ein garantierter Abbruch.

Was hier NICHT passiert
-----------------------
Kein Zwischenspeicher, keine Warteschlange, kein Hintergrundabgleich: schlaegt
Nextcloud fehl, meldet die Ablage das SOFORT und der Aufrufer entscheidet.
Ein „spaeter nachreichen“ waere ein zweiter, unsichtbarer Datenbestand — genau
das Problem, das diese Karte loest.
"""

from __future__ import annotations

import logging
import re
import time
from typing import IO, Any, Callable, Iterable, Iterator
from urllib.parse import quote

import httpx

from diakronos_app.speicher.basis import (
    BLOCKGROESSE,
    AblageFehler,
    Basis,
    NichtErlaubt,
    Quelle,
    SpeicherNichtErreichbar,
    werfe_nicht_gefunden,
)
from diakronos_app.speicher.schluessel import elternordner, normalisiere

logger = logging.getLogger("diakronos_app.speicher.nextcloud")

__all__ = ["Nextcloud", "NextcloudZugang"]


class _DateiStrom(httpx.SyncByteStream):
    """Ein Datenstrom, der beim SENDEN aus der Datei gelesen wird.

    Fuer den PUT eines grossen Dumps: ``httpx`` holt die Bloecke erst, wenn
    der Transport sie schreibt. Damit liegt nie mehr als ein Block im
    Speicher — unabhaengig von der Groesse der Datei.

    ``spulen`` setzt die Datei auf ihre STARTposition zurueck (nicht auf 0!);
    es wird nur dann benutzt, wenn die Wiederholung wirklich etwas bringt
    (siehe ``_schreibe_strom``). Ist der Strom schon verbraucht und laesst
    sich nicht zuruecksetzen, ist eine Wiederholung nicht moeglich
    (``False``).

    Die Startposition ist der Stand der Datei, als dieser Strom entstand
    (SPEICHER-3, Punkt 1). ``laenge`` ist ``ende - start`` — die Bytes, die
    uebertragen werden, sind also ``[start, start + laenge)``. Ein
    ``seek(0)`` beim Spulen schickte dagegen ``[0, laenge)``: bei einem
    bereits angelesenen Strom (Spool nach einem Kopf, Datei hinter einem
    Vorspann) landete damit stillschweigend der FALSCHE Inhalt unter dem
    richtigen Namen — der zweite PUT ist der, der zaehlt.
    """

    def __init__(self, datei: IO[bytes], laenge: int, start: int = 0) -> None:
        self._datei = datei
        self.laenge = laenge
        #: Erste Position, die dieser Strom sendet (``tell()`` bei Entstehung).
        self.start = max(0, int(start))
        self._gelesen = 0
        self._fertig = False

    def __iter__(self) -> Iterator[bytes]:
        # Kein ``while True`` um ``read()``: der Strom wird genau EINMAL
        # durchlaufen, die Laenge ist bekannt (``Content-Length``).
        while self._gelesen < self.laenge:
            block = self._datei.read(min(BLOCKGROESSE, self.laenge - self._gelesen))
            if not block:
                # Die Datei ist kuerzer als angekuendigt (waehrend des
                # Uploads beschnitten?) — abbrechen statt weniger Bytes zu
                # senden und dem Server eine falsche Laenge zu melden.
                self._fertig = True
                raise AblageFehler(
                    "Die Quelldatei ist waehrend der Uebertragung kuerzer "
                    "geworden — der Upload ist unvollstaendig."
                )
            self._gelesen += len(block)
            yield block
        self._fertig = True

    def spulen(self) -> bool:
        """Datei auf ihre STARTposition zurueck; ``False``, wenn das nicht geht.

        ``self.start`` statt ``0`` (SPEICHER-3, Punkt 1): die Laenge des
        Stroms ist ``ende - start``, gesendet wurden ``[start, ende)``. Ein
        Sprung auf 0 schickte beim zweiten Versuch ``[0, laenge)`` — bei
        einem Strom, der nicht am Anfang stand, also fremde Bytes
        (Kopf/Vorspann der Datei) unter dem richtigen Namen.
        """
        try:
            self._datei.seek(self.start)
        except (OSError, ValueError, AttributeError):
            return False
        self._gelesen = 0
        self._fertig = False
        return True

    #: ``httpx`` fragt die Laenge NICHT ab (``content=`` mit ``SyncByteStream``
    #: ergibt keinen ``Content-Length``). ``schreiben`` setzt die Kopfzeile
    #: deshalb selbst — der Wert MUSS zu dem passen, was hier herauskommt.
    def __len__(self) -> int:
        return self.laenge


#: Statuscodes, die eine Wiederholung NICHT besser machen.
_ENDGUELTIG = frozenset({400, 401, 403, 405, 409, 413, 415, 507})

#: Statuscodes, nach denen ein erneuter Versuch sinnvoll ist.
_WIEDERHOLBAR = frozenset({429, 500, 502, 503, 504})


class NextcloudZugang:
    """Zugangsdaten und Adressbau (EINE Wahrheit fuer die WebDAV-URL).

    Das Passwort steht als Attribut im Speicher (es muss bei jeder Anfrage in
    die Kopfzeile) — es wird aber NIE protokolliert, NIE in eine Ausnahme
    geschrieben und NIE nach aussen gegeben: ``__repr__`` ist ueberschrieben,
    und Fehlermeldungen nennen nur Status und Aktion.
    """

    def __init__(
        self,
        url: str,
        benutzer: str,
        passwort: str,
        ordner: str = "/Diakronos",
        *,
        timeout: float = 10.0,
        transfer_timeout: float = 300.0,
        versuche: int = 3,
    ) -> None:
        self.url = str(url or "").strip().rstrip("/")
        self.benutzer = str(benutzer or "").strip()
        # Review-Punkt 11: wie ``settings.nextcloud_konfiguriert`` — ein
        # Passwort mit umgebenden Leerzeichen (Kopierfehler aus der
        # Nextcloud-Oberflaeche) muss trotzdem passen, und reiner Leerraum
        # ist kein Passwort (sonst meldete die Ablage „eingerichtet“ und
        # bekäme bei jeder Anfrage ein 401).
        self._passwort = str(passwort or "").strip()
        self.ordner = _ordner_normalisieren(ordner)
        self.timeout = float(timeout)
        self.transfer_timeout = float(transfer_timeout)
        self.versuche = max(1, int(versuche))

    # ── Pruefung ───────────────────────────────────────────────────────────
    def fehlende_angaben(self) -> list[str]:
        """Welche Pflichtangaben fehlen? (Namen, keine Werte!)"""
        fehlt = []
        if not self.url:
            fehlt.append("NEXTCLOUD_URL")
        if not self.benutzer:
            fehlt.append("NEXTCLOUD_BENUTZER")
        if not self._passwort:
            fehlt.append("NEXTCLOUD_APP_PASSWORT")
        return fehlt

    @property
    def vollstaendig(self) -> bool:
        return not self.fehlende_angaben()

    @property
    def passwort(self) -> str:
        """Das App-Passwort — nur fuer die Kopfzeile, nie fuer Protokolle."""
        return self._passwort

    # ── Adressen ───────────────────────────────────────────────────────────
    def basis(self) -> str:
        """``https://host/remote.php/dav/files/<benutzer>/<ordner>`` (ohne /)."""
        benutzer = quote(self.benutzer, safe="")
        return f"{self.url}/remote.php/dav/files/{benutzer}{self.ordner}"

    def datei_url(self, schluessel: str) -> str:
        """Vollstaendige WebDAV-Adresse einer Datei (je Segment kodiert)."""
        sauber = normalisiere(schluessel)
        teile = "/".join(quote(teil, safe="") for teil in sauber.split("/"))
        return f"{self.basis()}/{teile}"

    def ordner_url(self, ordner: str = "") -> str:
        """Vollstaendige Adresse eines Ordners (``""`` = Basisordner)."""
        if not ordner.strip("/"):
            return self.basis()
        sauber = normalisiere(ordner)
        teile = "/".join(quote(teil, safe="") for teil in sauber.split("/"))
        return f"{self.basis()}/{teile}"

    def __repr__(self) -> str:  # pragma: no cover — Diagnose
        return f"<NextcloudZugang {self.url!r} benutzer={self.benutzer!r} ordner={self.ordner!r}>"


def _ordner_normalisieren(ordner: str) -> str:
    """``Nextcloud_ordner`` -> ``/Diakronos`` (fuehrender Schraegstrich, keiner am Ende).

    Leer = Wurzel des Benutzers (``""``). Ein Ordnername mit ``..`` oder
    Steuerzeichen ist ein Konfigurationsfehler und wird sofort abgewiesen —
    er wuerde sonst bei JEDER Anfrage in der URL landen.
    """
    roh = str(ordner or "").strip().strip("/")
    if not roh:
        return ""
    teile = [teil for teil in roh.split("/") if teil]
    for teil in teile:
        if teil in (".", "..") or "\\" in teil or any(ord(z) < 32 for z in teil):
            raise ValueError(
                f"Ungueltiger NEXTCLOUD_ORDNER: {teil!r} — nur normale Ordnernamen erlaubt."
            )
    return "/" + "/".join(teile)


class Nextcloud(Basis):
    """WebDAV-Ablage in einer Nextcloud (App-Passwort, MKCOL bei Bedarf).

    ``client`` ist eine Naht fuer den Test: ein ``httpx.Client`` mit
    ``MockTransport`` (kein Netz, kein echter Nextcloud-Server). Im Betrieb
    entsteht der Client hier — EINER je Instanz, weil jede Anfrage sonst eine
    neue TLS-Verbindung aufbauen muesste.
    """

    name = "nextcloud"

    def __init__(
        self,
        zugang: NextcloudZugang | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._zugang = zugang
        self._client = client
        self._angelegte_ordner: set[str] = set()
        # Wartezeiten der Wiederholung (Sekunden). Im Test auf 0 gesetzt,
        # damit die Fehlerfaelle nicht drei Sekunden schlafen.
        self.wartezeiten: tuple[float, ...] = (0.5, 1.0, 2.0)

    # ── Zugang und Client ──────────────────────────────────────────────────
    @property
    def zugang(self) -> NextcloudZugang:
        if self._zugang is None:
            from diakronos_app.settings import settings

            self._zugang = NextcloudZugang(
                settings.nextcloud_url,
                settings.nextcloud_benutzer,
                settings.nextcloud_app_passwort_effektiv,
                settings.nextcloud_ordner,
                timeout=settings.nextcloud_timeout_sekunden,
                transfer_timeout=settings.nextcloud_transfer_timeout_sekunden,
                versuche=settings.nextcloud_versuche,
            )
        return self._zugang

    def _http(self) -> httpx.Client:
        if self._client is None:
            zugang = self.zugang
            self._client = httpx.Client(
                auth=(zugang.benutzer, zugang.passwort),
                timeout=httpx.Timeout(zugang.timeout, read=zugang.transfer_timeout),
                follow_redirects=False,
                # trust_env=False: kein Proxy aus der Umgebung, keine
                # .netrc-Anmeldung — der WebDAV-Zugang kommt AUSSCHLIESSLICH
                # aus den Einstellungen (App-Passwort). Ein .netrc im
                # Container wuerde sonst still die Zugangsdaten ersetzen,
                # und das ist bei einem Dienstkonto genau der Fehler, den
                # niemand findet. (Genau das passierte im ersten Testlauf:
                # eine ~/.netrc im Testcontainer ueberschrieb die
                # Basic-Auth-Kopfzeile mit einer fremden Anmeldung.)
                trust_env=False,
            )
        return self._client

    def schliessen(self) -> None:
        if self._client is not None:
            self._client.close()

    # ── Anfrage mit Wiederholung ───────────────────────────────────────────
    def _anfrage(
        self,
        methode: str,
        url: str,
        *,
        inhalt: bytes | IO[bytes] | httpx.SyncByteStream | None = None,
        kopf: dict[str, str] | None = None,
        transfer: bool = False,
        erlaube_404: bool = False,
        erlaube_status: tuple[int, ...] = (),
        aktion: str = "Zugriff",
        strom: bool = False,
        wiederholbar: Callable[[], bool] | None = None,
        timeout: float | None = None,
        versuches: int | None = None,
    ) -> httpx.Response:
        """Eine WebDAV-Anfrage; wiederholt 429/5xx/Netzfehler.

        ``erlaube_404`` gibt die 404-Antwort zurueck, statt
        ``NichtGefunden`` zu werfen (Loeschen und Existenzpruefung wollen
        gerade „nein“ wissen). ``erlaube_status`` sind weitere Statuscodes, die
        als Antwort durchgereicht werden (MKCOL: 405 = „gibt es schon“).

        ``timeout``/``versuches`` sind die Notbremse fuer Aufrufer, die nicht
        warten duerfen (``loeschen_mit_zeitlimit``, CHAT-12a/R1): gesetzt,
        ueberschreiben sie das Zeitlimit aus den Einstellungen bzw. die Zahl
        der Versuche — ``versuches=1`` heisst genau EIN Netzaufruf, ohne
        Wartezeiten dazwischen.

        ``strom=True`` ist fuer Anfragen mit KOERPER (GET): ``client.send(...,
        stream=True)`` laesst ``httpx`` die Antwort NICHT vorab einlesen — der
        Aufrufer bekommt die Bytes erst, wenn er sie abholt (Review-Punkt 1:
        vorher las ``client.request`` eine 10-MB-Datei komplett, bevor der
        erste Block ankam). **Die Antwort gehoert dann dem Aufrufer** und muss
        geschlossen werden (``schliessen``/``close``) — bei einer
        Fehlerantwort besorgt das diese Funktion selbst.
        """
        zugang = self.zugang
        fehlt = zugang.fehlende_angaben()
        if fehlt:
            raise NichtErlaubt(
                "Die Nextcloud-Ablage ist nicht eingerichtet (fehlt: "
                + ", ".join(fehlt)
                + ")."
            )
        client = self._http()
        # ``timeout`` als Parameter (Notbremse fuer ``loeschen_mit_zeitlimit``)
        # sticht das Zeitlimit aus den Einstellungen.
        if timeout is not None:
            zeitlimit = max(0.1, float(timeout))
        else:
            zeitlimit = zugang.transfer_timeout if transfer else zugang.timeout
        anzahl_versuche = (zugang.versuche if versuches is None
                           else max(1, int(versuches)))
        letzte: Exception | None = None
        for versuch in range(1, anzahl_versuche + 1):
            try:
                if strom:
                    antwort = client.send(
                        client.build_request(
                            methode, url, content=inhalt, headers=kopf or {},
                            timeout=zeitlimit,
                        ),
                        stream=True,
                    )
                else:
                    antwort = client.request(
                        methode,
                        url,
                        content=inhalt,
                        headers=kopf or {},
                        timeout=zeitlimit,
                    )
            except httpx.TimeoutException as fehler:
                letzte = fehler
                logger.warning(
                    "Nextcloud: %s Zeitueberschreitung (Versuch %d/%d).",
                    aktion, versuch, anzahl_versuche,
                )
            except httpx.HTTPError as fehler:
                letzte = fehler
                logger.warning(
                    "Nextcloud: %s Netzfehler %s (Versuch %d/%d).",
                    aktion, type(fehler).__name__, versuch, anzahl_versuche,
                )
            else:
                status = antwort.status_code
                if status < 400 or status == 404 and erlaube_404:
                    return antwort
                if status in erlaube_status:
                    return antwort
                # Ab hier ist die Antwort ein Fehler: einen offenen Strom
                # sofort schliessen, sonst bleibt die Verbindung haengen.
                if strom:
                    antwort.close()
                if status in (401, 403):
                    raise NichtErlaubt(
                        f"Die Nextcloud hat {aktion} verweigert "
                        f"(HTTP {status}) — bitte Zugangsdaten und "
                        "Ordnerrechte pruefen."
                    )
                if status == 507:
                    raise AblageFehler(
                        "Die Nextcloud meldet keinen freien Speicher "
                        "(HTTP 507) — bitte dort Platz schaffen."
                    )
                if status == 404:
                    raise werfe_nicht_gefunden(normalisiere(_schluessel_rest(url)))
                if status in _ENDGUELTIG:
                    raise AblageFehler(
                        f"Die Nextcloud hat {aktion} abgelehnt (HTTP {status})."
                    )
                if status in _WIEDERHOLBAR:
                    letzte = AblageFehler(f"HTTP {status}")
                    logger.warning(
                        "Nextcloud: %s HTTP %d (Versuch %d/%d).",
                        aktion, status, versuch, anzahl_versuche,
                    )
                    # Review R1/2: NICHT warten, wenn kein Versuch mehr folgt.
                    # Sonst schlief ein Aufruf mit ``versuches=1`` (der Weg mit
                    # Zeitlimit im Request) erst noch bis zu 5 s (Retry-After)
                    # bzw. die Backoff-Wartezeit ab — das Zeitlimit gilt nur
                    # fuer den Netzaufruf, nicht fuer das Warten danach.
                    #
                    # CHAT-12a-3, Punkt 5: nur EINMAL warten. Vorher schlief
                    # dieser Zweig erst nach ``Retry-After`` und danach noch
                    # einmal die Backoff-Zeit (die Wartephase unten) — zusammen
                    # bis zu 5 s + Backoff fuer einen einzigen Versuch. Jetzt
                    # gilt das Maximum aus beiden, genau einmal. Das Zurueck-
                    # setzen der Quelle (unten, ``wiederholbar``) darf dabei
                    # NICHT entfallen: ohne das Zuruecksetzen der Quelle
                    # (``spulen``, springt auf die STARTPOSITION) schickte der
                    # zweite Versuch 0 Bytes.
                    if versuch < anzahl_versuche:
                        self._warte(versuch, antwort.headers.get("Retry-After"))
                        if wiederholbar is not None and not wiederholbar():
                            raise SpeicherNichtErreichbar(
                                f"Die Nextcloud ist nicht erreichbar ({aktion}); "
                                "die Quelle laesst sich fuer eine Wiederholung "
                                "nicht zuruecksetzen."
                            )
                        # Warten ist erledigt — die gemeinsame Wartephase
                        # unten ueberspringen.
                        continue
                else:  # unbekannter 4xx: wiederholen bringt nichts
                    raise AblageFehler(
                        f"Die Nextcloud hat {aktion} abgelehnt (HTTP {status})."
                    )
            if versuch < anzahl_versuche:
                if wiederholbar is not None and not wiederholbar():
                    # Die Quelle ist schon verbraucht und laesst sich nicht
                    # zuruecksetzen (z. B. ein Strom ohne ``seek``): ein
                    # zweiter Versuch schickte nur den Rest der Datei.
                    raise SpeicherNichtErreichbar(
                        f"Die Nextcloud ist nicht erreichbar ({aktion}); die "
                        "Quelle laesst sich fuer eine Wiederholung nicht "
                        "zuruecksetzen."
                    )
                self._warte(versuch, None)
        raise SpeicherNichtErreichbar(
            f"Die Nextcloud ist nicht erreichbar ({aktion} nach "
            f"{anzahl_versuche} Versuchen)."
        )

    def _warte(self, versuch: int, retry_after: str | None) -> None:
        """Einmal warten: das MAXIMUM aus ``Retry-After`` und Backoff.

        CHAT-12a-3, Punkt 5: Vorher gewann ``Retry-After`` und der Backoff
        entfiel — der Aufrufer wartete fuer diesen Versuch also genau einmal,
        aber nie die längere der beiden Zeiten. (Der Fehler lag im
        Aufrufpfad: nach ``Retry-After`` schlief der 429/5xx-Zweig noch einmal
        den Backoff, insgesamt bis zu 5 s + Backoff.) Hier steht die eine
        Wahrheit: beide Quellen werden bestimmt, geschlafen wird EINMAL, mit
        der grösseren Zeit — nie addiert.
        """
        sekunden = 0.0
        if retry_after:
            try:
                roh = float(str(retry_after).strip())
            except ValueError:
                roh = 0.0
            if roh > 0:
                sekunden = min(roh, 5.0)
        werte = self.wartezeiten
        if werte:
            backoff = werte[min(max(versuch, 1) - 1, len(werte) - 1)]
            sekunden = max(sekunden, backoff)
        if sekunden > 0:
            time.sleep(sekunden)

    # ── Ordner (MKCOL) ─────────────────────────────────────────────────────
    def _ordner_anlegen(self, ordner: str) -> None:
        """Legt ``ordner`` samt Eltern an (MKCOL; 405 = gibt es schon).

        **Angefangen wird beim BASISORDNER** (``NEXTCLOUD_ORDNER``): auf einer
        frischen Nextcloud existiert ``/Diakronos`` nicht, und WebDAV legt bei
        einem PUT keine fehlenden Ordner an — ohne diesen Schritt endete der
        erste Upload in einem 409. ``elternordner("x")`` liefert ``[]``, der
        Basisordner selbst kommt deshalb aus ``_basis_teile()``.
        """
        for teil in self._alle_ebenen(ordner):
            if teil in self._angelegte_ordner:
                continue
            antwort = self._anfrage(
                "MKCOL",
                self._ordner_url_von_wurzel(teil),
                erlaube_404=False,
                erlaube_status=(405, 301),
                aktion=f"Ordner {teil!r} anlegen",
            )
            if antwort.status_code in (201, 200, 405, 301):
                # 405 Method Not Allowed = existiert bereits (RFC 4918, 9.3.1),
                # 301 = manche Server leiten auf den Ordner mit Schraegstrich.
                self._angelegte_ordner.add(teil)

    def _alle_ebenen(self, ordner: str) -> list[str]:
        """Alle anzulegenden Ebenen (Basisordner + ``ordner``), Wurzel-relativ.

        Eine Liste, in der die Ebenen von oben nach unten stehen und keine
        doppelt vorkommt: bei ``NEXTCLOUD_ORDNER=/Diakronos`` und dem
        Schluessel ``Diakronos/x.png`` ist das genau ``["Diakronos"]``.
        """
        basis = self.zugang.ordner.strip("/")
        rest = "/".join(teil for teil in ordner.strip("/").split("/") if teil)
        gesamt = f"{basis}/{rest}" if basis and rest else (basis or rest)
        return _ebenen(gesamt)

    def _basis_teile(self) -> list[str]:
        """Die Ebenen des Basisordners, von der BENUTZERWURZEL abwaerts.

        Nur fuer Diagnose/Status gebraucht; angelegt wird ueber
        :meth:`_alle_ebenen` (dort zusammen mit dem Schluessel, ohne
        Doppelungen). Leer (Wurzel des Benutzers) -> ``[]``.
        """
        return _ebenen(self.zugang.ordner.strip("/"))

    def _ordner_url_von_wurzel(self, ordner: str) -> str:
        """WebDAV-Adresse eines Ordners relativ zur Wurzel des Benutzers."""
        benutzer = quote(self.zugang.benutzer, safe="")
        basis = f"{self.zugang.url}/remote.php/dav/files/{benutzer}"
        roh = str(ordner or "").strip("/")
        if not roh:
            return basis
        teile = "/".join(quote(teil, safe="") for teil in roh.split("/"))
        return f"{basis}/{teile}"

    # ── Schreiben ──────────────────────────────────────────────────────────
    def schreiben(self, schluessel: str, daten: bytes | IO[bytes]) -> int:
        """Datei anlegen/ersetzen. Rueckgabe: geschriebene Bytes.

        ``bytes`` gehen als fertiger Koerper hinaus (kleine Dateien: Bilder,
        JSON). Ein **Datenstrom** wird dagegen als Strom gesendet
        (``_DateiStrom``): ``httpx`` holt die Bloecke beim Schreiben, es liegt
        nie mehr als ein Block im Speicher. Das ist die Voraussetzung dafuer,
        dass ein Dump von mehreren GB in die Nextcloud geht — frueher wurde
        der Strom in einen ``bytearray`` gesammelt und oberhalb von
        ``MAX_ZWISCHENPUFFER`` (200 MB) abgelehnt.
        """
        sauber = normalisiere(schluessel)
        ordner = "/".join(sauber.split("/")[:-1])
        if isinstance(daten, (bytes, bytearray, memoryview)):
            roh = bytes(daten)
            self._schreibe_bytes(sauber, ordner, roh)
            return len(roh)
        return self._schreibe_strom(sauber, ordner, daten)

    def _schreibe_strom(self, sauber: str, ordner: str, daten: IO[bytes]) -> int:
        """PUT aus einem Datenstrom — mit bekannter Laenge, ohne Zwischenpuffer.

        Die Laenge kommt aus der DATEI (``seek`` ans Ende), nicht aus einem
        Einlesen: ``Content-Length`` muss stehen, sonst schickt ``httpx``
        ``Transfer-Encoding: chunked``, und manche WebDAV-Server (und
        Reverse-Proxys davor) nehmen das nicht an.

        **Wiederholung nur mit zurueckspulbarer Quelle:** Ein 5xx/429/Netz-
        fehler kann den Strom schon halb verbraucht haben. Eine echte Datei
        laesst sich zuruecksetzen; geht das nicht (Pipe, Socket, ein Strom
        ohne ``seek``), wird NICHT wiederholt — sonst landete eine halbe
        Datei unter dem richtigen Namen.

        **Zurueckgesetzt wird auf die STARTPOSITION, nicht auf 0**
        (SPEICHER-3, Punkt 1): ``laenge`` ist ``ende - position``. Steht ein
        uebergebener Strom nicht am Anfang (Spool nach einem gelesenen Kopf,
        Datei hinter einem Vorspann) und scheitert der erste PUT, schickte
        ein ``seek(0)`` die Bytes ``[0, laenge)`` statt ``[position, ende)``
        — stillschweigend der falsche Inhalt unter dem richtigen Namen.
        """
        laenge = _strom_laenge(daten)
        if laenge is None:
            raise AblageFehler(
                "Die Datei hat keine feststellbare Groesse — ohne Laenge "
                "kann sie nicht in die Nextcloud uebertragen werden."
            )
        # Die Startposition VOR dem ersten Lesen festhalten: sie ist der
        # Bezugspunkt, zu dem ``spulen`` zurueckkehrt.
        strom = _DateiStrom(daten, laenge, start=_strom_start(daten))
        kopf = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(laenge),
        }
        for runde in (1, 2):
            self._ordner_anlegen(ordner)
            try:
                # KEIN ``strom=True`` (SPEICHER-2b, Punkt 2): das gehoert zu
                # einem GET, dessen Antwort der Aufrufer selbst liest. Bei
                # einem PUT ist die Antwort leer und wird nirgends
                # geschlossen — jede Antwort belegte damit eine Verbindung im
                # Pool, bis nach genug Uploads kein Platz mehr war
                # (``httpx`` meldete dann „no free connections“). Ohne die
                # Option liest ``httpx`` die Antwort ein und gibt die
                # Verbindung nach dem Lesen selbst zurueck.
                self._anfrage(
                    "PUT",
                    self.zugang.datei_url(sauber),
                    inhalt=strom,
                    kopf=kopf,
                    transfer=True,
                    aktion="Datei schreiben",
                    # Der Strom ist NACH dem Senden immer verbraucht: nur mit
                    # ``spulen`` (zurueck auf die Startposition) geht eine
                    # Wiederholung. Ohne das schickte der zweite Versuch
                    # 0 Bytes bzw. — mit ``seek(0)`` — die falschen.
                    wiederholbar=strom.spulen,
                )
                return laenge
            except AblageFehler as fehler:
                if not _ordner_fehlt(fehler) or runde == 2 or strom._fertig:
                    raise
                # Der Ordner war inzwischen weg: Cache verwerfen, einmal neu.
                for teil in self._alle_ebenen(ordner):
                    self._angelegte_ordner.discard(teil)
                logger.warning(
                    "Nextcloud: Ordner %r war nicht mehr da — wird neu angelegt.",
                    ordner,
                )
        raise AblageFehler("Die Datei konnte nicht geschrieben werden.")  # pragma: no cover

    def _schreibe_bytes(self, sauber: str, ordner: str, roh: bytes) -> None:
        """PUT mit einer zweiten Runde, wenn der Ordner inzwischen fehlt.

        **Review-Punkt 8:** ``_angelegte_ordner`` merkt sich, was WIR angelegt
        haben. Wird der Ordner serverseitig entfernt (Aufraeumen, ein Umzug in
        der Nextcloud), antwortet der PUT mit 404/409 — der Cache ist dann
        falsch. Statt den Fehler nach oben zu geben, wird der Cache fuer diesen
        Pfad verworfen und EINMAL neu angelegt.
        """
        for runde in (1, 2):
            self._ordner_anlegen(ordner)
            try:
                self._anfrage(
                    "PUT",
                    self.zugang.datei_url(sauber),
                    inhalt=roh,
                    kopf={"Content-Type": "application/octet-stream"},
                    transfer=len(roh) > 1024 * 1024,
                    aktion="Datei schreiben",
                )
                return
            except AblageFehler as fehler:
                if runde == 2 or not _ordner_fehlt(fehler):
                    raise
                # Cache fuer diesen Ordner (und seine Ebenen) verwerfen.
                for teil in self._alle_ebenen(ordner):
                    self._angelegte_ordner.discard(teil)
                logger.warning(
                    "Nextcloud: Ordner %r war nicht mehr da — wird neu angelegt.",
                    ordner,
                )

    # ── Lesen ──────────────────────────────────────────────────────────────
    def oeffnen(self, schluessel: str) -> Quelle:
        """Lese-Kontext ueber einen GESTREAMTEN GET (nichts wird vorab gelesen).

        ``BytesQuelle(antwort.content)`` waere ein voller Lesevorgang im
        Speicher — bei einer 500-MB-Audiodatei genau das, was diese Karte
        behebt. Stattdessen haengt die Antwort am Strom: ``lesen_vorn`` holt
        nur den Anfang (und bricht danach ab), ``strom`` gibt die Bloecke
        weiter. ``schliessen`` (``__exit__``) schliesst die WebDAV-Antwort.
        """
        sauber = normalisiere(schluessel)
        antwort = self._lese_get(sauber)
        return _AntwortQuelle(antwort, _laenge_der_antwort(antwort))

    def _lese_get(
        self,
        sauber: str,
        kopf: dict[str, str] | None = None,
        *,
        erlaube_status: tuple[int, ...] = (),
        erlaube_404: bool = False,
    ) -> httpx.Response:
        """Gestreamter Lese-GET mit den Kopfzeilen fuer einen STROM.

        ``Accept-Encoding: identity`` (Review Runde 4, Punkt 4): ``httpx``
        fragt sonst nach ``gzip``. Dann gilt eine ``Content-Length`` fuer den
        KOMPRIMIERTEN Koerper, waehrend ``iter_bytes`` die entpackten Bytes
        liefert — die Laenge waere falsch (und das Entpacken wuerde ausserdem
        jede Menge CPU kosten, weil Audio/Video sich nicht komprimieren
        laesst). ``identity`` heisst: die Bytes kommen so, wie sie liegen.

        ``erlaube_404`` gibt die 404-Antwort zurueck (``None`` = es wird
        ``NichtGefunden`` geworfen, das ist die Vorgabe fuer Lesen/Streamen).
        """
        zeilen = {"Accept-Encoding": "identity", **(kopf or {})}
        return self._anfrage(
            "GET",
            self.zugang.datei_url(sauber),
            kopf=zeilen,
            transfer=True,
            erlaube_404=erlaube_404,
            erlaube_status=erlaube_status,
            aktion="Datei lesen",
            strom=True,
        )

    def lesen_vorn(self, schluessel: str, anzahl: int) -> bytes | None:
        """Die ersten ``anzahl`` Bytes per gestreamtem ``Range``-GET.

        Review-Punkt 2: der Kopf zum Bestimmen des Dateityps holte vorher die
        GANZE Datei (``oeffnen`` -> ``BytesQuelle(antwort.content)``). Jetzt
        geht ``Range: bytes=0-(anzahl-1)`` mit, und es wird hoechstens
        ``anzahl`` Bytes gelesen — auch von einem Server, der ``Range``
        ignoriert (dann bricht der Lesevorgang ab und schliesst die Antwort).
        ``None`` = gibt es nicht.

        Review Runde 4, Punkt 1: bei einer LEEREN Datei ist jeder Bereich
        unerfuellbar — der Server antwortet auf ``Range: bytes=0-4095`` mit
        ``416``. Frueher fiel das durch die Fehlerbehandlung (``AblageFehler:
        HTTP 416``) und die Route machte daraus ein ``404``: die leere Datei
        war nicht auslieferbar. ``416`` heisst hier „existiert, ist aber
        leer“ -> ``b""``.
        """
        sauber = normalisiere(schluessel)
        anzahl = int(anzahl)
        if anzahl <= 0:
            return b""
        antwort = self._lese_get(
            sauber, {"Range": f"bytes=0-{anzahl - 1}"},
            erlaube_status=(416,), erlaube_404=True,
        )
        if antwort.status_code == 404:
            antwort.close()
            return None
        if antwort.status_code == 416:
            # Leere Datei: der Anfang ist leer, die Datei existiert aber.
            antwort.close()
            return b""
        gesammelt = bytearray()
        try:
            # Bewusst in kleinen Stuecken: bei einem Server, der ``Range``
            # ignoriert, soll der Abbruch nach ``anzahl`` Bytes und nicht nach
            # einem 256-KiB-Block kommen.
            for block in antwort.iter_bytes(min(anzahl, 64 * 1024)):
                gesammelt.extend(block)
                if len(gesammelt) >= anzahl:
                    break
        finally:
            antwort.close()
        return bytes(gesammelt[:anzahl])

    def strom(
        self,
        schluessel: str,
        *,
        von: int = 0,
        bis: int | None = None,
        bereich: bool | None = None,
        gesamt: int | None = None,
    ) -> tuple[Iterable[bytes], int, int]:
        """Blockweise aus der Nextcloud (echtes Streaming, Review-Punkt 1).

        ``httpx`` liest die Antwort in Stuecken (``iter_bytes``); der
        WebDAV-``Range``-Kopf geht nur mit, wenn der AUFRUFER einen Bereich
        will (Review-Punkt 8). ``bereich=False`` heisst ausdruecklich „ganze
        Datei“ — so ruft die Auslieferung ohne Client-``Range``; sie uebergibt
        dabei ``von=0, bis=gesamt-1``, was sonst wie ein ``bytes=0-N``-Wunsch
        aussaehe. ``None`` = aus ``von``/``bis`` ableiten (Vorgabe 0/``None``
        heisst „alles“).

        ``gesamt`` ist eine bereits bekannte Dateigroesse des Aufrufers (aus
        ``groesse_und_bereich``). Sie wird gebraucht, wenn die GET-Antwort
        KEINE ``Content-Length`` traegt (chunked, Proxy, HTTP/2) — sonst
        laesst sich die Groesse nur mit einer weiteren Abfrage bestimmen
        (Review Runde 4, Punkt 3).

        Der Generator schliesst die Antwort in seinem ``finally`` — auch
        wenn ``StreamingResponse`` ihn bei einem Client-Abbruch abbricht
        (``aclose``/``close`` des Generators, Review-Punkt 1).
        """
        sauber = normalisiere(schluessel)
        if bereich is None:
            # Ohne ausdrueckliche Angabe gilt: ein Teil ist verlangt, sobald
            # von/bis nicht der Vorgabe (0/None) entsprechen.
            bereich = bool(von) or bis is not None
        kopf: dict[str, str] = {}
        if bereich:
            ende = "" if bis is None else str(int(bis))
            kopf["Range"] = f"bytes={int(von or 0)}-{ende}"
        antwort = self._lese_get(
            sauber, kopf or None, erlaube_status=(206, 416), erlaube_404=True,
        )
        if antwort.status_code == 404:
            antwort.close()
            raise werfe_nicht_gefunden(sauber)
        if antwort.status_code == 416:
            antwort.close()
            return iter(()), 0, -1
        gesamt, anfang, ende = _bereich_der_antwort(
            antwort, int(von or 0), bis, bekannt=gesamt,
            quell_groesse=lambda: self.groesse(sauber),
        )
        if ende < anfang:
            # Die Datei ist zwischen Groessenabfrage und GET geschrumpft (oder
            # war leer): die Route antwortet mit 416, OHNE diesen Generator je
            # zu starten — sein ``finally`` liefe also nie. Deshalb wird die
            # Antwort hier sofort geschlossen (Review Runde 4, Punkt 2: sonst
            # bleibt die WebDAV-Verbindung offen).
            antwort.close()
            return iter(()), anfang, ende
        if bereich is False:
            # Ausdruecklich die ganze Datei: der Server hat keinen Range
            # gesehen, also kommt 200 mit allem — keine Ausschnitts-Arbeit.
            return _schliessender_strom(antwort), 0, max(gesamt - 1, -1)
        if antwort.status_code == 206:
            return _schliessender_strom(antwort), anfang, ende
        # Kein 206, obwohl ein Bereich angefragt war: der Server ignoriert
        # ``Range``. Dann wird nur der Ausschnitt geliefert (und der Rest
        # verworfen) — die Antwort ist die GANZE Datei.
        return (
            _ausschnitt_strom(antwort, int(von or 0), bis),
            anfang,
            min(ende, max(gesamt - 1, -1)),
        )

    def existiert(self, schluessel: str) -> bool:
        # ``normalisiere`` laeuft VOR dem Zugriff: ein boeser Schluessel ist
        # ein Programmfehler und wird gemeldet, nicht als „gibt's nicht“
        # verschluckt. Ein Netzfehler ebenso — wer „nicht erreichbar“ und
        # „gibt es nicht“ verwechselt, haelt eine volle Ablage fuer leer und
        # schreibt alles neu.
        #
        # Review-Punkt 10: ein ORDNER ist keine Datei. ``HEAD`` auf einen
        # Ordner antwortet bei Nextcloud mit 200 und ``Content-Type:
        # httpd/unix-directory`` — ohne die zweite Pruefung meldete
        # ``existiert("devmodus")`` True und die Ablage widerspraeche
        # ``Lokal``.
        sauber = normalisiere(schluessel)
        antwort = self._anfrage(
            "HEAD",
            self.zugang.datei_url(sauber),
            erlaube_404=True,
            aktion="Datei pruefen",
        )
        if antwort.status_code >= 400:
            return False
        return not _ist_ordner(antwort)

    def groesse(self, schluessel: str) -> int | None:
        """Groesse in Bytes (``None`` = gibt es nicht / unbekannt).

        Weg 1 ist ``HEAD`` und dessen ``Content-Length``. Antwortet der
        Server ohne Laenge (chunked, Proxy, HTTP/2) oder lehnt er ``HEAD`` ab,
        wird die Groesse per ``PROPFIND`` (``getcontentlength``, Depth 0)
        geholt — Review Runde 4, Punkt 5: vorher war die Datei dann
        „unbekannt“ und die Auslieferung endete in einem 404.
        """
        sauber = normalisiere(schluessel)
        antwort = self._anfrage(
            "HEAD",
            self.zugang.datei_url(sauber),
            erlaube_404=True,
            erlaube_status=(405, 501),
            aktion="Groesse lesen",
        )
        if antwort.status_code == 404:
            return None
        wert = antwort.headers.get("Content-Length")
        if wert is not None:
            try:
                return int(wert)
            except ValueError:
                pass
        if antwort.status_code >= 400:
            return None
        return self._groesse_per_propfind(sauber)

    def _groesse_per_propfind(self, sauber: str) -> int | None:
        """``getcontentlength`` eines einzelnen Eintrags (``Depth: 0``)."""
        antwort = self._anfrage(
            "PROPFIND",
            self.zugang.datei_url(sauber),
            kopf={"Depth": "0", "Content-Type": "application/xml"},
            inhalt=_PROPFIND_KOERPER,
            erlaube_404=True,
            aktion="Groesse lesen",
        )
        if antwort.status_code >= 400:
            return None
        return _laenge_aus_propfind(antwort.text)

    def auflisten(self, praefix: str = "") -> list[str]:
        """Alle Dateien unterhalb ``praefix`` (PROPFIND Depth: 1, je Ordner)."""
        start = normalisiere(praefix) if praefix.strip("/") else ""
        gesehen: list[str] = []
        self._sammle(start, gesehen, tiefe=0)
        return sorted(gesehen)

    def _sammle(self, ordner: str, ergebnis: list[str], tiefe: int) -> None:
        if tiefe > MAX_TIEFE:
            return
        antwort = self._anfrage(
            "PROPFIND",
            self.zugang.ordner_url(ordner),
            kopf={"Depth": "1", "Content-Type": "application/xml"},
            inhalt=_PROPFIND_KOERPER,
            erlaube_404=True,
            aktion="Ordner lesen",
        )
        if antwort.status_code == 404:
            return
        # Review-Punkt 3: Die Antwort enthaelt IMMER den abgefragten Ordner
        # selbst. Wird er nicht uebersprungen, laeuft ein gleichnamiger
        # Unterordner (``a/a``) ein zweites Mal und seine Dateien stehen
        # doppelt in der Liste — deshalb wird der Eigen-Eintrag hier anhand
        # seines VOLLEN href erkannt (nicht an einem leeren Namen).
        eigen = _href_pfad(self.zugang.ordner_url(ordner))
        for eintrag in _propfind(antwort.text):
            if eintrag.ist_eigen or not eintrag.name:
                continue
            if eigen and eintrag.pfad.rstrip("/") == eigen.rstrip("/"):
                continue
            schluessel = (
                eintrag.name.strip("/")
                if ordner == ""
                else f"{ordner}/{eintrag.name.strip('/')}"
            )
            try:
                sauber = normalisiere(schluessel)
            except Exception:  # noqa: BLE001 — fremde Eintraege ignorieren
                continue
            if eintrag.ist_ordner:
                self._sammle(sauber, ergebnis, tiefe + 1)
            else:
                ergebnis.append(sauber)

    # ── Loeschen ───────────────────────────────────────────────────────────
    def loeschen(self, schluessel: str) -> bool:
        return self._loeschen(schluessel, zeitlimit=None)

    def loeschen_mit_zeitlimit(self, schluessel: str, sekunden: float) -> bool:
        """Review R1 (CHAT-12a): Loeschen mit OBERGRENZE je Netzaufruf.

        Anders als bei ``Lokal`` gibt es hier einen Netzweg (WebDAV), und der
        darf den Aufrufer nicht aufhaengen: ein Lese-Timeout von 10 s mal drei
        Versuche (plus Wartezeiten) waere laenger als das Speichern einer
        Nachricht selbst. Deshalb:

        * **keine Wiederholung** (``versuches = 1``) — ein zweiter Versuch ist
          hier nicht noetig, weil der Minuten-Job den Auftrag ohnehin wieder
          aufnimmt (``chat_anhang_entsorgung``),
        * **EIN HTTP-Aufruf** mit ``timeout=max(0.1, sekunden)``,
        * auch der Kontroll-Blick nach einer Zeitueberschreitung
          (``_noch_da``) laeuft im selben Limit.

        Scheitert das Loeschen, wirft die Methode wie ``loeschen`` — der
        Aufrufer laesst den Auftrag dann stehen.
        """
        return self._loeschen(schluessel, zeitlimit=max(0.1, float(sekunden)))

    def _loeschen(self, schluessel: str, *, zeitlimit: float | None) -> bool:
        sauber = normalisiere(schluessel)
        try:
            antwort = self._anfrage(
                "DELETE",
                self.zugang.datei_url(sauber),
                erlaube_404=True,
                aktion="Datei loeschen",
                timeout=zeitlimit,
                versuches=1 if zeitlimit is not None else None,
            )
        except SpeicherNichtErreichbar:
            # Review-Punkt 7: Der DELETE kann den Server erreicht haben und
            # nur die ANTWORT verloren gegangen sein (Zeitueberschreitung).
            # Ein zweiter, kurzer Blick entscheidet: ist die Datei weg, war
            # das Loeschen erfolgreich — ein „nicht erreichbar“ waere hier
            # falsch und liesse den Aufrufer eine geloeschte Datei als Fehler
            # verbuchen (DSGVO-Loeschung!).
            if not self._noch_da(sauber, zeitlimit=zeitlimit):
                return True
            raise
        return antwort.status_code < 400

    def ordner_loeschen(self, schluessel: str) -> bool:
        """Einen Ordner SAMT Inhalt entfernen (WebDAV-DELETE, rekursiv).

        SPEICHER-2b, Punkt 5: ``auflisten`` liefert nur Dateien, „leere
        Ordner suchen“ konnte deshalb nie greifen. Der DELETE auf die
        ORDNER-Adresse nimmt nach RFC 4918 den ganzen Baum mit — so bleibt
        nach einem halben Loeschvorgang kein Rest stehen.

        ``False`` = der Ordner war nicht da (nichts zu tun) — dieselbe
        Sprache wie :meth:`loeschen`. Der Statuscode entscheidet, nicht ein
        Vorab-PROPFIND: der kostete bei jeder Aufbewahrung einen Aufruf je
        Sicherung.
        """
        sauber = normalisiere(schluessel)
        try:
            antwort = self._anfrage(
                "DELETE",
                self.zugang.ordner_url(sauber),
                erlaube_404=True,
                aktion="Ordner loeschen",
            )
        except SpeicherNichtErreichbar:
            # Wie oben: der DELETE kann angekommen sein, nur die Antwort ging
            # verloren. Ein PROPFIND (Depth 0) entscheidet.
            if not self._ordner_da(sauber):
                return True
            raise
        # 405 = manche Server erlauben kein DELETE auf eine Sammlung; dann
        # bleibt der Ordner stehen und der Aufrufer erfaehrt es.
        return antwort.status_code < 400

    def _ordner_da(self, sauber: str) -> bool:
        """Existiert der Ordner noch? (Nach einem abgebrochenen DELETE.)"""
        try:
            antwort = self._anfrage(
                "PROPFIND",
                self.zugang.ordner_url(sauber),
                kopf={"Depth": "0", "Content-Type": "application/xml"},
                inhalt=_PROPFIND_KOERPER,
                erlaube_404=True,
                aktion="Ordner pruefen",
            )
        except AblageFehler:
            return True
        return antwort.status_code < 400

    def _noch_da(self, sauber: str, *, zeitlimit: float | None = None) -> bool:
        """Ist die Datei noch da? (Nach einem abgebrochenen DELETE.)

        Eine kurze, einzelne Abfrage OHNE Wiederholungsschleife: hier geht es
        nur um „weg oder nicht weg“. Ist auch die Pruefung nicht erreichbar,
        gilt die Datei als noch da — dann meldet der Aufrufer den Fehler,
        statt sich auf eine unklare Lage zu verlassen.

        ``zeitlimit`` (``loeschen_mit_zeitlimit``): dieselbe Obergrenze wie
        der DELETE selbst — der Blick danach darf nicht laenger dauern als das
        Loeschen.
        """
        try:
            antwort = self._anfrage(
                "HEAD",
                self.zugang.datei_url(sauber),
                erlaube_404=True,
                aktion="Datei pruefen",
                timeout=zeitlimit,
                versuches=1 if zeitlimit is not None else None,
            )
        except AblageFehler:
            return True
        return antwort.status_code < 400

    # ── Zustand ────────────────────────────────────────────────────────────
    def gesundheit(self) -> dict[str, Any]:
        """Ein PROPFIND auf den Basisordner — erreichbar und angemeldet?

        ``erreichbar`` = angemeldet und antwortet; ``ordner_vorhanden`` = der
        Basisordner ist da. Fehlt er, ist das KEIN Fehler: ``schreiben`` legt
        ihn (samt Ebenen) beim ersten Upload per MKCOL an. Der Text sagt
        genau das, damit „nicht vorhanden“ nicht als „kaputt“ gelesen wird.
        """
        try:
            antwort = self._anfrage(
                "PROPFIND",
                self.zugang.ordner_url(""),
                kopf={"Depth": "0", "Content-Type": "application/xml"},
                inhalt=_PROPFIND_KOERPER,
                erlaube_404=True,
                aktion="Statusabfrage",
            )
        except AblageFehler as fehler:
            return {"backend": self.name, "erreichbar": False,
                    "grund": str(fehler), "ordner_vorhanden": False,
                    "ordner": self.zugang.ordner or "/",
                    "hinweis": "Die Ablage ist nicht erreichbar."}
        vorhanden = antwort.status_code < 400
        return {
            "backend": self.name,
            "erreichbar": True,
            "status": antwort.status_code,
            "ordner": self.zugang.ordner or "/",
            "ordner_vorhanden": vorhanden,
            "hinweis": (
                "Der Basisordner ist vorhanden."
                if vorhanden
                else "Der Basisordner fehlt noch — er wird beim ersten "
                     "Schreiben angelegt."
            ),
        }


#: Groesste Datei, die fuer einen Strom zwischengepuffert wird. Darueber
#: bricht ``schreiben_strom`` ab — ein 50-GB-Archiv gehoert nicht in den
#: Speicher. (Der Umzug liest ohnehin blockweise und schreibt je Datei.)
#:
#: **Seit SPEICHER-2 nicht mehr die Grenze des Uploads:** ``schreiben`` mit
#: einer Datei/Strom sendet stroemend (``_DateiStrom``) und liest die Datei
#: nie ganz ein. Der Wert bleibt als benannte Konstante stehen (Diagnose und
#: die Zusage „nichts wird zwischengepuffert“).
MAX_ZWISCHENPUFFER = 200 * 1024 * 1024


def _strom_laenge(daten: IO[bytes]) -> int | None:
    """Laenge eines Datenstroms OHNE ihn einzulesen — ``None``, wenn unbekannt.

    Reihenfolge: erst ``seek``/``tell`` (jede echte Datei), dann die
    ``os.fstat``-Groesse (auch bei einem Strom, der schon an einer Position
    steht), zuletzt ``len()`` fuer Aufrufer, die die Laenge selbst mitbringen.
    """
    try:
        position = daten.tell()
        ende = daten.seek(0, 2)
        daten.seek(position)
        return max(0, int(ende) - int(position))
    except (OSError, ValueError, AttributeError):
        pass
    try:
        import os as _os

        groesse = _os.fstat(daten.fileno()).st_size
        return max(0, int(groesse) - int(daten.tell()))
    except (OSError, ValueError, AttributeError):
        pass
    try:
        return int(len(daten))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _strom_start(daten: IO[bytes]) -> int:
    """Position, ab der der Strom sendet — ``0``, wenn nicht feststellbar.

    SPEICHER-3, Punkt 1: ``_strom_laenge`` misst ``ende - position``. Genau
    diese ``position`` muss ``_DateiStrom`` als Start merken, sonst springt
    ``spulen`` beim Wiederholen an die falsche Stelle. Ein Strom ohne
    ``tell()`` (Pipe) faengt eben bei 0 an — dort bricht die Wiederholung
    ohnehin am fehlenden ``seek`` ab.
    """
    try:
        return max(0, int(daten.tell()))
    except (OSError, ValueError, AttributeError):
        return 0


def _ebenen(ordner: str) -> list[str]:
    """Die Ebenen eines Ordners, von oben nach unten (``""`` -> ``[]``).

    ``"a/b"`` -> ``["a", "a/b"]``. Anders als ``schluessel.elternordner``
    liefert das hier AUCH die oberste Ebene (dort ist sie der Elternordner
    einer Datei und faellt weg) — beim MKCOL brauchen wir genau die.
    """
    roh = str(ordner or "").strip("/")
    if not roh:
        return []
    teile = roh.split("/")
    return ["/".join(teile[: i + 1]) for i in range(len(teile))]


def _ordner_fehlt(fehler: Exception) -> bool:
    """True, wenn der Fehler „der Elternordner fehlt“ bedeutet (404/409).

    Genau diese beiden Statuscodes beantwortet WebDAV auf einen PUT, dessen
    Elternordner es nicht (mehr) gibt. Nur dann ist ein zweiter Anlauf mit
    frischem MKCOL sinnvoll — ein 401/403/507 wird davon nicht besser.
    """
    text = str(fehler)
    return "HTTP 409" in text or "HTTP 404" in text


def _ist_ordner(antwort: httpx.Response) -> bool:
    """True, wenn die Antwort auf einen ORDNER zeigt (kein Datei-Treffer).

    Review-Punkt 9: ``text/html`` ist KEIN Ordnerbeweis — ``seite.html``
    antwortet auf ``HEAD`` mit ``Content-Type: text/html``, und die alte
    Regel haette daraus „kein Datei-Treffer“ gemacht (die Datei waere nicht
    auslieferbar gewesen). Ordner erkennt nur, was WebDAV dafuer hergibt:
    ``httpd/unix-directory`` (Nextcloud auf ``HEAD``) oder eine Antwort ohne
    jede Datei-Kennung (kein Typ, kein ETag, keine Laenge).
    """
    typ = (antwort.headers.get("Content-Type") or "").lower()
    if "httpd/unix-directory" in typ:
        return True
    # Ein Ordner hat keine Laenge in Bytes. ``Content-Length: 0`` allein ist
    # aber KEIN Beweis (leere Dateien gibt es), deshalb nur zusammen mit
    # fehlendem Typ UND fehlendem ETag.
    return not typ and "ETag" not in antwort.headers and "Content-Length" not in antwort.headers


class _AntwortQuelle(Quelle):
    """``Quelle`` direkt auf einer GESTREAMTEN ``httpx``-Antwort.

    Kein Zwischenpuffer: ``lesen_vorn`` bricht nach ``n`` Bytes ab (und
    schliesst danach die Antwort), ``strom`` gibt die Bloecke weiter. Damit
    kostet ein Blick auf die Magic-Bytes nicht mehr die ganze Datei.

    Der Vertrag verlangt, dass ``lesen_vorn`` mehrfach aufgerufen werden darf
    und jedes Mal wieder vorn beginnt (erst 12 Bytes, dann 4096, dann alles).
    Ein HTTP-Strom laesst sich nicht zurueckspulen — deshalb merkt sich die
    Quelle, was sie schon gesehen hat, und holt nur den FEHLENDEN Rest nach
    (``oeffnen`` liefert dafuer einen neuen Strom).
    """

    def __init__(self, antwort: httpx.Response, groesse: int) -> None:
        self._antwort = antwort
        self._groesse = groesse
        self._kopf = bytearray()
        self._strom: Iterator[bytes] | None = None
        self._fertig = False

    # -- Hilfen ---------------------------------------------------------
    def _quelle(self) -> Iterator[bytes]:
        if self._strom is None:
            if self._fertig:
                # Alles schon gelesen: eine leere Fortsetzung.
                return iter(())
            self._strom = self._antwort.iter_bytes(BLOCKGROESSE)
        return self._strom

    def _nachladen(self, mindestens: int) -> None:
        """Vom Strom lesen, bis der Kopf ``mindestens`` Bytes hat (oder Ende)."""
        if len(self._kopf) >= mindestens or self._fertig:
            return
        for block in self._quelle():
            self._kopf.extend(block)
            if len(self._kopf) >= mindestens:
                break
        else:
            self._fertig = True

    def _rest(self) -> Iterator[bytes]:
        """Erst den bereits gelesenen Kopf, dann den Rest des Stroms."""
        if self._kopf:
            zwischen = bytes(self._kopf)
            self._kopf = bytearray()
            yield zwischen
        if self._fertig:
            return
        for block in self._quelle():
            yield block
        self._fertig = True

    # -- Vertrag --------------------------------------------------------
    def lesen_vorn(self, anzahl: int) -> bytes:
        if anzahl is None or anzahl < 0:
            return self.ganz()
        self._nachladen(anzahl)
        return bytes(self._kopf[:anzahl])

    def lesen_rest(self) -> bytes:
        return b"".join(self._rest())

    def strom(self) -> Iterator[bytes]:
        return self._rest()

    def _ganz(self) -> bytes:
        """Die ganze Datei: erst der gelesene Kopf, dann der Rest des Stroms."""
        if not self._fertig:
            # Ein Byte mehr als die gemeldete Groesse: dann ist der Strom am
            # Ende (die Schleife in ``_nachladen`` setzt ``_fertig``).
            self._nachladen((self._groesse + 1) if self._groesse >= 0 else (1 << 62))
        return bytes(self._kopf)

    @property
    def groesse(self) -> int:
        return self._groesse

    def schliessen(self) -> None:
        try:
            self._antwort.close()
        except Exception:  # noqa: BLE001 — Schliessen darf nie werfen
            pass


def _laenge_der_antwort(antwort: httpx.Response) -> int:
    """``Content-Length`` der Antwort (``-1`` = unbekannt, z. B. chunked)."""
    wert = antwort.headers.get("Content-Length")
    try:
        return int(wert) if wert is not None else -1
    except ValueError:
        return -1


def _schliessender_strom(antwort: httpx.Response) -> Iterator[bytes]:
    """Die Bloecke der Antwort — und die Antwort wird IMMER geschlossen.

    Das ``finally`` laeuft auch, wenn der Verbraucher den Generator abbricht
    (``StreamingResponse`` ruft bei einem Client-Abbruch ``close()``/``aclose``
    auf den Generator): ohne das bliebe die WebDAV-Verbindung offen.
    """
    try:
        yield from antwort.iter_bytes(BLOCKGROESSE)
    finally:
        antwort.close()


def _ausschnitt_strom(
    antwort: httpx.Response, von: int, bis: int | None
) -> Iterator[bytes]:
    """Nur ``[von, bis]`` aus einer Antwort, die die GANZE Datei enthaelt.

    Der Server hat ``Range`` ignoriert (kein 206). Statt die ganze Datei in
    den Speicher zu lesen, wird blockweise gezaehlt und nur der verlangte
    Ausschnitt weitergereicht; danach wird abgebrochen und geschlossen.
    """
    grenze = None if bis is None else int(bis)
    try:
        position = 0
        for block in antwort.iter_bytes(BLOCKGROESSE):
            anfang = position
            position += len(block)
            if position <= von:
                continue
            links = max(0, von - anfang)
            rechts = len(block) if grenze is None else min(len(block), grenze - anfang + 1)
            stueck = block[links:rechts]
            if stueck:
                yield stueck
            if grenze is not None and position > grenze:
                return
    finally:
        antwort.close()


def _gesamt_aus_content_range(antwort: httpx.Response) -> int | None:
    """``Content-Range: bytes a-b/GESAMT`` -> ``GESAMT`` (``None`` = unbekannt)."""
    wert = antwort.headers.get("Content-Range") or ""
    _, _, gesamt = str(wert).partition("/")
    try:
        return int(gesamt.strip())
    except ValueError:
        return None


def _bereich_der_antwort(
    antwort: httpx.Response,
    von: int,
    bis: int | None,
    *,
    bekannt: int | None = None,
    quell_groesse: Callable[[], int | None] | None = None,
) -> tuple[int, int, int]:
    """``(gesamt, von, bis)`` aus einer GET-Antwort (``bis`` inklusiv).

    Mit ``206`` steht der tatsaechliche Bereich im ``Content-Range``-Kopf —
    der Server hat ihn womoeglich gekuerzt (Datei endet frueher). Ohne
    ``206`` ist die Antwort die GANZE Datei.

    Review-Punkt 7: Ist die Datei zwischen ``HEAD`` und ``GET`` GESCHRUMPFT,
    luegt ``Content-Range`` (sie nennt die alte Gesamtgroesse) oder fehlt.
    Deshalb wird der gemeldete Bereich gegen die wirklich ankommenden Bytes
    geprueft: gemeldet wird immer der Bereich, den die Antwort HERGIBT. Ein
    leerer Koerper ergibt ``(0, 0, -1)`` — der Aufrufer antwortet dann mit
    ``416`` statt mit ``206 bytes 0--1/N``.

    Review Runde 4, Punkt 3: Eine Antwort OHNE ``Content-Length`` (chunked,
    Proxy, HTTP/2) hat trotzdem eine Groesse. Sie kommt aus ``Content-Range``,
    sonst aus ``bekannt`` (der Groesse, die der Aufrufer schon hat), sonst aus
    ``quell_groesse()`` (eine Abfrage, z. B. ``HEAD``/``PROPFIND``). Ist die
    Groesse unbekannt, ist ``gesamt`` ``-1`` (unbekannt) — der Aufrufer reicht
    dann OHNE ``Content-Length`` durch (200, chunked) statt einen 416 zu
    erfinden.
    """
    wert = str(antwort.headers.get("Content-Range") or "")
    treffer = re.match(r"\s*bytes\s+(\d+)-(\d+)/(\d+|\*)", wert)
    if antwort.status_code == 206 and treffer:
        anfang, ende = int(treffer.group(1)), int(treffer.group(2))
        gesamt = int(treffer.group(3)) if treffer.group(3) != "*" else ende + 1
        laenge = _laenge_der_antwort(antwort)
        if laenge == 0 and ende >= anfang:
            return 0, 0, -1
        if 0 <= laenge < (ende - anfang + 1):
            # Der Server hat weniger geschickt als angekuendigt.
            ende = anfang + laenge - 1
            if ende < anfang:
                return 0, 0, -1
            gesamt = max(gesamt, ende + 1)
        return gesamt, anfang, ende
    gesamt = _laenge_der_antwort(antwort)
    if gesamt < 0:
        # Chunked/HTTP2: keine Laenge im Kopf. Die Gesamtgroesse kommt aus
        # ``Content-Range`` (falls doch einer da ist), sonst von aussen.
        gesamt = _gesamt_aus_content_range(antwort)
        if gesamt is None and bekannt is not None and bekannt >= 0:
            gesamt = int(bekannt)
        if gesamt is None and quell_groesse is not None:
            gefragt = quell_groesse()
            gesamt = gefragt if gefragt is not None else -1
        if gesamt is None or gesamt < 0:
            return -1, max(0, von or 0), -1
    if gesamt <= 0:
        return 0, 0, -1
    anfang = max(0, von or 0)
    ende = gesamt - 1 if bis is None else min(int(bis), gesamt - 1)
    if ende < anfang:
        return 0, 0, -1
    return gesamt, anfang, ende

#: Tiefenbegrenzung der Ordnerliste (Schutz vor einer Schleife im Baum).
MAX_TIEFE = 12

_PROPFIND_KOERPER = (
    b'<?xml version="1.0" encoding="utf-8"?>'
    b'<d:propfind xmlns:d="DAV:"><d:prop>'
    b"<d:resourcetype/><d:getcontentlength/>"
    b"</d:prop></d:propfind>"
)


def _propfind(xml: str) -> list["_Eintrag"]:
    """Antwort eines PROPFIND auswerten.

    Bewusst mit ``defusedxml`` (Pflichtabhaengigkeit): die Antwort kommt von
    einem fremden Server.

    **Der Eigen-Eintrag ist der erste** (der abgefragte Ordner selbst, mit dem
    href der Abfrage). Er wird hier als ``ist_eigen`` markiert, weil ein
    Vergleich ueber den blossen NAMEN nicht eindeutig ist: der Ordner ``a``
    enthaelt oft wieder einen Ordner ``a``.
    """
    from urllib.parse import unquote

    from defusedxml.ElementTree import fromstring

    try:
        wurzel = fromstring(xml)
    except Exception:  # noqa: BLE001 — kaputte Antwort = keine Eintraege
        return []
    liste: list[_Eintrag] = []
    for antwort in wurzel.iter():
        if not str(antwort.tag).endswith("response"):
            continue
        href_teil = ""
        ist_ordner = False
        for kind in antwort.iter():
            tag = str(kind.tag)
            if tag.endswith("href") and kind.text:
                href_teil = unquote(kind.text.strip())
            if tag.endswith("collection"):
                ist_ordner = True
        if not href_teil:
            continue
        teile = [t for t in href_teil.rstrip("/").split("/") if t]
        name = teile[-1] if teile else ""
        liste.append(_Eintrag(
            name=name,
            pfad=href_teil,
            ist_ordner=ist_ordner,
            # Der ERSTE Eintrag ist der abgefragte Ordner selbst (RFC 4918,
            # 9.1: „the response for the request URI“).
            ist_eigen=(not liste),
        ))
    return liste


def _laenge_aus_propfind(xml: str) -> int | None:
    """``getcontentlength`` aus einer PROPFIND-Antwort (``None`` = keine Angabe).

    Nimmt den ERSTEN Eintrag mit einer Zahl — bei ``Depth: 0`` ist das die
    angefragte Datei selbst. Ein Ordner hat dort keine Laenge (``None``).
    """
    from defusedxml.ElementTree import fromstring

    try:
        wurzel = fromstring(xml)
    except Exception:  # noqa: BLE001 — kaputte Antwort = keine Angabe
        return None
    for knoten in wurzel.iter():
        if not str(knoten.tag).endswith("getcontentlength"):
            continue
        try:
            return int(str(knoten.text or "").strip())
        except ValueError:
            continue
    return None


class _Eintrag:
    """Ein Eintrag aus einer PROPFIND-Antwort."""

    __slots__ = ("name", "pfad", "ist_ordner", "ist_eigen")

    def __init__(self, name: str, pfad: str, ist_ordner: bool, ist_eigen: bool) -> None:
        self.name = name
        self.pfad = pfad
        self.ist_ordner = ist_ordner
        self.ist_eigen = ist_eigen

    def __repr__(self) -> str:  # pragma: no cover — Diagnose
        art = "ordner" if self.ist_ordner else "datei"
        return f"<_Eintrag {self.name!r} {art}{' eigen' if self.ist_eigen else ''}>"


def _href_pfad(url: str) -> str:
    """Der Pfadteil einer Adresse OHNE Schema/Host (fuer den Vergleich).

    ``https://host/a/b/`` -> ``/a/b/``. Ein href darf in einer PROPFIND-Antwort
    absolut oder relativ sein; verglichen wird nur der Pfad.
    """
    from urllib.parse import unquote, urlsplit

    teile = urlsplit(str(url or ""))
    pfad = teile.path or str(url or "")
    return unquote(pfad)


def _schluessel_rest(url: str) -> str:
    """Aus einer WebDAV-Adresse einen Schluessel fuer die Fehlermeldung.

    Nur fuer ``NichtGefunden`` — die Meldung nennt den Schluessel, NIE die
    Adresse mit Host (die gehoert nicht in eine Antwort an den Browser).
    """
    teile = str(url).split("/")
    if len(teile) < 2:
        return url
    return "/".join(teile[-2:])
