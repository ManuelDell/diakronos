"""A1c8 — der Notweg muss sehen, was nach der Konto-Freigabe noch sperrt.

DER BEFUND
----------
Nach fuenf erlaubten Fehlversuchen steht der IP-Fehlversuchszaehler **auf der
Schwelle**: der naechste Versuch dieser Adresse sperrt sie. Steht das Konto
dann auf der Sperre, ist der allergewoehnlichste Fall einer Gemeinde erreicht —
ein Benutzer, ein gemeinsamer Internetanschluss:

    Konto gesperrt, Adresse nur ueber der Schwelle  ->  Notweg sagt "erledigt"
                                                    ->  Anmeldung gibt 401

`zaehle_gesperrte_ips()` sah das nicht: sie zaehlt **Sperren**, und im Store
steht in diesem Fall keine. Live gemessen (echter Redis, DB 14, Worktree-Code
auf c380d96): IP-Zaehler `5`, Schwelle `5`, `zaehle_gesperrte_ips() == 0`,
Notweg `exit 0` — und der danach folgende Anmeldeversuch wurde abgewiesen.

Diese Datei haelt die **Store-Seite** fest: `zaehle_adressen_im_weg()`.
Der Aufrufer (die CLI, `cli_entsperren.py::_ip_hinweis`) sitzt in
`test_a1c6_cli_entsperren.py` — dort steht der Unterprozess.

WAS GEMESSEN UND ENTSCHIEDEN WURDE (Weg a oder b der Karte)
-----------------------------------------------------------
Weg (a) war "abfragen statt zaehlen": laesst sich fragen, ob zu irgendeiner
gesperrten Adresse eine offene Sperrbeziehung zu **diesem** Konto besteht?

**Nein — und das ist gemessen, nicht vermutet.** Der vollstaendige Keyspace im
Fall 2 (echter Redis, nach dem 6. Fehlversuch) besteht aus genau drei Keys:

    diakronos:anmeldesperre:u:<hash(BENUTZER)>          = '300'   (Sperre)
    diakronos:anmeldesperre:u:<hash(BENUTZER)>:stufe    = '1'
    diakronos:loginversuche:ip:<hash(ADRESSE)>          = '5'    (Zaehler)

Es gibt **keinen** Schluessel, der Konto und Adresse verbindet: der Benutzer-
Schluessel traegt den Hash des Benutzernamens, der IP-Zaehler den Hash der
Adresse. Die Zuordnung "welche Adresse gehoert zu diesem Benutzer" existiert im
Store nicht — sie entsteht nur im Moment des Anmeldeversuchs, und
`pruefe_und_merke` merkt sie sich nicht. Ein Scan kann sie deshalb nicht
herstellen; das hiesse einen neuen Indexschluessel, der Benutzer-Hash und
Adress-Hash verknuepft — ein Eingriff in die Sicherheitseigenschaft des
Keyspace ("jemand mit Zugriff auf den Keyspace sieht keine Adressen",
Modulkopf `frappe_compat/loginversuche.py`), auf dem heissen Pfad jedes
Anmeldeversuchs, fuer ein Notfallwerkzeug.

Gemessen wurde auch die Begruendung im Kartentext, der Zaehler-Umfang: eine
Adresse hat im Store **zwei** Zaehler-Keys (einer je Bereich), nicht "Dutzende
bis Tausende". Der Grund fuer den Fehler liegt also woanders — nicht in der
Zahl, sondern darin, dass `zaehle_gesperrte_ips()` nur `anmeldesperre:ip:*`
ansieht und die Zaehler-Schluessel gar nicht oeffnet.

Deshalb wird (a) in der Form gebaut, die der Keyspace hergibt, und **ohne**
die Karte A1c7 umzudrehen: die Exitcode-Semantik bleibt ("0 heisst: es steht
nichts mehr im Weg"), aber die Frage wird jetzt richtig gestellt — nicht "welche
Adresse ist gesperrt", sondern "steht irgendeine Adresse **so** weit, dass der
naechste Versuch sie sperrt". Weg (b) (Semantik umdeuten auf "nur das Konto")
wuerde die Information genau dort entziehen, wo die Karte sie vermisst.

Diese Datei laeuft gegen den **Stub** (schnell, ohne echten Redis). Der echte
Store und der echte Unterprozess stehen in `test_a1c6_cli_entsperren.py`.
"""

from __future__ import annotations

from diakronos_app.frappe_compat import loginversuche as lv

# **A1c10:** das war früher `SCHWELLE = 5`, und die Zahl war fuer den *Konto*
# zaehler richtig und fuer den *Adresszaehler* die Ursache des
# Betriebsausfalls. Diese Datei misst ausschliesslich **Adressen** — deshalb
# steht hier die Adressschwelle (25) und nicht die Kontoschwelle (5).
# Wer sie aus dem Store liest statt sie hier zu schreiben, hat eine Kopie
# mehr; wer sie hart codiert, hat eine weniger. Aus dem Grund des
# Modulkopfes ("eine Quelle der Wahrheit") wird sie gelesen — und der
# Test `test_a1c10_sperren.py` haelt fest, dass die Vorgabe 5/25 lautet.
ADRESSSCHWELLE = lv._max_versuche("ip")

ZIEL = "anna@example.org"
IP_A = "203.0.113.77"
IP_B = "198.51.100.23"


# ── Helfer: Zustaende herstellen, die sich nicht ausschliessen ──────────────


def _zaehler_auf(ip: str, stand: int, bereich: str = lv.BEREICH_LOGIN) -> None:
    """Bringt den IP-Zaehler auf einen **gemessenen** Stand.

    Ueber verschiedene Konten, wie ein Angriff von aussen das tut — sonst
    sperrt zuerst der Benutzerzaehler und die Adresse kommt nie dran. Jeder
    Versuch zaehlt die Adresse mit, `pruefe_und_merke` bricht aber sofort ab,
    sobald eine Schwelle ausloest: bei `stand <= ADRESSSCHWELLE` bleibt es deshalb
    bei genau `stand` Versuchen, ohne dass gesperrt wird.
    """
    for nummer in range(stand):
        erlaubt, _grund = lv.pruefe_und_merke(f"opfer{nummer}@example.org", ip, bereich=bereich)
        assert erlaubt, (
            f"die Adresse wurde bei {nummer + 1} Versuchen gesperrt — der Test "
            "will aber nur den Zaehler stellen, keine Sperre"
        )


def _zaehler_dann_sperre(ip: str, stand: int, zaehler_bereich: str) -> None:
    """Der Zustand, um den es hier geht: **Zaehler auf der Schwelle und
    gesperrt, an derselben Adresse.**

    Die Reihenfolge ist nicht frei waehlbar, und das ist der interessante
    Teil: `pruefe_und_merke` prueft die Sperre **bereichsuebergreifend** (der
    Sperrschluessel traegt keinen Bereich, Modulkopf A1c2). Ist die Adresse
    also schon gesperrt, blockiert **jeder** weitere Versuch — auch der des
    anderen Bereichs — und der zweite Zaehler steigt nie. Wer in dieser
    Reihenfolge testet, baut einen Zustand, den das Produkt gar nicht
    erzeugen kann, und prueft nichts.

    Erreichbar ist er nur andersherum, und genau so kommt er in echt vor:

        1. ein Bereich zaehlt bis zur Schwelle (hier der CalDAV-Zaehler),
        2. der andere Bereich laesst **darueber** hinausgehen — das loest die
           Sperre aus und loescht **nur seinen eigenen** Zaehler.

    Der CalDAV-Zaehler bleibt dabei auf der Schwelle stehen, und die Adresse
    traegt jetzt beides: einen Sperrschluessel und einen Zaehler, der beim
    naechsten Versuch ebenfalls sperren wuerde.
    """
    _zaehler_auf(ip, stand, bereich=zaehler_bereich)

    # Der zweite Bereich geht ueber die Schwelle. Der Zaehler dieses
    # Bereichs wird dabei geloescht — der erste nicht.
    for nummer in range(stand + 1):
        lv.pruefe_und_merke(f"opfer{nummer}@example.org", ip, bereich=lv.BEREICH_LOGIN)


def _zaehler_lesen(ip: str, bereich: str = lv.BEREICH_LOGIN) -> int:
    client = lv._client()
    for _art, zaehler, _sperr in lv._kennungen(None, ip, bereich):
        roh = client.get(zaehler)
        if roh is not None:
            return int(roh)
    return 0


# ── 1. Der Normalfall: nichts steht im Weg ──────────────────────────────────


def test_im_unauffaelligen_store_steht_nichts_im_weg(fake_redis):
    assert lv.zaehle_adressen_im_weg() == 0


def test_drei_vertippten_sind_kein_notfall(fake_redis):
    """Der haeufigste Fall darf keinen Alarm ausloesen.

    Wer sich dreimal im Browser vertippt, ist kein Notfall. Sobald der Befehl
    hier schon "offen" meldet, ist Exitcode 2 wertlos — und ein Skript bricht
    im Alltag aus.
    """
    for _ in range(3):
        lv.pruefe_und_merke(ZIEL, IP_A)

    assert _zaehler_lesen(IP_A) == 3
    assert lv.zaehle_adressen_im_weg() == 0


# ── 2. Die Grenze ist die Schwelle, und die Schwelle ist inklusiv ───────────


def test_auf_der_schwelle_steht_die_adresse_im_weg(fake_redis):
    """**Der Messfall der Karte.** Zaehler == Schwelle, keine Sperre im Store.

    `pruefe_und_merke` sperrt bei `zaehler > schwelle` und loescht den Zaehler
    dabei. Ein Zaehler kann deshalb nie *ueber* der Schwelle stehen — er
    erreicht sie, und der **naechste** Versuch dieser Adresse sperrt sie. Wer
    nur auf `>` prueft, haette genau hier blind.
    """
    _zaehler_auf(IP_A, ADRESSSCHWELLE)

    assert lv.zaehle_gesperrte_ips() == 0, (
        "Ausgangslage ist nicht der Messfall: es steht eine Sperre im Store"
    )
    assert _zaehler_lesen(IP_A) == ADRESSSCHWELLE
    assert lv.zaehle_adressen_im_weg() == 1, (
        "die Adresse steht auf der Schwelle und sperrt beim naechsten Versuch — "
        "der Notweg muss das sehen"
    )


def test_eine_stufe_unter_der_schwelle_steht_noch_nicht_im_weg(fake_redis):
    """Die Grenze sitzt genau auf der Schwelle, nicht darueber.

    Wer `zaehler > schwelle` prueft, wuerde diese Adresse ebenfalls melden und
    den Exitcode 2 an den Alltagsfall kleben. Wer `zaehler < schwelle` prueft,
    verliert den Messfall. Beides wird hier festgenagelt.
    """
    _zaehler_auf(IP_A, ADRESSSCHWELLE - 1)

    assert lv.zaehle_adressen_im_weg() == 0, (
        "eine Adresse kurz unter der Schwelle sperrt beim naechsten Versuch nicht"
    )

    _zaehler_auf(IP_A, 1)  # auf die Schwelle
    assert lv.zaehle_adressen_im_weg() == 1


def test_eine_gesperrte_adresse_steht_auch_im_weg(fake_redis):
    """Der Fall aus A1c6 bleibt erhalten: Sperre, nicht nur Zaehler."""
    for nummer in range(ADRESSSCHWELLE + 1):
        lv.pruefe_und_merke(f"opfer{nummer}@example.org", IP_A)

    assert lv.ist_gesperrt(None, IP_A), "Ausgangslage: die Adresse ist nicht gesperrt"
    assert lv.zaehle_adressen_im_weg() == 1


# ── 3. Zwei unabhaengige Faelle nebeneinander (ZUSATZBEFUND) ────────────────


def test_gesperrt_und_nur_zaehler_ueber_der_schwelle_sind_zwei_faelle(fake_redis):
    """Die Verwechslung darf nicht unsichtbar bleiben.

    `zaehle_gesperrte_ips()` sah nur den einen Fall und nannte fuer den anderen
    eine Null — daher die Luege. Dieser Test legt deshalb **beide** Faelle
    nebeneinander: eine Adresse wirklich gesperrt, eine andere nur auf der
    Schwelle. Erwartet wird: die Sperre zaehlt **1**, der Zaehlerstand
    zaehlt **mit**, zusammen also **2**. Wer die beiden Faelle wieder
    vermischt, sieht es hier.
    """
    # Fall 1 — Sperre.
    for nummer in range(ADRESSSCHWELLE + 1):
        lv.pruefe_und_merke(f"opfer{nummer}@example.org", IP_A)
    # Fall 2 — nur Zaehler auf der Schwelle, an einer ANDEREN Adresse.
    _zaehler_auf(IP_B, ADRESSSCHWELLE)

    assert lv.ist_gesperrt(None, IP_A) is True
    assert lv.ist_gesperrt(None, IP_B) is False, "Fall 2 darf keine Sperre haben"

    assert lv.zaehle_gesperrte_ips() == 1, "nur Fall 1 ist eine gesperrte Adresse"
    assert lv.zaehle_adressen_im_weg() == 2, "beide Adressen stehen im Weg"


def test_je_adresse_zaehlt_es_einmal_und_nicht_je_zaehler(fake_redis):
    """Zwei Bereiche, eine Adresse, eine Zahl.

    Die Sperre ist bereichsuebergreifend, die Zaehler sind es nicht. Ein
    Zaehler-Key je Bereich (hier zwei) darf deshalb **nicht** zweimal
    gezaehlt werden — sonst meldet derselbe Zustand eine Zahl, die von der
    Liste der Bereiche abhaengt und nicht vom Bestand.
    """
    for bereich in lv.BEREICHE:
        _zaehler_auf(IP_A, ADRESSSCHWELLE, bereich=bereich)

    assert _zaehler_lesen(IP_A, lv.BEREICH_LOGIN) == ADRESSSCHWELLE
    assert _zaehler_lesen(IP_A, lv.BEREICH_CALDAV) == ADRESSSCHWELLE
    assert lv.zaehle_adressen_im_weg() == 1, (
        "eine Adresse steht im Weg — nicht eine je Bereich"
    )


def test_gesperrt_und_zaehler_auf_der_schwelle_an_derselben_adresse_zaehlt_einmal(fake_redis):
    """**Regression:** Sperre **und** Zaehlerstand an *einer* Adresse = 1.

    Die beiden Faelle der Karte treffen sich an **derselben** Adresse, wenn
    die Bereiche auseinanderlaufen: der CalDAV-Zaehler steht auf der
    Schwelle, der Login-Bereich geht darueber hinaus und sperrt. Die Adresse
    traegt dann einen Sperrschluessel **und** einen Zaehler auf der Schwelle
    (`_zaehler_dann_sperre` zeigt, warum das in dieser Reihenfolge geht und
    nicht andersherum).

    Genau hier laeuft eine Vereinigung schief, wenn die beiden Seiten
    unterschiedliche Formen liefern. Der Sperrpfad liefert dann den
    **vollen Schluessel** (`diakronos:anmeldesperre:ip:<hash>`), der
    Zaehlerpfad den **nackten Hash** — die Mengen ueberlappen nie, und
    dieselbe Adresse wird zweimal gezaehlt. In der ersten Fassung dieser
    Karte war genau das so; dieser Test ist der Grund, warum es jetzt
    stimmt.
    """
    _zaehler_dann_sperre(IP_A, ADRESSSCHWELLE, zaehler_bereich=lv.BEREICH_CALDAV)

    assert lv.ist_gesperrt(None, IP_A) is True, "Fall 1: Sperre muss stehen"
    assert _zaehler_lesen(IP_A, lv.BEREICH_CALDAV) == ADRESSSCHWELLE, (
        "Fall 2: der CalDAV-Zaehler dieser Adresse steht auf der Schwelle"
    )
    assert _zaehler_lesen(IP_A, lv.BEREICH_LOGIN) == 0, (
        "der ausloesende Zaehler wurde bei der Sperre geloescht"
    )

    assert lv.zaehle_adressen_im_weg() == 1, (
        "eine Adresse, zweimal gemeldet — die Sperre und ihr eigener "
        "Zaehlerstand sind derselbe Adressblock"
    )


def test_eine_adresse_erscheint_im_bericht_mit_ihrem_eigenen_zaehler_nicht_zweimal(fake_redis):
    """Dieselbe Adresse, einmal freigegeben — der Restcheck meldet sie einmal.

    Das ist der Weg, den der Notweg wirklich geht: `entsperre_konto_und_ip`
    raeumt das **Konto** ab, die Adresse bleibt. Steht dieselbe Adresse
    gleichzeitig ueber der Schwelle, darf der Restcheck sie nicht doppelt
    melden — das wuerde als "zwei Adressen im Weg" lesen und den Bericht
    sinnlos machen.
    """
    _zaehler_dann_sperre(IP_A, ADRESSSCHWELLE, zaehler_bereich=lv.BEREICH_CALDAV)

    assert lv.zaehle_adressen_im_weg() == 1
    # Und die Konto-Freigabe raeumt die Adresse nicht ab — sie darf die
    # Zahl also weder heben (falsche Entwarnung) noch verdoppeln.
    lv.zuruecksetzen_alles(ZIEL)
    assert lv.zaehle_adressen_im_weg() == 1, "die Konto-Freigabe raeumt die Adresse nicht ab"


def test_die_backoff_stufe_ist_keine_zweite_adresse(fake_redis):
    """`:stufe` ist die Stufe derselben Sperre, kein eigener Eintrag."""
    for nummer in range(ADRESSSCHWELLE + 1):
        lv.pruefe_und_merke(f"opfer{nummer}@example.org", IP_A)

    client = lv._client()
    stufen = [
        k.decode() if isinstance(k, bytes) else str(k)
        for k in client.scan_iter(match=f"{lv.SPERRE_PRAEFIX}ip:*")
    ]
    assert any(k.endswith(":stufe") for k in stufen), (
        "Ausgangslage fehlt: es gibt keine Backoff-Stufe, der Test prueft nichts"
    )

    assert lv.zaehle_adressen_im_weg() == 1, "die Stufe wurde mitgezaehlt"


# ── 4. Der CalDAV-Zaehler zaehlt, weil die Freigabe beide Bereiche umfasst ──


def test_der_caldav_zaehler_allein_steht_schon_im_weg(fake_redis):
    """Der Notweg gibt Login **und** CalDAV frei — beide Zaehler sind es auch.

    Wer sich am Kalender die Finger vertippt hat, ist aus der SPA nicht
    ausgesperrt, aber aus seinem Kalender schon. Die Freigabe raeumt beides ab
    (`BEREICHE`), also muss die Frage nach dem Rest auch beide Bereiche
    betrachten.
    """
    _zaehler_auf(IP_A, ADRESSSCHWELLE, bereich=lv.BEREICH_CALDAV)

    assert lv.ist_gesperrt(None, IP_A) is False, "es ist keine Sperre entstanden"
    assert lv.zaehle_adressen_im_weg() == 1


# ── 5. Der Kontenzaehler gehoert NICHT in diese Frage ───────────────────────


def test_der_kontenzaehler_einer_anderen_person_zaehlt_nicht(fake_redis):
    """Nur Adressen — und das ist keine Vereinfachung, sondern die Begruendung.

    Die Konto-Freigabe loescht **jeden** Kontenzaehler, in allen Bereichen
    (`zuruecksetzen_alles`, `BEREICHE`). Ein Kontenzaehler auf der Schwelle kann
    also nach dem Aufraehrweg nichts mehr blockieren — er ist weg. Nur, was der
    Aufraehrweg **nicht** anfasst, kann danach noch sperren, und das sind genau
    die Adressen. Deshalb fragt diese Funktion nach Adressen und nicht nach
    beidem: ein Kontenzaehler hier zu zaehlen hiesse Alarm ohne Ursache.
    """
    for nummer in range(ADRESSSCHWELLE + 1):
        lv.pruefe_und_merke(ZIEL, None, bereich=lv.BEREICH_LOGIN)

    assert _zaehler_lesen(IP_A) == 0
    assert lv.zaehle_adressen_im_weg() == 0, (
        "ein Kontenzaehler blockiert nach der Freigabe nichts"
    )

    # Und die Freigabe raeumt ihn wirklich ab, damit die Aussage stimmt.
    lv.zuruecksetzen_alles(ZIEL)
    assert lv.gib_bericht(ZIEL, None) == {"u": 0, "ip": 0}


# ── 6. Was der alte Zaehler sah — die Luege als Beleg ───────────────────────


def test_der_alte_zaehler_sah_genau_diesen_fall_nicht(fake_redis):
    """Die Behauptung dieser Karte, als Test: der alte Zaehler sagt 0.

    Wer `zaehle_gesperrte_ips()` in eine "optimierte" Fassung zurueckbaut, die
    nur Sperren zaehlt, sieht hier, dass wieder eine Luege zurueckkommt. Die
    Beide-Faelle-Pruefung oben haelt fest, dass es **beide** braucht — diese
    hier haelt fest, welcher der beiden der alte Stand verfehlt hat.
    """
    _zaehler_auf(IP_A, ADRESSSCHWELLE)

    assert lv.zaehle_gesperrte_ips() == 0
    assert lv.zaehle_adressen_im_weg() == 1


def test_lesen_aendert_nichts(fake_redis):
    """Rein lesend — wie der ganze Berichtsweg seit A1c6."""
    _zaehler_auf(IP_A, ADRESSSCHWELLE)

    vorher = _zaehler_lesen(IP_A)
    assert lv.zaehle_adressen_im_weg() == 1
    assert lv.zaehle_adressen_im_weg() == 1, "zweites Lesen meldet etwas anderes"
    assert _zaehler_lesen(IP_A) == vorher, "das Lesen hat den Zaehler veraendert"
