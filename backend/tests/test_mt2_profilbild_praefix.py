"""MT-2 — Profilbild speichern: „Nur eigene hochgeladene Dateien erlaubt“.

BEFUND (Manuel, Live-Test 11.11. auf dev.ecg-hn.de, Konto rebekka.fink):
Profilbild-Upload klappte, das Speichern scheiterte mit „Nur eigene
hochgeladene Dateien sind erlaubt.".

URSACHE: Betriebs-Praefix. `upload_file` gibt die Adresse PRAEFIXIERT aus
(`base_path.datei_url`, WEB-5a), die `File`-Zeile in der Datenbank traegt
weiter `/files/<name>`. `update_profile_picture` verglich die Client-URL
zeichengenau mit der DB-Zeile — unter `/diakronos` passte das nie, also 403
fuer die EIGENE Datei.

SOLL (Karte): eigenes Bild speicherbar, fremde Dateien bleiben gesperrt. Die
Sicherheitspruefung wird deshalb NICHT entfernt, sondern am Dateinamen
festgemacht: die DB-Zeile muss existieren, dem Aufrufer gehoeren (`owner`)
und die Datei im Ablageverzeichnis vorhanden sein.

Zusatz aus demselben Befund: `get_my_profile` lieferte `foto` praefixfrei —
der Router praefigiert nur den Schluessel `file_url`. Unter dem Praefix lief
`<img :src="profile.foto">` damit in ein 404; die Ausgabe praefigiert jetzt
an der Quelle.
"""

from __future__ import annotations

import pytest

PROFILE = "diakronos.diakonos.api.profile"
ANNA = "anna@example.org"
BRUNO = "bruno@example.org"


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def zwei(patched_db):
    """Zwei Mitglieder mit eigenem Konto — der Fremdzugriff ist der Pruefstein."""
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    sess.add_all([
        User(name=ANNA, email=ANNA, full_name="Anna Beispiel", enabled=True),
        User(name=BRUNO, email=BRUNO, full_name="Bruno Beispiel", enabled=True),
    ])
    sess.add_all([
        Mitglied(name="M-0001", vorname="Anna", nachname="Beispiel", email=ANNA,
                 status="Mitglied", user=ANNA, docstatus=0, idx=0,
                 wohnort="Stuttgart", postleitzahl="70173"),
        Mitglied(name="M-0002", vorname="Bruno", nachname="Beispiel", email=BRUNO,
                 status="Mitglied", user=BRUNO, docstatus=0, idx=0,
                 wohnort="Esslingen", postleitzahl="73728"),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def praefix(request):
    """Setzt den Betriebs-Praefix fuer die Dauer des Tests (Default: an).

    `request.param` ist der Praefix; die Karte prueft beide Welten, weil der
    Fehler nur MIT Praefix auftrat und der Weg OHNE Praefix unveraendert
    bleiben muss.
    """
    from diakronos_app import base_path

    wert = getattr(request, 'param', '/diakronos')
    alt = base_path.aktiver_praefix()
    base_path.setze_praefix(wert)
    yield wert
    base_path.setze_praefix(alt)


@pytest.fixture()
def dateien(tmp_path, monkeypatch):
    from diakronos_app.settings import settings

    ordner = tmp_path / 'files'
    monkeypatch.setattr(settings, 'files_dir', str(ordner))
    return ordner


def _upload(client, name: str = 'profilbild.jpg'):
    """Der Weg der SPA: erst `upload_file`, dann die zurueckgegebene URL."""
    return client.post('/api/method/upload_file', files={
        'file': (name, b'\xff\xd8\xff\xe0JPEG', 'image/jpeg'),
    }, data={'is_private': '0', 'folder': 'Home/Attachments'})


def _speichern(client, file_url: str):
    return client.post(f'/api/method/{PROFILE}.update_profile_picture',
                       json={'file_url': file_url})


def _foto(client) -> str:
    return client.post(f'/api/method/{PROFILE}.get_my_profile').json()['message']['foto']


def _ohne_praefix(foto: str, praefix: str) -> str:
    """Adresse fuer den TestClient: der Mount-Praefix fehlt dort."""
    return foto[len(praefix):] if praefix and foto.startswith(praefix + '/') else foto


# ── Eigenes Bild: speichern klappt (Kernbefund) ─────────────────────────────


@pytest.mark.parametrize('praefix', ['', '/diakronos'], indirect=True)
def test_eigenes_profilbild_laesst_sich_speichern(
        client, zwei, set_user, dateien, praefix):
    """BEFUND MT-2: mit Praefix war das Speichern der EIGENEN Datei 403.

    Ohne Praefix lief derselbe Weg schon immer — beide werden geprueft, damit
    die Reparatur nicht nur eine der zwei Adressformen kennt.
    """
    set_user(ANNA)
    hochgeladen = _upload(client)
    assert hochgeladen.status_code == 200, hochgeladen.text
    url = hochgeladen.json()['message']['file_url']
    assert url.startswith(praefix + '/files/'), url

    res = _speichern(client, url)
    assert res.status_code == 200, res.text
    assert res.json()['message'] == {'ok': True}

    # Gespeichert wird die DB-Form; ausgegeben wird sie praefigiert — fuer die
    # SPA ist das dieselbe Adresse, die sie gerade hochgeladen hat.
    assert _foto(client) == url


@pytest.mark.parametrize('praefix', ['/diakronos'], indirect=True)
def test_profilbild_datei_ist_unter_dem_praefix_abrufbar(
        client, zwei, set_user, dateien, praefix):
    """Die Anzeige braucht die Datei: die ausgegebene `foto`-Adresse liefert 200.

    Deckt den zweiten Teil des Befunds ab — `get_my_profile` praefigierte
    `foto` nicht, das `<img :src="profile.foto">` lief in ein 404.
    """
    set_user(ANNA)
    url = _upload(client).json()['message']['file_url']
    assert _speichern(client, url).status_code == 200

    foto = _foto(client)
    assert foto.startswith(praefix + '/files/'), foto
    antwort = client.get(_ohne_praefix(foto, praefix))
    assert antwort.status_code == 200
    assert antwort.content.startswith(b'\xff\xd8\xff')


def test_praefixierte_url_wird_als_db_form_gespeichert(
        client, zwei, set_user, dateien, praefix):
    """In der Spalte steht die praefixfreie Form — ein Praefix-Wechsel darf
    das gespeicherte Bild nicht kaputt machen (DB wird nicht migriert)."""
    from diakronos_app.models.diakonos import Mitglied

    set_user(ANNA)
    url = _upload(client).json()['message']['file_url']
    assert _speichern(client, url).status_code == 200

    zwei.expire_all()
    gespeichert = zwei.get(Mitglied, 'M-0001').foto
    assert gespeichert == url[len('/diakronos'):], gespeichert
    assert gespeichert.startswith('/files/')


# ── Fremde Dateien bleiben gesperrt (Sicherheitspruefung) ───────────────────


@pytest.mark.parametrize('praefix', ['', '/diakronos'], indirect=True)
def test_fremde_datei_wird_abgewiesen(client, zwei, set_user, dateien, praefix):
    """Brunos Datei ist fuer Anna tabu — mit UND ohne Praefix."""
    from diakronos_app.models.diakonos import Mitglied

    set_user(BRUNO)
    bruno_url = _upload(client, 'bruno.jpg').json()['message']['file_url']

    set_user(ANNA)
    res = _speichern(client, bruno_url)
    assert res.status_code == 403, res.text
    assert 'Nur eigene hochgeladene Dateien' in res.text

    zwei.expire_all()
    assert zwei.get(Mitglied, 'M-0001').foto is None


def test_unbekannte_datei_wird_abgewiesen(client, zwei, set_user, dateien, praefix):
    """Eine Adresse ohne `File`-Zeile ist kein Eigentumsnachweis."""
    set_user(ANNA)
    res = _speichern(client, '/diakronos/files/gibtsnicht.jpg')
    assert res.status_code == 403, res.text


def test_fehlende_datei_auf_dem_datentraeger_wird_abgewiesen(
        client, zwei, set_user, dateien, praefix):
    """DB-Zeile allein genuegt nicht: die Datei muss vorhanden sein."""
    from diakronos_app.models.diakonos import Mitglied

    set_user(ANNA)
    url = _upload(client).json()['message']['file_url']
    dateien.joinpath(url.rsplit('/', 1)[-1]).unlink()

    res = _speichern(client, url)
    assert res.status_code == 403, res.text
    zwei.expire_all()
    assert zwei.get(Mitglied, 'M-0001').foto is None


@pytest.mark.parametrize('boese', [
    '/diakronos/files/../files/x.jpg',
    '/diakronos/files/%2e%2e%2fx.jpg',
    '/diakronos/private/files/../files/x.jpg',
    'files/x.jpg',
    '/diakronos/files/sub/x.jpg',
    'https://fremd.example.org/files/x.jpg',
])
def test_pfad_ausbruch_und_fremde_herkunft_werden_abgewiesen(
        client, zwei, set_user, dateien, praefix, boese):
    """Nur ein einzelner Dateiname unter `files/` ist eine gueltige Adresse."""
    set_user(ANNA)
    res = _speichern(client, boese)
    assert res.status_code == 403, res.text


# ── Unveraendert: leeren, fremdes Profil, Protokoll ─────────────────────────


def test_leerer_wert_entfernt_das_profilbild(client, zwei, set_user, dateien, praefix):
    set_user(ANNA)
    url = _upload(client).json()['message']['file_url']
    assert _speichern(client, url).status_code == 200

    res = _speichern(client, '')
    assert res.status_code == 200, res.text
    assert _foto(client) == ''


def test_fremdes_profil_bleibt_unberuehrt(client, zwei, set_user, dateien, praefix):
    """Annas Speichern aendert Brunos `foto` nicht."""
    from diakronos_app.models.diakonos import Mitglied

    set_user(BRUNO)
    bruno_url = _upload(client, 'bruno.jpg').json()['message']['file_url']
    assert _speichern(client, bruno_url).status_code == 200

    set_user(ANNA)
    anna_url = _upload(client).json()['message']['file_url']
    assert _speichern(client, anna_url).status_code == 200

    zwei.expire_all()
    assert zwei.get(Mitglied, 'M-0002').foto == bruno_url[len('/diakronos'):]
