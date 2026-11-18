"""SPEICHER-1 — die umgestellten ROUTEN liefern auch aus der Nextcloud aus.

Der Vertragstest (``test_speicher1_vertrag``) prueft die Ablage selbst. Hier
geht es um das, was der Browser sieht: ``/files/<name>``,
``/gemeinde/logo`` und das Formularbild muessen ihre Bytes auch dann liefern,
wenn die Ablage **keinen lokalen Pfad** hat (Nextcloud).

Warum das eine eigene Datei verdient: bei der Nextcloud-Ablage ist ``pfad()``
``None``. Ein Aufrufer, der trotzdem ``FileResponse(pfad)`` baut, ist zur
Laufzeit kaputt — aber nur, wenn ``SPEICHER_BACKEND=nextcloud`` gesetzt ist.
Genau dieser Zustand wird hier hergestellt: die Ablage wird auf einen
In-Process-WebDAV-Fake gestellt, und die vorhandenen Routen muessen weiter
antworten (mit denselben Rechten, denselben Typen, denselben Kopfzeilen).

Kein Netz, kein echter Nextcloud-Server (Kartenvorgabe 6).
"""

from __future__ import annotations

import httpx
import pytest

from diakronos_app.speicher import setze_speicher, vergiss_speicher
from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang

from test_speicher1_vertrag import FakeWebDAV, URL

ZUGANG = ("diakronos", "geheim-app-passwort")

#: 1×1-PNG (echte Signatur + IHDR + IEND), damit die Magic-Bytes greifen.
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture()
def fake() -> FakeWebDAV:
    return FakeWebDAV()


@pytest.fixture()
def cloud(fake):
    """Die Ablage fest auf Nextcloud stellen — nach dem Test wieder zurueck."""
    zugang = NextcloudZugang(URL, *ZUGANG, "/Diakronos", versuche=1)
    client = httpx.Client(transport=httpx.MockTransport(fake),
                          auth=ZUGANG, trust_env=False)
    ablage = Nextcloud(zugang, client=client)
    ablage.wartezeiten = (0.0,)
    setze_speicher(ablage)
    try:
        yield ablage
    finally:
        vergiss_speicher()


def test_datei_wird_aus_der_nextcloud_ausgeliefert(client, set_user, cloud, fake):
    """``GET /files/<name>`` liefert die Bytes — ohne lokalen Dateipfad."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    cloud.schreiben("abc-def.png", PNG)
    with SessionLocal() as sess:
        sess.add(FileModel(name="f-cloud1", file_name="def.png",
                           file_url="/files/abc-def.png", is_private=0,
                           owner="Administrator", modified_by="Administrator"))
        sess.commit()

    set_user("Mitglied A")
    antwort = client.get("/files/abc-def.png")
    assert antwort.status_code == 200, antwort.text
    assert antwort.content == PNG
    assert antwort.headers["content-type"] == "image/png"
    # Dieselben Schutz-Kopfzeilen wie beim lokalen Weg.
    assert antwort.headers["x-content-type-options"] == "nosniff"
    assert antwort.headers["cache-control"] == "private, no-store"


def test_unbekannte_datei_bleibt_404(client, set_user, cloud):
    set_user("Mitglied A")
    antwort = client.get("/files/gibtsnicht.png")
    assert antwort.status_code == 404


def test_fehlende_datei_trotz_datensatz_ist_404(client, set_user, cloud):
    """``File``-Zeile ja, Datei nein: 404 (nicht 500, nicht leeres 200)."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    with SessionLocal() as sess:
        sess.add(FileModel(name="f-cloud2", file_name="weg.png",
                           file_url="/files/weg.png", is_private=0,
                           owner="Administrator", modified_by="Administrator"))
        sess.commit()
    set_user("Mitglied A")
    assert client.get("/files/weg.png").status_code == 404


def test_gemeinde_logo_kommt_aus_der_nextcloud(client, cloud):
    """Die oeffentliche Logo-Route liefert die Bytes samt SVG-Kopfzeilen."""
    name = "gemeinde-logo-" + "a" * 32 + ".png"
    cloud.schreiben(name, PNG)

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )

    with SessionLocal() as sess:
        zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
        if zeile is None:
            zeile = GemeindeEinstellungen(name=GEMEINDE_EINSTELLUNGEN_NAME)
            sess.add(zeile)
        zeile.logo_datei = name
        sess.commit()

    antwort = client.get("/gemeinde/logo")
    assert antwort.status_code == 200, antwort.text
    assert antwort.content == PNG
    assert antwort.headers["content-type"] == "image/png"
    assert "sandbox" in antwort.headers["content-security-policy"]


def test_formularbild_kommt_aus_der_nextcloud(cloud):
    """``oeffne_formularbild`` + ``formularbild_daten`` ohne lokalen Pfad."""
    from diakronos_app.anmeldung.formularbilder import (
        formularbild_daten,
        oeffne_formularbild,
    )

    cloud.schreiben("reg1a-bild.png", PNG)
    pfad, typ = oeffne_formularbild("reg1a-bild.png")
    assert pfad is None, "Nextcloud hat keinen lokalen Pfad"
    assert typ == "image/png"
    assert formularbild_daten("reg1a-bild.png") == PNG
    # Kein Rasterbild -> kein Formularbild (unveraenderte Regel).
    cloud.schreiben("reg1a-text.png", b"<html>kein Bild</html>")
    assert oeffne_formularbild("reg1a-text.png") is None


def test_devmodus_bild_laesst_sich_lesen(cloud):
    """``dienste.bild_pfad`` liefert eine Lesequelle statt eines Pfads."""
    from diakronos_app.devmodus import dienste

    schluessel = "devmodus/2026-10-15/" + "b" * 16 + ".png"
    cloud.schreiben(schluessel, PNG)
    quelle = dienste.bild_pfad(schluessel)
    assert quelle is not None
    with quelle:
        assert quelle.ganz() == PNG
    # Fremder Pfad bleibt abgewiesen (unveraendertes Muster).
    assert dienste.bild_pfad("devmodus/2026-10-15/../../etc/passwd") is None


def test_upload_legt_in_der_nextcloud_ab(client, set_user, cloud, fake):
    """``upload_file`` schreibt in die Ablage — auch wenn sie Nextcloud ist."""
    set_user("Administrator")
    antwort = client.post(
        "/api/method/upload_file",
        files={"file": ("probe.png", PNG, "image/png")},
        data={"is_private": "0"},
    )
    assert antwort.status_code == 200, antwort.text
    url = antwort.json()["message"]["file_url"]
    name = url.rsplit("/", 1)[1]
    # Genau EINE Datei liegt im WebDAV-Baum, und es ist die hochgeladene.
    assert list(fake.dateien) == [
        "/remote.php/dav/files/diakronos/Diakronos/" + name
    ]
    assert fake.dateien[list(fake.dateien)[0]] == PNG


def test_ausliefern_nennt_keine_nextcloud_adresse(client, set_user, cloud):
    """Eine WebDAV-Adresse darf in KEINER Antwort an den Browser stehen."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    cloud.schreiben("no-leak.png", PNG)
    with SessionLocal() as sess:
        sess.add(FileModel(name="f-cloud3", file_name="no-leak.png",
                           file_url="/files/no-leak.png", is_private=0,
                           owner="Administrator", modified_by="Administrator"))
        sess.commit()
    set_user("Mitglied A")
    antwort = client.get("/files/no-leak.png")
    assert antwort.status_code == 200
    for kopf, wert in antwort.headers.items():
        assert "remote.php" not in wert, kopf
        assert URL not in wert, kopf
    assert b"remote.php" not in antwort.content
