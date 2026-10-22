"""A1c6 (1/2) — der Aufraehrweg im Store: Bericht, IP-Freigabe, Werkzeugbudget.

Alles hier ist **Datenlogik ohne HTTP**. Der Web-Weg (`api/entsperren.py`) und
die CLI (`loginversuche.py::__main__`) sitzen beide auf diesen Funktionen auf;
was hier nicht gilt, kann keiner der beiden Wege richtig machen.

Ausgangspunkt ist der Befund der Gegenprobe (Orchestrator, Lauf 2): nach fuenf
Fehlversuchen war das Konto frei, aber die **IP blieb gesperrt** — jede Anmeldung
blieb 401. `zuruecksetzen_alles(user)` leert nur das Konto, und das ist fuer den
Web-Weg richtig (die IP-Sperre gehoert dem Absender). Fuer den Notweg ist es
eine Sackgasse, deshalb `entsperre_konto_und_ip(user, ip)`.

Die fuenf Saetze, die diese Datei zusammenhalten:

  1. Der Bericht verraet **ob**, nicht **wie viel**: je Kennungsart eine Zahl
     von Schluesseln, nie Zaehlerstaende, Sperrzeiten oder Fehlversuche.
  2. `entsperre_konto_und_ip` loest beide Bereiche **und** die IP — belegt an
     beiden Zaehler-Keys, nicht nur an der Behauptung im Docstring.
  3. Die IP-Freigabe ist ein **zweiter, ausdruecklicher** Schritt. Ohne `ip`
     passiert genau das, was A1c2 entschieden hat: nur das Konto.
  4. Der Werkzeugzaehler traegt **keinen Klartext** — derselbe gesalzene Hash
     wie die Zaehler-Keys, auch im Rate-Limit.
  5. Das Budget laeuft je **Benutzer** und wird bei jedem Aufruf **nicht**
     verlaengert: ein laufendes Fenster verschiebt sich nicht.
"""

from __future__ import annotations

from diakronos_app.frappe_compat import loginversuche as lv

SCHWELLE = 5


# ── Helfer: Sperren erzeugen und einzeln PRUEFEN ────────────────────────────
#
# `pruefe_und_merke` zaehlt Benutzer UND IP, kehrt aber sofort zurueck, sobald
# EINE Schwelle ausgeloest hat. Bei einem wiederholten Versuch mit derselben
# Kennung reisst also der Benutzerzaehler zuerst — die IP wird dann nie
# gesperrt. Wer beides braucht, muss es getrennt erzeugen (`_sperre_beides`);
# sonst prueft man den leeren Fall und freut sich ueber ein gruenes, das nichts
# beweist. Genau daran ist die Gegenprobe gescheitert.


def _konto_gesperrt(user: str) -> bool:
    """Steht der **Konto**-Sperr-Key? Nicht die IP, nicht "irgendetwas"."""
    client = lv._client()
    return any(
        client.exists(sperr)
        for bereich in lv.BEREICHE
        for _art, _zaehler, sperr in lv._kennungen(user, None, bereich)
    )


def _ip_gesperrt(ip: str) -> bool:
    """Steht der **IP**-Sperr-Key?"""
    client = lv._client()
    return any(
        client.exists(sperr)
        for bereich in lv.BEREICHE
        for _art, _zaehler, sperr in lv._kennungen(None, ip, bereich)
    )


def _sperre_konto(user: str, bereiche=lv.BEREICHE) -> None:
    """Bringt ein Konto bis zur Sperre — und prueft es danach einzeln."""
    for bereich in bereiche:
        for _ in range(SCHWELLE + 1):
            lv.pruefe_und_merke(user, None, bereich=bereich)
    assert _konto_gesperrt(user), "Testvoraussetzung verfehlt: kein Konto gesperrt"


def _sperre_ip(ip: str, bereiche=lv.BEREICHE) -> None:
    """Bringt eine IP bis zur Sperre — ueber viele verschiedene Konten.

    Das ist der Angriff, den die IP-Sperre abfangen soll, und zugleich der
    Zustand, in dem eine Gemeinde mit einem Anschluss hengen kann: der Admin,
    der sich anmeldet, IST die gesperrte Adresse.

    **A1c10:** die Adresse sperrt erst bei `LOGIN_MAX_VERSUCHE_IP` (25), nicht
    bei `LOGIN_MAX_VERSUCHE` (5). Diese Hilfsfunktion liest die Schwelle aus
    dem Store — mit `SCHWELLE` hier einzusetzen hiesse, einen Zustand zu
    behaupten, den es nicht mehr gibt, und der Test wuerde an seiner eigenen
    Voraussetzung scheitern.
    """
    for bereich in bereiche:
        for nummer in range(lv._max_versuche("ip") + 1):
            lv.pruefe_und_merke(f"opfer{nummer}@example.org", ip, bereich=bereich)
    assert _ip_gesperrt(ip), "Testvoraussetzung verfehlt: keine IP gesperrt"


def _sperre_beides(user: str, ip: str) -> None:
    """Der Notfall der Karte: Konto **und** IP stehen gleichzeitig."""
    _sperre_konto(user)
    _sperre_ip(ip)
    assert _konto_gesperrt(user) and _ip_gesperrt(ip), "Testvoraussetzung verfehlt"


def _zaehler_und_sperrkeys(user: str, ip: str | None = None) -> list[str]:
    """Alle Keys dieses Kontos/dieser IP — ueber die echten Key-Funktionen.

    Bewusst nicht per `SCAN` ueber den Store: der Test soll pruefen, dass die
    Freigabe genau die berechneten Keys trifft, und nicht, dass zurueck
    irgendetwas anderes leer ist.
    """
    keys: list[str] = []
    for bereich in lv.BEREICHE:
        for _art, zaehler, sperr in lv._kennungen(user, ip, bereich):
            keys += [zaehler, sperr, f"{sperr}:stufe"]
    return sorted(set(keys))


# ── 1. Der Bericht sagt ob, nicht wie viel ──────────────────────────────────


def test_bericht_ist_leer_wenn_nichts_da_ist(fake_redis):
    assert lv.gib_bericht("anna@example.org", "203.0.113.9") == {"u": 0, "ip": 0}


def test_bericht_zaehlt_das_gesperrte_konto(fake_redis):
    """Ein gesperrtes Konto steht drin — als EINS, ohne Fehlversuchszahl."""
    _sperre_konto("anna@example.org")

    bericht = lv.gib_bericht("anna@example.org")

    assert bericht["u"] == 1
    assert bericht["ip"] == 0


def test_bericht_nennt_keine_zaehlerstaende_und_keine_sperrzeit(fake_redis):
    """Abnahme: keine Trefferzahl, keine Sperrdauer, keine Restzeit.

    Der Bericht traegt genau zwei Zahlen — je Kennungsart. Wer daraus mehr
    ableiten will (wie viele Fehlversuche, wie lange noch gesperrt), laesst
    sich das hier nicht liefern.
    """
    _sperre_konto("anna@example.org")

    bericht = lv.gib_bericht("anna@example.org")

    assert set(bericht) == {"u", "ip"}
    assert all(isinstance(v, int) and v >= 0 for v in bericht.values())


def test_bericht_aendert_nichts(fake_redis):
    """Rein lesend: ein Bericht ist kein Aufraehrvorgang im disguise."""
    _sperre_konto("anna@example.org")

    lv.gib_bericht("anna@example.org")

    assert _konto_gesperrt("anna@example.org"), "der Bericht hat entsperrt"


def test_bericht_ohne_ip_sagt_nichts_ueber_die_ip(fake_redis):
    """Ohne genannte IP wird keine IP ausgekundet — auch nicht fuer sich selbst.

    Wer keine IP nennt, hat nach der IP nicht gefragt. Der Bericht darf ihm
    nicht ungefragt sagen, dass unter derselben Adresse etwas sperrt.
    """
    _sperre_konto("anna@example.org")
    _sperre_ip("203.0.113.9")

    assert lv.gib_bericht("anna@example.org")["ip"] == 0
    assert lv.gib_bericht("anna@example.org", "203.0.113.9")["ip"] == 1


def test_bericht_behandelt_gross_klein_und_umraum_wie_der_anmeldepfad(fake_redis):
    """Der Admin tippt die Adresse ein — wie im Anmeldepfad normalisiert."""
    _sperre_konto("anna@example.org")

    bericht = lv.gib_bericht("  ANNA@Example.ORG  ", " 203.0.113.9 ")

    assert bericht["u"] == 1


def test_bericht_ist_leer_fuer_unbekanntes_konto(fake_redis):
    """Ein Name, den es nie gab, sieht aus wie ein Name, der nie gesperrt war."""
    assert lv.gib_bericht("niemand@example.org", "203.0.113.9") == {"u": 0, "ip": 0}


def test_bericht_fuer_leere_kennung_faellt_nicht_ueber(fake_redis):
    """Auch der Aufrufer, der gar nichts nennt, bekommt eine Antwort."""
    assert lv.gib_bericht("", None) == {"u": 0, "ip": 0}
    assert lv.entsperre_konto_und_ip(None, None) == {"u": 0, "ip": 0}


# ── 2. Konto UND IP, beide Bereiche ────────────────────────────────────────


def test_entsperren_loest_die_sperrte_woechentlich(fake_redis):
    """Der Kernfall: Konto UND IP gesperrt, danach ist beides frei.

    Genau die Messung der Gegenprobe, die gescheitert war: Konto frei, IP
    weiter gesperrt, jede Anmeldung 401. Beide Sperren werden hier getrennt
    erzeugt und getrennt geprueft — sonst prueft der Test den leeren Fall.
    """
    _sperre_beides("anna@example.org", "203.0.113.9")

    bericht = lv.entsperre_konto_und_ip("anna@example.org", "203.0.113.9")

    assert bericht["u"] == 1 and bericht["ip"] == 1, "die Sperre stand woertlich nicht"
    assert not _konto_gesperrt("anna@example.org")
    assert not _ip_gesperrt("203.0.113.9")
    assert not lv.ist_gesperrt("anna@example.org", "203.0.113.9")


def test_entsperren_leert_alle_schluessel_des_kontos(fake_redis):
    """Beleg auf Keyebene: kein Zaehler und keine Stufe bleibt von IHM stehen.

    Nur die Sperre zu loeschen reicht nicht: ein Zaehler, der auf der Schwelle
    steht, sperrt beim naechsten Versuch sofort wieder, und der Aufrufer
    wundert sich ueber den naechsten 401.

    Geprueft werden die Keys des genannten Kontos und der genannten IP — nicht
    der ganze Store. Die Hilfskonten, mit denen die IP gesperrt wurde, sind
    fremde Konten; ihre Zaehler zu loeschen waere genau der Fehler, vor dem
    diese Karte baut ("Freigeben heisst freigeben").
    """
    user, ip = "anna@example.org", "203.0.113.9"
    _sperre_beides(user, ip)
    fremde = fake_redis._values.copy()
    assert fremde, "Testvoraussetzung verfehlt: Store ist leer"

    lv.entsperre_konto_und_ip(user, ip)

    eigene = [k for k in _zaehler_und_sperrkeys(user, ip)]
    assert [k for k in eigene if fake_redis._values.get(k)] == [], "eigener Rest"
    # Und nichts, was dem Konto oder der IP gehoert, ist ueberhaupt noch da:
    assert not any(lv._hash(user) in k or lv._hash(ip) in k for k in fake_redis._values)


def test_entsperren_leert_die_zaehler_beider_bereiche(fake_redis):
    """Nicht nur die Sperre: die halben Serien in BEIDEN Zaehlern sind weg."""
    user, ip = "anna@example.org", "203.0.113.9"
    for bereich in lv.BEREICHE:
        for _ in range(SCHWELLE - 1):
            lv.pruefe_und_merke(user, ip, bereich=bereich)
    assert lv.zaehler_stand(user, ip, bereich=lv.BEREICH_CALDAV)["benutzer"] > 0

    lv.entsperre_konto_und_ip(user, ip)

    for bereich in lv.BEREICHE:
        stand = lv.zaehler_stand(user, ip, bereich=bereich)
        assert stand["benutzer"] == 0, f"Bereich {bereich}: Kontozaehler steht noch"
        assert stand["ip"] == 0, f"Bereich {bereich}: IP-Zaehler steht noch"


def test_entsperren_ist_idempotent(fake_redis):
    """Zweimal aufrufen ist unschaedlich — und meldet beim zweiten Mal nichts."""
    _sperre_beides("anna@example.org", "203.0.113.9")

    lv.entsperre_konto_und_ip("anna@example.org", "203.0.113.9")
    zweiter = lv.entsperre_konto_und_ip("anna@example.org", "203.0.113.9")

    assert zweiter == {"u": 0, "ip": 0}, "der zweite Lauf meldet noch eine Sperre"
    assert not _konto_gesperrt("anna@example.org")
    assert not _ip_gesperrt("203.0.113.9")


def test_entsperren_lasst_andere_konten_gesperrt(fake_redis):
    """Freigeben heisst freigeben — nicht "alle Schluessel leeren"."""
    a, ip = "anna@example.org", "203.0.113.9"
    b = "berta@example.org"
    _sperre_konto(a)
    _sperre_konto(b)
    assert _konto_gesperrt(b)

    lv.entsperre_konto_und_ip(a, ip)

    assert not _konto_gesperrt(a)
    assert _konto_gesperrt(b), "b wurde mitfreigegeben"


def test_entsperren_braucht_keine_ip_fuer_die_konto_freigabe(fake_redis):
    """`ip=None` loest genau das, was A1c2 entschieden hat: nur das Konto."""
    user = "anna@example.org"
    _sperre_konto(user)

    bericht = lv.entsperre_konto_und_ip(user, None)

    assert bericht["u"] == 1 and bericht["ip"] == 0
    assert not _konto_gesperrt(user)


# ── 3. Die IP-Freigabe ist ein eigener, ausdruecklicher Schritt ─────────────


def test_ohne_ip_bleibt_die_ip_sperrte_stehen(fake_redis):
    """Die A1c2-Entscheidung gilt unveraendert: Konto ja, IP nein.

    Wer sein eigenes Konto freigibt, will nicht ungefragt das halbe Buero
    mitentsperren. Deshalb ist die IP hier KEIN Mitloeschen im Hintergrund.
    """
    user, ip = "anna@example.org", "203.0.113.9"
    _sperre_beides(user, ip)

    lv.entsperre_konto_und_ip(user, None)

    assert not _konto_gesperrt(user), "das Konto ist nicht freigegeben"
    assert _ip_gesperrt(ip), "die IP wurde ungefragt mitfreigegeben"


def test_der_bericht_unterscheidet_die_zwei_faelle(fake_redis):
    """Der Aufrufer kann an der Antwort ablesen, was er getan hat.

    Das ist der Grund, warum es einen Bericht gibt: "Sperre fuer Login und
    CalDAV aufgehoben" und "war nicht gesperrt" muessen unterscheidbar sein,
    ohne dass der Bestand preisgegeben wird.
    """
    user, ip = "anna@example.org", "203.0.113.9"
    _sperre_beides(user, ip)

    nur_konto = lv.entsperre_konto_und_ip(user, None)
    mit_ip = lv.entsperre_konto_und_ip(user, ip)

    assert nur_konto["ip"] == 0
    assert mit_ip["ip"] == 1


def test_leere_ip_wird_ignoriert_statt_als_wildcard_zu_wirken(fake_redis):
    """`ip=""` ist "keine IP genannt", nicht "die IP aller".

    Sonst wuerde ein leerer String einen leeren Hash bauen und damit einen
    Schluessel loeschen, den kein Anmeldepfad je erzeugt — und, schlimmer,
    waere die Aussage "IP freigegeben" fuer einen Aufruf wahr, der es nicht war.
    """
    user, ip = "anna@example.org", "203.0.113.9"
    _sperre_beides(user, ip)

    bericht = lv.entsperre_konto_und_ip(user, "")

    assert bericht["ip"] == 0
    assert not _konto_gesperrt(user)
    assert _ip_gesperrt(ip), "eine leere IP hat die Sperre gehoben"


# ── 4. Das Werkzeugbudget traegt keinen Klartext ────────────────────────────


def test_budget_key_ist_gesalzen_und_nennt_keine_adresse(fake_redis):
    """Auch der Rate-Limit-Key nennt die Adresse nicht im Klartext."""
    key = lv._limit_key("entsperren", "anna@example.org")

    assert key.startswith(lv.WERKZEUGLIMIT_PRAEFIX)
    assert "anna" not in key and "example.org" not in key


def test_budget_zaehlt_je_benutzer_getrennt(fake_redis):
    """Zwei Administratoren verbrauchen ihr Budget nicht gegenseitig."""
    for _ in range(2):
        assert lv.pruefe_werkzeugbudget("entsperren", "chef@example.org", 2, 600)[0]
    erlaubt, rest = lv.pruefe_werkzeugbudget("entsperren", "chef@example.org", 2, 600)
    assert not erlaubt and rest == 0
    # Die Kollegin hat ihr eigenes Budget.
    assert lv.pruefe_werkzeugbudget("entsperren", "pfarrer@example.org", 2, 600)[0]


def test_budget_sperrt_nach_der_grenze(fake_redis):
    for _ in range(3):
        assert lv.pruefe_werkzeugbudget("entsperren", "chef@example.org", 3, 600)[0]
    assert not lv.pruefe_werkzeugbudget("entsperren", "chef@example.org", 3, 600)[0]


def test_budget_ist_je_werkzeug_eigenes(fake_redis):
    """Zwei Werkzeuge, zwei Budgets — sie teilen sich nichts."""
    for _ in range(2):
        assert lv.pruefe_werkzeugbudget("werkzeug-a", "chef@example.org", 2, 600)[0]
    assert not lv.pruefe_werkzeugbudget("werkzeug-a", "chef@example.org", 2, 600)[0]
    assert lv.pruefe_werkzeugbudget("werkzeug-b", "chef@example.org", 2, 600)[0]


def test_budget_ignoriert_gross_klein_und_umraum(fake_redis):
    """Dieselbe Person, nur anders getippt, ist dieselbe Person.

    Sonst wuerde `Chef@Example.ORG` ein frisches Budget bekommen — und die
    Begrenzung waere ein Vorschlagshaken.
    """
    for _ in range(2):
        lv.pruefe_werkzeugbudget("entsperren", "chef@example.org", 2, 600)
    assert not lv.pruefe_werkzeugbudget("entsperren", "  CHEF@Example.ORG ", 2, 600)[0]


def test_budget_verlaengert_ein_laufendes_fenster_nicht(fake_redis):
    """Dauerlast darf das Fenster nicht fortschieben.

    Wenn jeder Aufruf die TTL neu setzt, waere die Grenze bei einem Skript im
    Sekundentakt nie erreicht — die Begrenzung waere dann genau fuer den
    Angreifer unwirksam, gegen den sie dasteht.
    """
    lv.pruefe_werkzeugbudget("entsperren", "chef@example.org", 2, 600)
    erste_ttl = fake_redis.ttl(lv._limit_key("entsperren", "chef@example.org"))

    lv.pruefe_werkzeugbudget("entsperren", "chef@example.org", 2, 600)
    zweite_ttl = fake_redis.ttl(lv._limit_key("entsperren", "chef@example.org"))

    assert 0 < zweite_ttl <= erste_ttl, "das Fenster wurde verlaengert"


def test_budget_ueberlebt_das_ende_des_fensters(fake_redis):
    """Nach Ablauf ist wieder Luft — sonst waere es eine einmalige Sperre."""
    lv.pruefe_werkzeugbudget("entsperren", "chef@example.org", 1, 600)
    assert not lv.pruefe_werkzeugbudget("entsperren", "chef@example.org", 1, 600)[0]

    key = lv._limit_key("entsperren", "chef@example.org")
    fake_redis._ttl[key] = 0.0          # Fenster abgelaufen
    fake_redis._abgelaufen(key)

    assert lv.pruefe_werkzeugbudget("entsperren", "chef@example.org", 1, 600)[0]


def test_werkzeugname_kann_den_namensraum_nicht_verlassen(fake_redis):
    """Ein boesartiger Bezeichner baut keinen Key ausserhalb des Stores."""
    key = lv._limit_key("../../evil", "chef@example.org")

    assert key.startswith(lv.WERKZEUGLIMIT_PRAEFIX)
    assert ".." not in key and "/" not in key


def test_null_ist_ausdruecklich_unlimited(fake_redis):
    """Der Wert 0 heisst "keine Grenze" — und ist nicht der Default.

    Sonst wuerde ein fehlkonfigurierter oder leerer Wert die Begrenzung
    stillschweigend abschalten. Die Settings setzen `>= 1`.
    """
    assert lv.pruefe_werkzeugbudget("entsperren", "chef@example.org", 0, 600) == (True, -1)


def test_default_budget_ist_gesetzt():
    """Ohne ENV startet die App und begrenzt trotzdem — Pflicht der Karte."""
    from diakronos_app.settings import settings

    assert settings.werkzeuglimit_entsperren >= 1
    assert settings.werkzeuglimit_entsperren_fenster >= 1
