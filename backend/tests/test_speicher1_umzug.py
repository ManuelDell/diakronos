"""SPEICHER-1 — Umzugswerkzeug: kopieren, pruefen, NICHTS loeschen.

Geprueft wird:

1. **Umzug lokal -> Nextcloud** landet vollstaendig im Ziel, mit stimmiger
   Pruefsumme — und die QUELLE ist danach unveraendert (Kartenvorgabe 5:
   „loescht lokal NICHT“).
2. **Probelauf** schreibt NICHTS: keine Datei im Ziel, keine einzige Anfrage
   an den WebDAV-Fake (auch kein MKCOL/PROPFIND-PUT).
3. **Wiederholbarkeit**: ein zweiter Lauf schreibt nichts erneut, was schon
   identisch vorliegt (Abbruch nach der Haelfte kostet nicht alles).
4. **Abweichung wird erkannt**: liefert das Ziel andere Bytes, gilt die Datei
   als Fehler — nicht als uebertragen.
5. **CLI**: Aufrufform ``--nach nextcloud [--probelauf]``, Exit-Codes 0/1/2.

Der WebDAV-Fake kommt aus ``test_speicher1_vertrag`` — EIN Fake, keine zweite
Wahrheit ueber das WebDAV-Verhalten.
"""

from __future__ import annotations

import hashlib

import httpx
import pytest

from diakronos_app.speicher import Lokal
from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang
from diakronos_app.speicher.umzug import Ergebnis, main, umzug

from test_speicher1_vertrag import BASIS, URL, FakeWebDAV

ZUGANG = ("diakronos", "geheim-app-passwort")


def _nextcloud(fake: FakeWebDAV) -> Nextcloud:
    zugang = NextcloudZugang(URL, *ZUGANG, "/Diakronos", versuche=1)
    client = httpx.Client(transport=httpx.MockTransport(fake),
                          auth=ZUGANG, trust_env=False)
    ablage = Nextcloud(zugang, client=client)
    ablage.wartezeiten = (0.0,)
    return ablage


@pytest.fixture()
def fake() -> FakeWebDAV:
    """Der WebDAV-Fake aus dem Vertragstest (EIN Fake, kein zweiter)."""
    return FakeWebDAV()


@pytest.fixture()
def bestand(tmp_path):
    """Eine lokale Ablage mit drei Dateien (flach + Unterordner)."""
    quelle = Lokal(tmp_path / "files")
    quelle.schreiben("foto.png", b"\x89PNG-abc")
    quelle.schreiben("devmodus/2026-10-15/bild.jpg", b"\xff\xd8\xff-inhalt")
    quelle.schreiben("notes/leer.txt", b"")
    return quelle


# ── 1. Der Umzug selbst ────────────────────────────────────────────────────


def test_umzug_kopiert_alles_und_prueft(bestand, fake):
    ziel = _nextcloud(fake)
    ergebnis = umzug(bestand, ziel)
    assert ergebnis.erfolgreich, ergebnis.fehler
    assert ergebnis.uebertragen == 3
    assert ziel.lesen("foto.png") == b"\x89PNG-abc"
    assert ziel.lesen("devmodus/2026-10-15/bild.jpg") == b"\xff\xd8\xff-inhalt"
    assert ziel.lesen("notes/leer.txt") == b""


def test_umzug_loescht_die_quelle_nicht(bestand, fake):
    """Kartenvorgabe 5: lokal wird NICHTS geloescht."""
    vorher = {s: bestand.lesen(s) for s in bestand.auflisten()}
    umzug(bestand, _nextcloud(fake))
    assert bestand.auflisten() == sorted(vorher)
    for schluessel, daten in vorher.items():
        assert bestand.lesen(schluessel) == daten


def test_umzug_haengt_nicht_an_der_leseposition(tmp_path, fake):
    """Gelesen wird ab Dateianfang — nicht ab „wo die Pruefsumme aufgehoert hat“.

    Beim Umzug wird jede Datei ZWEIMAL geoeffnet (Pruefsumme, dann Kopie).
    Wer ``lesen_rest()`` auf einem halb gelesenen Objekt aufruft, kopiert nur
    den Rest — die Kopie waere zu kurz und die Pruefsumme falsch. Hier mit
    Inhalt, der groesser als ein Block ist.
    """
    grosse_datei = bytes(range(256)) * 4096  # 1 MiB, mehrere Bloecke
    quelle = Lokal(tmp_path / "files")
    quelle.schreiben("gross.bin", grosse_datei)
    ziel = _nextcloud(fake)
    ergebnis = umzug(quelle, ziel)
    assert ergebnis.erfolgreich, ergebnis.fehler
    assert len(ziel.lesen("gross.bin")) == len(grosse_datei)
    assert ziel.lesen("gross.bin") == grosse_datei


def test_umzug_prueft_groesse_und_pruefsumme(bestand, fake):
    """Belegt am Ziel: was dort liegt, hat dieselbe Summe wie die Quelle."""
    ziel = _nextcloud(fake)
    umzug(bestand, ziel)
    for schluessel in bestand.auflisten():
        assert hashlib.sha256(ziel.lesen(schluessel)).digest() == \
               hashlib.sha256(bestand.lesen(schluessel)).digest()


def test_umzug_nur_ein_unterordner(bestand, fake):
    ziel = _nextcloud(fake)
    ergebnis = umzug(bestand, ziel, praefix="devmodus")
    assert ergebnis.erfolgreich
    assert ziel.auflisten() == ["devmodus/2026-10-15/bild.jpg"]


def test_umzug_rueckweg_nextcloud_nach_lokal(bestand, fake, tmp_path):
    """Derselbe Vorgang mit getauschten Seiten (Rueckfallebene)."""
    cloud = _nextcloud(fake)
    umzug(bestand, cloud)
    zurueck = Lokal(tmp_path / "zurueck")
    ergebnis = umzug(cloud, zurueck)
    assert ergebnis.erfolgreich
    assert zurueck.lesen("foto.png") == b"\x89PNG-abc"


# ── 2. Probelauf ───────────────────────────────────────────────────────────


def test_probelauf_schreibt_nichts(bestand, fake):
    ziel = _nextcloud(fake)
    ergebnis = umzug(bestand, ziel, probelauf=True)
    assert ergebnis.erfolgreich
    assert ergebnis.probelauf is True
    assert len(ergebnis.geplant) == 3
    # Kein PUT, kein MKCOL — und im Fake liegt nichts.
    assert [m for m, _ in fake.anfragen if m in ("PUT", "MKCOL")] == []
    assert fake.dateien == {}


def test_probelauf_meldet_was_er_tun_wuerde(bestand, fake):
    ziel = _nextcloud(fake)
    ergebnis = umzug(bestand, ziel, probelauf=True)
    assert sorted(ergebnis.geplant) == sorted(bestand.auflisten())
    assert ergebnis.uebertragen == 3
    text = "\n".join(ergebnis.zeilen())
    assert "Probelauf" in text
    assert "NICHTS geloescht" not in text  # nur beim echten Lauf


# ── 3. Wiederholbarkeit ────────────────────────────────────────────────────


def test_zweiter_lauf_schreibt_nichts_erneut(bestand, fake):
    ziel = _nextcloud(fake)
    umzug(bestand, ziel)
    anzahl_put = [m for m, _ in fake.anfragen].count("PUT")
    ergebnis = umzug(bestand, ziel)
    assert ergebnis.erfolgreich
    assert ergebnis.vorhanden == 3
    assert ergebnis.uebertragen == 0
    assert [m for m, _ in fake.anfragen].count("PUT") == anzahl_put


def test_geaenderte_datei_wird_ersetzt(bestand, fake):
    ziel = _nextcloud(fake)
    umzug(bestand, ziel)
    bestand.schreiben("foto.png", b"neuer-inhalt")
    ergebnis = umzug(bestand, ziel)
    assert ergebnis.erfolgreich
    assert ziel.lesen("foto.png") == b"neuer-inhalt"


# ── 4. Abweichung wird erkannt ─────────────────────────────────────────────


def test_abweichende_pruefsumme_gilt_als_fehler(bestand, fake):
    """Schreibt das Ziel andere Bytes, ist die Datei NICHT uebertragen."""
    ziel = _nextcloud(fake)

    class Verfaelschend(Nextcloud):
        def schreiben(self, schluessel, daten):  # type: ignore[override]
            return super().schreiben(schluessel, b"verfaelscht")

    verfaelscht = Verfaelschend(ziel.zugang, client=ziel._client)
    verfaelscht.wartezeiten = (0.0,)
    ergebnis = umzug(bestand, verfaelscht)
    assert ergebnis.erfolgreich is False
    assert {grund for _, grund in ergebnis.fehler} == {"Pruefsumme/Groesse weicht ab"}


def test_unlesbare_quelle_ist_ein_fehler(tmp_path, fake):
    """Ein Fehler in EINER Datei haelt die anderen nicht auf."""
    quelle = Lokal(tmp_path / "files")
    quelle.schreiben("gut.png", b"ok")

    class TeilsKaputt(Lokal):
        def oeffnen(self, schluessel):  # type: ignore[override]
            if schluessel == "kaputt.png":
                raise OSError("Platte weg")
            return super().oeffnen(schluessel)

    teil = TeilsKaputt(tmp_path / "files")
    (tmp_path / "files" / "kaputt.png").write_bytes(b"x")
    ergebnis = umzug(teil, _nextcloud(fake))
    assert ergebnis.uebertragen == 1
    assert [s for s, _ in ergebnis.fehler] == ["kaputt.png"]


def test_nicht_erreichbares_ziel_wird_gemeldet(bestand, fake):
    fake.antworten = [("PUT", 503)] * 10
    ziel = _nextcloud(fake)
    ergebnis = umzug(bestand, ziel)
    assert ergebnis.erfolgreich is False
    assert ergebnis.uebertragen == 0
    assert ergebnis.fehler


# ── 5. CLI ─────────────────────────────────────────────────────────────────


def test_cli_verlangt_ein_ziel():
    with pytest.raises(SystemExit):
        main([])


def test_cli_lehnt_unbekanntes_ziel_ab():
    with pytest.raises(SystemExit):
        main(["--nach", "papierkorb"])


def test_cli_gleiche_quelle_und_ziel_ist_aufruffehler(capsys):
    assert main(["--nach", "lokal", "--von", "lokal"]) == 2
    assert "gleich" in capsys.readouterr().err


def test_cli_fehlende_nextcloud_einstellung_ist_aufruffehler(monkeypatch, capsys):
    """Ohne Zugangsdaten: Exit 2 mit Namen der fehlenden Werte, KEIN Wert."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "nextcloud_url", "", raising=False)
    monkeypatch.setattr(settings, "nextcloud_benutzer", "", raising=False)
    monkeypatch.setattr(settings, "nextcloud_app_passwort", "", raising=False)
    assert main(["--nach", "nextcloud"]) == 2
    fehler = capsys.readouterr().err
    assert "NEXTCLOUD_URL" in fehler
    assert "NEXTCLOUD_APP_PASSWORT" in fehler


def test_cli_umzug_gegen_fake_laeuft_durch(monkeypatch, bestand, fake, capsys):
    """Voller CLI-Weg mit In-Process-WebDAV (kein Netz, kein echter Server)."""
    import diakronos_app.speicher.umzug as umzug_modul

    ziel = _nextcloud(fake)
    monkeypatch.setattr(umzug_modul, "_ablage_fuer",
                        lambda name: ziel if name == "nextcloud" else bestand)
    assert main(["--nach", "nextcloud", "--von", "lokal", "--still"]) == 0
    ausgabe = capsys.readouterr().out
    assert "uebertragen: 3" in ausgabe
    assert "NICHTS geloescht" in ausgabe
    assert len(fake.dateien) == 3


def test_ergebnis_erfolgreich_ist_an_fehler_gebunden():
    assert Ergebnis().erfolgreich is True
    assert Ergebnis(fehler=[("a", "b")]).erfolgreich is False
