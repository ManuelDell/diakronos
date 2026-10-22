"""A1c10 — zwei Schwellen, und die eigene Infrastruktur wird nie gesperrt.

DER AUFTRAG
------------
> "Mach Sperre pro Nutzer, nicht IP-Sperre. Wenn 25 fehlgeschlagene Logins,
> dann erst IP-Sperre. Aber nicht den Proxy sperren!"

Drei Entscheidungen in einer Karte:

  1. **Zwei Schwellen** — 5 je Konto, 25 je Adresse. Vorher galt EINE Zahl
     fuer beide Zaehler (`_max_versuche()`), und die war am Konto richtig und
     an der Adresse ein Betriebsausfall: eine Gemeinde hat typischerweise
     einen Internetanschluss, hinter einem Reverse-Proxy ist die Adresse die
     des Proxies, im LAN die des Routers. Fuenf Fehlversuche einer Person
     sperrten dort **alle**.
  2. **Die eigene Infrastruktur wird nie gesperrt** — Loopback, privat,
     link-local, unspecified. Nicht mal gezaehlt.
  3. **Zwei Fallen, die dabei nicht passieren duerfen**:
       * XFF darf die Regel nicht aushebeln (der Header ist selbstsetzbar);
       * die Nicht-Zaehlung ist nicht die Nicht-Sperre — sonst meldet der
         Notweg (A1c8) exit 2 fuer eine Adresse, die nie gesperrt werden
         kann. Dieselbe Luege, die A1c7/A1c8 gerade abgeraeumt haben.

Diese Datei ist die **Store-Seite** gegen den Stub (schnell, kein echtes
Redis). Der echte Stack, CalDAV und der CLI-Unterprozess stehen in
`test_a1c10_live.py` und `tools/a1c10_abnahme.py`.

Warum 25 und nicht 5 an der Adresse: 25 ist die Sammelsperre gegen jemanden,
der **viele Konten** durchprobiert (Credential Stuffing). Fuer einen
Angreifer kostet 25 fast nichts, fuer Menschen hinter einem gemeinsamen
Anschluss praktisch nie. Die Kontosperre (5) greift in jedem Fall.
"""

from __future__ import annotations

import pytest

from diakronos_app.frappe_compat import loginversuche as lv

# Die beiden Schwellen aus der Karte. Sie stehen hier als **Konstanten des
# Tests** und nicht als `settings.login_max_versuche*` — sonst wuerde der
# Test die Implementierung bestaetigen statt die Vorgabe. Wenn jemand den
# Default aendert, faellt dieser Test auf.
KONTO = 5
ADRESSE = 25

OEFFENTLICH = "203.0.113.77"
OEFFENTLICH_2 = "198.51.100.23"
PRIVAT = "127.0.0.1"


# ── Helfer ──────────────────────────────────────────────────────────────────


def _adresse_auf(ip: str, stand: int, bereich: str = lv.BEREICH_LOGIN) -> None:
    """Bringt den IP-Zaehler auf einen **gemessenen** Stand.

    Ueber verschiedene Konten, wie ein Angriff von aussen das tut — sonst
    sperrt zuerst der Benutzerzaehler und die Adresse kommt nie dran. Jeder
    Versuch zaehlt die Adresse mit; bei `stand <= ADRESSE` bleibt es bei
    genau `stand` Versuchen, ohne dass gesperrt wird (bei `> ADRESSE` waere
    das Gegenteil der Fall — dann legt `_adresse_bis_sperre` den Zustand an).
    """
    for nummer in range(stand):
        erlaubt, _grund = lv.pruefe_und_merke(f"opfer{nummer}@example.org", ip, bereich=bereich)
        assert erlaubt, (
            f"die Adresse wurde bei {nummer + 1} Versuchen gesperrt — der Test "
            "will nur den Zaehler stellen, keine Sperre"
        )


def _zaehler_lesen(ip: str, bereich: str = lv.BEREICH_LOGIN) -> int:
    client = lv._client()
    for _art, zaehler, _sperr in lv._kennungen(None, ip, bereich):
        roh = client.get(zaehler)
        if roh is not None:
            return int(roh)
    return 0


def _konto_gesperrt(user: str) -> bool:
    client = lv._client()
    return any(
        client.exists(sperr)
        for bereich in lv.BEREICHE
        for _art, _zaehler, sperr in lv._kennungen(user, None, bereich)
    )


def _adresse_gesperrt(ip: str) -> bool:
    client = lv._client()
    return any(
        client.exists(sperr)
        for bereich in lv.BEREICHE
        for _art, _zaehler, sperr in lv._kennungen(None, ip, bereich)
    )


# ── 1. Die zwei Schwellen ───────────────────────────────────────────────────


def test_das_konto_sperrt_bei_fuenf_der_adresse_bei_fuenfundzwanzig(fake_redis):
    """**Die Karte, als Test.** Fuenf Fuenf vs. fuenfundzwanzig Fuenf.

    Dieselbe Adresse, dieselben fuenf Versuche — aber an zwei Konten. Am
    Konto sperrt der 6. Versuch, an der Adresse ist nichts passiert. Genau
    diese Entkopplung hat Manuel verlangt.
    """
    for nummer in range(KONTO):
        assert lv.pruefe_und_merke("anna@example.org", OEFFENTLICH)[0] is True
    assert lv.pruefe_und_merke("anna@example.org", OEFFENTLICH)[0] is False, (
        "fuenf Fehlversuche fuer ein Konto muessen sperren"
    )
    assert _konto_gesperrt("anna@example.org")
    assert not _adresse_gesperrt(OEFFENTLICH), (
        "die Adresssperre darf nicht mitlaufen — das war genau der Ausfall"
    )


def test_keine_adresssperre_zwischen_sechs_und_fuenfundzwanzig(fake_redis):
    """Der Alltagsfall: viele Fehlversuche ueber viele Konten, keine Sperre.

    Das ist der Credential-Stuffing-Angriff, den die Adresssperre abfangen
    soll — aber erst ab 25. Zwischen 6 und 24 Fehlversuchen darf **nichts**
    passieren, und genau hier hat die alte Fassung (Schwelle 5) das halbe
    Buero ausgesperrt.
    """
    _adresse_auf(OEFFENTLICH, KONTO + 1)

    assert _zaehler_lesen(OEFFENTLICH) == KONTO + 1
    assert not _adresse_gesperrt(OEFFENTLICH), "die Adresssperrt zu frueh"
    assert lv.ist_gesperrt(None, OEFFENTLICH) is False


def test_erst_bei_fuenfundzwanzig_sperrt_die_adresse(fake_redis):
    """Ab 25 ueber **mehrere Konten** hinweg greift die Adresssperre."""
    for nummer in range(ADRESSE):
        lv.pruefe_und_merke(f"opfer{nummer}@example.org", OEFFENTLICH)

    assert not _adresse_gesperrt(OEFFENTLICH), "25 Versuche duerfen noch nicht sperren"
    erlaubt, grund = lv.pruefe_und_merke("opfer999@example.org", OEFFENTLICH)

    assert erlaubt is False
    assert grund == "ip", f"ausgeloest hat der Adresszaehler, nicht {grund}"
    assert _adresse_gesperrt(OEFFENTLICH)


def test_die_schwellen_kommen_aus_der_einen_funktion(fake_redis, monkeypatch):
    """**Eine Quelle der Wahrheit** (A1c3-Lehre, ausdruecklich gefordert).

    Wer die Zahlen an zwei Orten kopiert, hat sie an einem davon irgendwann
    falsch. Der Test misst deshalb nicht "die Zahl ist 5", sondern "beide
    Schwellen kommen aus `_max_versuche(art)`" — inklusive der Tatsache, dass
    ein Tippfehler im Aufrufer nicht die Adressschwelle durchfallen laesst.
    """
    monkeypatch.setattr(lv.settings, "login_max_versuche", 3)
    monkeypatch.setattr(lv.settings, "login_max_versuche_ip", 7)

    assert lv._max_versuche() == 3
    assert lv._max_versuche("u") == 3
    assert lv._max_versuche("ip") == 7
    # Und wirklich angewendet, nicht nur gelesen:
    for nummer in range(3):
        lv.pruefe_und_merke("anna@example.org", OEFFENTLICH)
    assert lv.pruefe_und_merke("anna@example.org", OEFFENTLICH)[0] is False


def test_die_adresssperre_rechnet_mit_der_adressschwelle(fake_redis, monkeypatch):
    """`zaehle_adressen_im_weg()` muss **dieselbe** Schwelle benutzen.

    Das ist die Falle aus A1c8, eine Ebene tiefer: der Notweg fragt
    "steht noch etwas im Weg", und wenn diese Funktion mit der
    **Kontoschwelle** rechnete, wuerde sie ab 5 Fehlversuchen "im Weg"
    melden — obwohl erst bei 25 gesperrt wird. Der Notweg wuerde dann
    dauerhaft Exitcode 2 liefern. Genau die Luege, die A1c7/A1c8 abraeumen.
    """
    monkeypatch.setattr(lv.settings, "login_max_versuche_ip", ADRESSE)

    # Auf der Kontoschwelle, aber weit unter der Adressschwelle:
    _adresse_auf(OEFFENTLICH, KONTO + 1)
    assert lv.zaehle_adressen_im_weg() == 0, (
        "eine Adresse kurz unter der Adressschwelle sperrt beim naechsten "
        "Versuch nicht — der Notweg wuerde sonst grundlos exit 2 melden"
    )

    # Auf der Adressschwelle: jetzt steht sie im Weg.
    _adresse_auf(OEFFENTLICH, ADRESSE - KONTO - 1)
    assert _zaehler_lesen(OEFFENTLICH) == ADRESSE
    assert lv.zaehle_adressen_im_weg() == 1, (
        "die Adresse steht auf der Adressschwelle und sperrt beim naechsten "
        "Versuch — der Notweg muss das sehen"
    )


# ── 2. Die Proxy-Regel: eigene Adressen werden nie gesperrt ────────────────


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",        # Loopback
        "127.1.2.3",        # Loopback/8, nicht nur 127.0.0.1
        "127.010_000_000_005.127",  # privat
        "127.010_255_255_254.127",
        "127.172_016_000_001.127",  # privat, untere Grenze
        "127.172_017_000_002.127",  # Docker-Bridge
        "127.172_031_255_254.127",  # 172.16/12, obere Grenze
        "127.192_168_007_011.127",  # privat
        "169.254.10.1",     # link-local
        "0.0.0.0",          # unspecified
    ],
)
def test_eigene_adressen_werden_weder_gezaehlt_noch_gesperrt(ip, fake_redis):
    """**Der Kern der Karte.** Deutlich mehr als 25 Fehlversuche von einer
    privaten Adresse: keine Adresssperre, und gar kein Zaehler.

    `127.0.0.1` genuegt fuer die Messung (die App sieht im Docker-Netz ohne
    Proxy die Container-Adresse), deshalb steht hier der ganze Bereich:
    eine Regel, die nur `127.0.0.1` kennt, waere kein Proxy-Schutz.
    """
    for nummer in range(ADRESSE + 10):
        lv.pruefe_und_merke(f"opfer{nummer}@example.org", ip)

    assert not _adresse_gesperrt(ip), f"{ip} wurde gesperrt — der Proxy darf das nie"
    assert not lv.ist_gesperrt(None, ip)
    assert lv.zaehle_adressen_im_weg() == 0, (
        "eine Adresse, die nie gesperrt werden kann, darf den Notweg nicht "
        "mit 'steht im Weg' aufhalten (A1c8)"
    )
    # Nicht mal gezaehlt: `_kennungen()` liefert fuer sie gar keine Kennung.
    assert _zaehler_lesen(ip) == 0
    assert [art for art, _z, _s in lv._kennungen("anna@example.org", ip)] == ["u"], (
        "eine eigene Adresse darf nicht einmal einen Zaehler-Key bekommen"
    )


def test_die_kontosperre_greift_auch_hinter_einer_privaten_adresse(fake_redis):
    """Die Proxy-Regel nimmt **nur** die Adresssperre weg — nicht das Konto.

    Sonst waere sie keine Proxy-Regel, sondern das Ende des Schutzes: ein
    Angreifer im LAN koennte jedes Konto beliebig oft durchprobieren.
    """
    for nummer in range(KONTO + 1):
        lv.pruefe_und_merke("anna@example.org", PRIVAT)

    assert _konto_gesperrt("anna@example.org"), "die Kontosperre muss greifen"
    assert not _adresse_gesperrt(PRIVAT), "die Adresse darf nie gesperrt werden"


@pytest.mark.parametrize(
    "ip",
    ["203.0.113.77", "198.51.100.23", "8.8.8.8", "172.15.0.1", "172.32.0.1", "11.0.0.1", "192.169.0.1"],
)
def test_oeffentliche_adressen_werden_wie_bisher_gezaehlt(ip, fake_redis):
    """Die Ausnahme gilt **nur** fuer eigene Adressen.

    Der Schutz muss dort existieren, wo er etwas nuetzt: im Internet ist die
    Adresse des Angreifers eine oeffentliche, und die wird gesperrt.

    Die Randfaelle sind mit drin, weil sie zeigen, dass der Bereich nicht
    zu weit gezogen ist: `172.15` und `172.32` liegen **ausserhalb** von
    172.16/12, `11.0.0.1` ausserhalb von 10/8, `192.169.0.1` ausserhalb von
    192.168/16. Wer dort laenger macht, sperrt oeffentliche Adressen mit —
    das waere genau die Umkehrung der Karte.
    """
    _adresse_auf(ip, 1)
    assert _zaehler_lesen(ip) == 1, f"{ip} wurde nicht gezaehlt"


def test_fremde_und_kaputte_werte_sind_keine_eigene_adresse(fake_redis):
    """Ungueltig ist nicht eigen; IPv6-Loopback ist seit A1c12 eigen.

    Die getrennte Validierung/Fallback-Regel prueft test_a1c12_ipv6.py.
    """
    for wert in ("2001:db8::1", "unix:/tmp/app.sock"):
        assert lv._ist_eigene_adresse(wert) is False, f"{wert} wurde ausgenommen"
        assert lv._ist_eigene_adresse(None) is False
        assert lv._ist_eigene_adresse("") is False
        assert lv._ist_eigene_adresse("   ") is False


def test_der_escape_hatch_schaltet_die_ausnahme_ab(fake_redis, monkeypatch):
    """`LOGIN_IP_SPERRE_AUCH_PRIVAT=1` hebt die Regel ausdruecklich auf.

    Und weil: der Wert ist ein Settings-Feld, wird beim Start gelesen und
    gilt damit fuer **alle** drei Zugriffe (Zaehlen, Sperre, Freigeben) —
    nicht fuer einen Aufruf. Wer ihn setzt, sperrt praktisch das ganze
    Buero; das ist der dokumentierte Preis, und die Karte verlangt genau
    diese Fluchtklappe fuer Betreiber, die es wollen.
    """
    assert lv._ist_eigene_adresse(PRIVAT) is True, "Ausgangslage: Regel nicht aktiv"
    monkeypatch.setattr(lv.settings, "login_ip_sperre_auch_privat", True)

    assert lv._ist_eigene_adresse(PRIVAT) is False, "der Schalter greift nicht"
    for nummer in range(ADRESSE + 1):
        lv.pruefe_und_merke(f"opfer{nummer}@example.org", PRIVAT)
    assert _adresse_gesperrt(PRIVAT), (
        "mit dem Schalter wird auch die private Adresse gesperrt"
    )


# ── 3. Falle 1: XFF darf die Regel nicht aushebeln ──────────────────────────


def test_xff_macht_eine_oeffentliche_adresse_zaehlbar(fake_redis):
    """Der Normalfall hinter dem Proxy: die Zieladresse ist oeffentlich.

    Von einer privaten Adresse (der Proxy) mit `X-Forwarded-For` auf eine
    oeffentliche: die **oeffentliche** wird gezaehlt und gesperrt, die
    private nicht. Das ist der Schutz, den die Karte im Internet will.
    """
    for nummer in range(ADRESSE + 1):
        lv.pruefe_und_merke(f"opfer{nummer}@example.org", "198.51.100.7")

    assert _adresse_gesperrt("198.51.100.7"), "die oeffentliche XFF-Adresse muss sperren"
    assert not _adresse_gesperrt(PRIVAT), "der Proxy selbst darf nie gesperrt werden"


def test_xff_auf_eine_eigene_adresse_hebelt_die_regel_nicht_aus(fake_redis):
    """**Die Falle.** XFF ist selbstsetzbar — die Regel gilt fuer JEDE Adresse.

    `X-Forwarded-For: 127.0.0.1` bei aktivem `BEHIND_PROXY` darf keine
    Sperre ausloesen, weil die Zieladresse privat ist. Wuerde die Pruefung
    nur auf `REMOTE_ADDR` angewendet, waere die Nicht-Zaehlung per Kopfzeile
    ausloesbar — und der Proxy-Schutz waere ein Wort.
    """
    # Der Aufrufer reicht die aus dem Header gelesene Adresse weiter; die
    # Regel haengt in `pruefe_und_merke` und muss fuer sie gelten.
    for nummer in range(ADRESSE + 10):
        lv.pruefe_und_merke(f"opfer{nummer}@example.org", "127.0.0.1")

    assert not _adresse_gesperrt("127.0.0.1"), "XFF hat die Proxy-Regel ausgehebelt"
    assert _zaehler_lesen("127.0.0.1") == 0


# ── 4. Falle 2: Nicht-Zaehlen ist nicht Nicht-Sperren ───────────────────────


def test_der_notweg_meldet_fuer_eine_eigene_adresse_nichts_im_weg(fake_redis):
    """**Die zweite Falle.** Sonst meldet der Notweg exit 2 ohne Grund.

    `zaehle_adressen_im_weg()` zaehlt nur, was **sperr- und
    schwellenrelevant** ist. Eine eigene Adresse wird nie gesperrt und nie
    auf die Schwelle gezaehlt — sie darf dort also nicht auftauchen.
    """
    # 1. Ein Konto wird gesperrt (der Alltagsfall).
    for nummer in range(KONTO + 1):
        lv.pruefe_und_merke("anna@example.org", PRIVAT)
    assert _konto_gesperrt("anna@example.org")

    # 2. Die Konto-Freigabe raeumt ab.
    bericht = lv.entsperre_konto_und_ip("anna@example.org", None)

    assert bericht["u"] == 1, "Ausgangslage: das Konto war nicht gesperrt"
    assert not _konto_gesperrt("anna@example.org"), "die Freigabe hat nicht gewirkt"
    assert lv.zaehle_adressen_im_weg() == 0, (
        "der Notweg wuerde exit 2 melden ('die Adresse steht noch im Weg'), "
        "obwohl die Adresse nie gesperrt werden kann — genau die Luege aus A1c8"
    )


def test_oeffentliche_adressen_meldet_der_notweg_weiterhin(fake_redis):
    """**Das Gegenteil, damit Nummer 4 nicht durch Abschalten gruen wird.**

    Nach derselben Freigabe bei einer oeffentlichen Adresse: steht die auf
    der Schwelle, meldet der Notweg sehr wohl "im Weg". Die Regel aus
    Abschnitt 4 darf nicht dazu fuehren, dass der Notweg insgesamt blind
    wird.
    """
    for nummer in range(KONTO + 1):
        lv.pruefe_und_merke("anna@example.org", PRIVAT)
    lv.entsperre_konto_und_ip("anna@example.org", None)

    _adresse_auf(OEFFENTLICH, ADRESSE)
    assert _zaehler_lesen(OEFFENTLICH) == ADRESSE

    assert lv.zaehle_adressen_im_weg() == 1, (
        "eine oeffentliche Adresse auf der Schwelle steht im Weg — der Notweg "
        "muss das weiterhin melden"
    )


# ── 5. CalDAV zieht automatisch mit ────────────────────────────────────────


def test_caldav_gilt_dieselbe_regel_ohne_zweite_kopie(fake_redis):
    """CalDAV zaehlt im eigenen Bereich, erbt aber Schwellen und Proxy-Regel.

    `caldav/auth.py::get_authenticated_user` ruft dieselbe
    `pruefe_und_merke`-Funktion — deshalb gilt fuer `bereich="caldav"`
    automatisch dasselbe. Dieser Test haelt fest, dass dort **nichts**
    nachzupflegen ist: gleiche Schwellen, gleiche Ausnahme. Wer spaeter eine
    eigene Zaehlung fuer CalDAV baut, sieht es hier.
    """
    # KONTO+1 Fehlversuche im CalDAV-Bereich, **dasselbe** Konto (sonst waere
    # es der Angriff ueber viele Konten und der Benutzerzaehler kaeme nie an
    # die Schwelle), von einer oeffentlichen Adresse.
    for _ in range(KONTO + 1):
        lv.pruefe_und_merke("anna@example.org", OEFFENTLICH, bereich=lv.BEREICH_CALDAV)

    assert not _adresse_gesperrt(OEFFENTLICH), "CalDAV darf die Adresse nicht mit 5 sperren"
    assert lv.ist_gesperrt("anna@example.org", None, bereich=lv.BEREICH_CALDAV)

    # Und die private Adresse bleibt auch im CalDAV-Bereich unberuehrt:
    for nummer in range(ADRESSE + 5):
        lv.pruefe_und_merke(f"opfer{nummer}@example.org", PRIVAT, bereich=lv.BEREICH_CALDAV)
    assert not _adresse_gesperrt(PRIVAT)
    assert lv.zaehle_adressen_im_weg() == 0


# ── 6. Der Bericht behauptet nichts Falsches ────────────────────────────────


def test_gib_bericht_nennt_keine_eigene_adresse(fake_redis):
    """Der Bericht darf fuer eine eigene Adresse nichts erfinden.

    `gib_bericht(user, ip)` sagt, ob etwas zu loeschen ist. Fuer eine
    Adresse, die nie gesperrt werden kann, ist die ehrliche Antwort `0` —
    nicht `1`, weil es "irgendwo im Keyspace" einen Schluessel gibt.
    """
    for nummer in range(ADRESSE + 5):
        lv.pruefe_und_merke(f"opfer{nummer}@example.org", PRIVAT)

    bericht = lv.gib_bericht("anna@example.org", PRIVAT)
    assert bericht["ip"] == 0, "der Bericht meldet eine Sperre, die es nicht gibt"

    # Zum Vergleich: dieselbe Abfrage mit oeffentlicher Adresse, wo es
    # wirklich etwas zu loeschen gibt.
    for nummer in range(KONTO + 1):
        lv.pruefe_und_merke("bruno@example.org", OEFFENTLICH_2)
    assert lv.gib_bericht("bruno@example.org", OEFFENTLICH_2)["ip"] == 1, (
        "der Vergleichsfall fehlt — der Test prueft sonst nichts"
    )
