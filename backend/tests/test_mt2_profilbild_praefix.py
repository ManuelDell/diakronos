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


# ── MT-2b: Ausbruch-Varianten gegen eine ECHTE fremde Datei ─────────────────
# Die Varianten oben nennen `x.jpg`, die es gar nicht gibt — sie waeren auch
# ohne jede Pfadpruefung gruen (die File-Zeile fehlt ja). Hier steht eine
# WIRKLICH vorhandene Datei einer anderen Person (Bruno) hinter jeder
# Variante: nur dann beweist ein 403, dass die Pruefung greift und nicht die
# blosse Nichtexistenz.


def _bruno_datei(client, set_user) -> tuple[str, str]:
    """Brunos eigene Datei hochladen; (praefigierte URL, Dateiname)."""
    set_user(BRUNO)
    bruno_url = _upload(client, 'bruno.jpg').json()['message']['file_url']
    return bruno_url, bruno_url.rsplit('/', 1)[-1]


def _varianten(url: str, name: str) -> dict[str, str]:
    return {
        # {p}/files/<name> — die echte, fremde Adresse.
        'fremde_url': url,
        # /private/files/<name> — anderer Ablagezweig, gleicher Name.
        'private_zweig': f'/private/files/{name}',
        # ../ — Ausbruch aus `files/`.
        'punkt_punkt': f'/files/../files/{name}',
        # doppeltes Praefix.
        'doppeltes_praefix': f'/diakronos{url}',
        # %2F — kodierter Schraegstrich.
        'prozent_slash': f'/files%2F{name}',
        # absolute Adresse (fremder Host, gleicher Dateiname).
        'absolute_url': f'https://fremd.example.org/files/{name}',
    }


@pytest.mark.parametrize('variante', [
    'fremde_url', 'private_zweig', 'punkt_punkt',
    'doppeltes_praefix', 'prozent_slash', 'absolute_url',
])
def test_echte_fremde_datei_bleibt_unter_jeder_variante_gesperrt(
        client, zwei, set_user, dateien, praefix, variante):
    """403 fuer jede Adressform auf eine EXISTIERENDE fremde Datei.

    Der Unterschied zu `test_pfad_ausbruch…`: die Datei gibt es wirklich
    (Brunos Upload liegt in `files_dir`, die `File`-Zeile in der Datenbank).
    Ein 200 hier waere ein Datenleck; `foto` muss NULL bleiben.
    """
    from diakronos_app.models.diakonos import Mitglied

    url, name = _bruno_datei(client, set_user)
    boese = _varianten(url, name)[variante]
    assert name in boese, 'Variante muss die echte Datei benennen'

    set_user(ANNA)
    res = _speichern(client, boese)
    assert res.status_code == 403, f'{variante}: {res.text}'

    zwei.expire_all()
    assert zwei.get(Mitglied, 'M-0001').foto is None


# ── MT-2b: strengere Pfadpruefung (`fullmatch`, nur aktiver Praefix) ────────


@pytest.mark.parametrize('boese', [
    '/diakronos/files/foto.jpg\n',      # `$` haette das Zeilenende geschluckt
    '/fremd/diakronos/files/foto.jpg',  # beliebiges Praefix-Paar
    '/x/y/files/foto.jpg',              # beliebiges Praefix-Paar
    '/x/private/files/foto.jpg',
    '/files/foto.jpg\r\n',
    ' /diakronos/files/foto.jpg',       # fuehrendes Leerzeichen
])
def test_dateiname_muster_ist_streng(boese, praefix):
    """Nur `<aktiver Praefix>?/files/<name>` — sonst kein Dateiname (MT-2b)."""
    from diakronos_app.api.profile import _dateiname_aus_file_url

    assert _dateiname_aus_file_url(boese) is None, boese


@pytest.mark.parametrize('gut', [
    '/files/foto.jpg',
    '/private/files/foto.jpg',
])
@pytest.mark.parametrize('praefix', ['/diakronos'], indirect=True)
def test_dateiname_muster_akzeptiert_die_praefixfreie_form(gut, praefix):
    """Die DB-Form (`/files/<name>`) gilt auch, wenn ein Praefix gesetzt ist."""
    from diakronos_app.api.profile import _dateiname_aus_file_url

    assert _dateiname_aus_file_url(gut) == 'foto.jpg'


@pytest.mark.parametrize('gut', [
    '/diakronos/files/foto.jpg',
    '/diakronos/private/files/foto.jpg',
])
@pytest.mark.parametrize('praefix', ['/diakronos'], indirect=True)
def test_dateiname_muster_akzeptiert_die_praefigierte_form(gut, praefix):
    """Die Upload-Antwort (`upload_file`) liefert die praefigierte Form."""
    from diakronos_app.api.profile import _dateiname_aus_file_url

    assert _dateiname_aus_file_url(gut) == 'foto.jpg'


@pytest.mark.parametrize('gut', [
    '/files/foto.jpg',
    '/private/files/foto.jpg',
])
@pytest.mark.parametrize('praefix', [''], indirect=True)
def test_ohne_praefix_gilt_die_praefixfreie_form(gut, praefix):
    from diakronos_app.api.profile import _dateiname_aus_file_url

    assert _dateiname_aus_file_url(gut) == 'foto.jpg'


def test_fremdes_praefix_ist_unter_aktivem_praefix_kein_treffer(praefix):
    """`/fremd/files/…` ist unter `/diakronos` keine Adresse dieser App."""
    from diakronos_app.api.profile import _dateiname_aus_file_url

    assert _dateiname_aus_file_url('/fremd/files/foto.jpg') is None
    assert _dateiname_aus_file_url('/diakronos/files/foto.jpg') == 'foto.jpg'


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


# ── MT-2b: die anderen Leser von `foto` praefigieren ebenfalls ──────────────
# Befund aus dem MT-2-Review: nur das Profil praefigierte seine Bildadresse.
# GruppeDetail (`gruppen.get_gruppe_detail`), Organigramm
# (`orgchart_api.get_orgchart_data`) und Adressbuch (`mitglieder.get_adressbuch`)
# gaben den DB-Wert roh aus — unter `/diakronos` war jedes dieser Bilder ein
# 404. Je Leser ein Test: Praefix gesetzt -> praefigiert; Altbestand, der
# schon praefigiert in der DB steht -> kein Doppelpraefix.

LESER = {
    'gruppe': 'diakronos.diakonos.api.gruppen',
    'orgchart': 'diakronos.diakonos.api.orgchart_api',
    'mitglieder': 'diakronos.diakonos.api.mitglieder',
}


@pytest.fixture()
def leserwelt(patched_db, set_user):
    """Anna in einer Gruppe, als Verantwortliche und im Adressbuch.

    Eine Welt fuer alle drei Leser: `get_gruppe_detail` liefert die
    Mitglieder UND die Verantwortlichen, das Organigramm die Mitgliederknoten,
    das Adressbuch die Personenzeilen — alle vier Wege lesen `Mitglied.foto`.
    """
    from datetime import date

    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import (
        Gruppe,
        GruppeVerantwortlicher,
        Gruppenmitgliedschaft,
        Mitglied,
    )

    sess = patched_db()
    sess.add_all([
        User(name=ANNA, email=ANNA, full_name="Anna Beispiel", enabled=True),
        User(name=BRUNO, email=BRUNO, full_name="Bruno Beispiel", enabled=True),
        HasRole(name="HR-mt2b", parent=ANNA, parenttype="User",
                parentfield="roles", role="System Manager", docstatus=0, idx=1),
        Gruppe(name="G-MT2B", gruppenname="Kleingruppe", status="Aktiv",
               sichtbarkeit="Öffentlich", ancestor_path="/G-MT2B/",
               docstatus=0, idx=0),
    ])
    sess.flush()
    sess.add_all([
        Mitglied(name="M-0001", vorname="Anna", nachname="Beispiel", email=ANNA,
                 status="Mitglied", user=ANNA, docstatus=0, idx=0,
                 ancestor_path="/G-MT2B/"),
        Mitglied(name="M-0002", vorname="Bruno", nachname="Beispiel", email=BRUNO,
                 status="Mitglied", user=BRUNO, docstatus=0, idx=0,
                 ancestor_path="/G-MT2B/"),
        Gruppenmitgliedschaft(name="GM-mt2b-1", parent="G-MT2B",
                              parenttype="Gruppe", parentfield="mitglieder",
                              mitglied="M-0001", rolle="Mitglied", status="Aktiv",
                              beitrittsdatum=date(2024, 1, 1), docstatus=0, idx=1),
        Gruppenmitgliedschaft(name="GM-mt2b-2", parent="G-MT2B",
                              parenttype="Gruppe", parentfield="mitglieder",
                              mitglied="M-0002", rolle="Mitglied", status="Aktiv",
                              beitrittsdatum=date(2024, 1, 2), docstatus=0, idx=2),
        GruppeVerantwortlicher(name="GRV-mt2b", parent="G-MT2B",
                               parenttype="Gruppe", parentfield="verantwortliche",
                               user=ANNA, docstatus=0, idx=1),
    ])
    sess.commit()
    yield sess
    sess.close()


def _lese(client, modul: str, methode: str, payload: dict) -> list[str]:
    """Alle `foto`-Werte einer Antwort (verschachtelt, Mehrfachtreffer)."""
    antwort = client.post(f'/api/method/{modul}.{methode}', json=payload)
    assert antwort.status_code == 200, antwort.text
    roh = antwort.json()['message']

    treffer: list[str] = []

    def _sammeln(knoten):
        if isinstance(knoten, dict):
            for schluessel, wert in knoten.items():
                if schluessel == 'foto':
                    treffer.append(wert or '')
                else:
                    _sammeln(wert)
        elif isinstance(knoten, (list, tuple)):
            for eintrag in knoten:
                _sammeln(eintrag)

    _sammeln(roh)
    return treffer


def _fotos(client, set_user, erwartet: str) -> dict[str, list[str]]:
    """Die `foto`-Werte aller Leser, gefiltert auf die EINE Person.

    `erwartet` ist die Adresse, die Anna haben soll (`''` = kein Bild). Die
    Welt enthaelt weitere Personen ohne Bild — geprueft wird, dass jede
    Personenzeile der Leser entweder genau diese Adresse oder ein leeres
    Feld traegt (kein Leser liefert ein ungepraefigiertes Fremdbild).
    """
    set_user(ANNA)
    return {
        'gruppe': _lese(client, LESER['gruppe'], 'get_gruppe_detail',
                        {'gruppe_id': 'G-MT2B'}),
        'orgchart': _lese(client, LESER['orgchart'], 'get_orgchart_data', {}),
        'adressbuch': _lese(client, LESER['mitglieder'], 'get_adressbuch', {}),
        'liste': _lese(client, LESER['mitglieder'], 'get_mitglieder_liste',
                       {'limit': 50}),
    }


def _pruefe(fotos: dict[str, list[str]], erwartet: str) -> None:
    """Jede Zeile traegt die erwartete Adresse oder ist leer; kein Rohpfad."""
    for name, werte in fotos.items():
        assert werte, f'{name}: kein `foto` in der Antwort gefunden'
        assert erwartet in werte, f'{name}: {erwartet!r} fehlt in {werte!r}'
        for wert in werte:
            assert wert in ('', erwartet), f'{name}: unerwartet {wert!r}'


def _foto_setzen(sess, url: str | None) -> None:
    from diakronos_app.models.diakonos import Mitglied

    sess.expire_all()
    anna = sess.get(Mitglied, 'M-0001')
    anna.foto = url
    sess.commit()


@pytest.mark.parametrize('praefix', ['', '/diakronos'], indirect=True)
def test_alle_leser_praefigieren_das_profilbild(
        client, leserwelt, set_user, dateien, praefix):
    """MT-2b: Gruppe, Organigramm, Adressbuch und Liste liefern `/files/…`
    unter dem Praefix als `<praefix>/files/…` (und ohne Praefix unveraendert)."""
    _foto_setzen(leserwelt, '/files/anna.jpg')

    _pruefe(_fotos(client, set_user, praefix + '/files/anna.jpg'),
            praefix + '/files/anna.jpg')


@pytest.mark.parametrize('praefix', ['', '/diakronos'], indirect=True)
def test_alle_leser_praefigieren_nicht_doppelt(
        client, leserwelt, set_user, dateien, praefix):
    """Altbestand, der schon praefigiert in der Spalte steht: kein Doppelpraefix.

    `base_path.datei_url` ist idempotent — genau das muss auch fuer die drei
    Leser gelten, damit ein Datensatz aus einer frueheren Fassung (oder ein
    Praefix-Wechsel) nicht `/diakronos/diakronos/files/…` ergibt.
    """
    _foto_setzen(leserwelt, praefix + '/files/anna.jpg')

    _pruefe(_fotos(client, set_user, praefix + '/files/anna.jpg'),
            praefix + '/files/anna.jpg')


def test_leser_praefigieren_absolute_und_fremde_adressen_nicht(
        client, leserwelt, set_user, dateien, praefix):
    """Nur `/files/…` und `/private/files/…` bekommen den Praefix.

    Eine absolute Adresse (Altbestand mit CDN-URL) bleibt unangetastet —
    `datei_url` haengt den Praefix nicht vor fremde Schemata.
    """
    fremd = 'https://cdn.example.org/bilder/anna.jpg'
    _foto_setzen(leserwelt, fremd)

    _pruefe(_fotos(client, set_user, fremd), fremd)


def test_leeres_profilbild_bleibt_leer(client, leserwelt, set_user, dateien, praefix):
    """Ohne Bild ist `foto` leer — kein `/diakronos` als Wert."""
    _foto_setzen(leserwelt, None)

    for name, werte in _fotos(client, set_user, '').items():
        assert werte, f'{name}: kein `foto` in der Antwort gefunden'
        for wert in werte:
            assert wert == '', f'{name}: {wert!r}'


# ── NACHBESSERUNG (Review MT-2b, Befund 1 HOCH) ─────────────────────────────
# `update_mitglied` und `update_mitglied_with_confirmation` fuehrten `foto` in
# `allowed_fields` und schrieben den Client-Wert UNGEPRUEFT. Jedes Mitglied darf
# sein EIGENES Mitglied bearbeiten — damit liessen sich fremde Dateien
# (`/private/files/<fremde Datei>`) und Pfad-Ausbrueche (`/files/../../etc/passwd`)
# in die Spalte legen; die Leser praefigierten den Wert und lieferten ihn an
# ALLE Betrachter aus. Profilbilder laufen jetzt ausschliesslich ueber
# `update_profile_picture` (Besitzpruefung an der `File`-Zeile).

SCHREIBWEGE = ['update_mitglied', 'update_mitglied_with_confirmation']


@pytest.mark.parametrize('endpoint', SCHREIBWEGE)
@pytest.mark.parametrize('boese', [
    '/private/files/bruno.jpg',      # fremde Datei, existierender Zweig
    '/files/../../etc/passwd',       # Ausbruch aus dem Ablageverzeichnis
    '/diakronos/files/bruno.jpg',    # fremde Datei, praefigiert
    'https://fremd.example.org/x.jpg',
])
def test_foto_ist_ueber_die_mitglied_update_wege_nicht_schreibbar(
        client, zwei, set_user, dateien, praefix, endpoint, boese):
    """HOCH (Review MT-2b): `foto` steht in KEINER allowed_fields-Liste mehr.

    MT-2c (Review, NIEDRIG 4): der Test liess vorher 403/417 als Erfolg gelten
    — er bestuende auch, wenn der Endpunkt GAR NICHTS mehr schriebe. Jetzt ist
    die Erwartung eindeutig:

      * 200 (das Feld wird still verworfen; die SPA schickt es nicht mehr),
      * ein ZWEITES Feld in derselben Anfrage AENDERT sich (der Aufruf wirkt),
      * `foto` bleibt unveraendert (Annas Bild ist vorher gesetzt — so ist
        "nichts geschrieben" von "auf NULL gesetzt" unterscheidbar).
    """
    from diakronos_app.models.diakonos import Mitglied

    set_user(ANNA)
    eigenes = '/files/anna-eigen.jpg'
    _foto_setzen(zwei, eigenes)

    res = client.post(f'/api/method/mitglieder.{endpoint}', json={
        'mitglied_id': 'M-0001',
        'data': {'vorname': 'Anna', 'wohnort': 'Esslingen', 'foto': boese},
        'audit_confirmation': {},
    })
    # MT-2c: nur 200 ist Erfolg — 403/417 hiesse, der Weg schreibt nicht mehr
    # (dann prueft der Test nichts). Siehe Review-Befund 4.
    assert res.status_code == 200, f'{endpoint}/{boese}: {res.text}'

    zwei.expire_all()
    anna = zwei.get(Mitglied, 'M-0001')
    assert anna.foto == eigenes, f'{endpoint}: {boese}'
    # Das zweite Feld belegt, dass der Aufruf tatsaechlich geschrieben hat.
    assert anna.wohnort == 'Esslingen', f'{endpoint}: Aufruf ohne Wirkung'


@pytest.mark.parametrize('endpoint', SCHREIBWEGE)
def test_foto_wird_auch_bei_leerem_altwert_nicht_gesetzt(
        client, zwei, set_user, dateien, praefix, endpoint):
    """Ohne Altbild bleibt `foto` NULL — auch dann kein Schreibweg."""
    from diakronos_app.models.diakonos import Mitglied

    set_user(ANNA)
    _foto_setzen(zwei, None)

    res = client.post(f'/api/method/mitglieder.{endpoint}', json={
        'mitglied_id': 'M-0001',
        'data': {'foto': '/private/files/bruno.jpg', 'wohnort': 'Esslingen'},
        'audit_confirmation': {},
    })
    # MT-2c (Befund 4): 200 erwartet, nicht "200 oder Fehler".
    assert res.status_code == 200, res.text

    zwei.expire_all()
    anna = zwei.get(Mitglied, 'M-0001')
    assert anna.foto is None
    assert anna.wohnort == 'Esslingen', 'Aufruf ohne Wirkung'


def test_der_erlaubte_weg_bleibt_offen(client, zwei, set_user, dateien, praefix):
    """Gegenprobe: `update_profile_picture` setzt das EIGENE Bild weiterhin."""
    set_user(ANNA)
    url = _upload(client).json()['message']['file_url']

    assert _speichern(client, url).status_code == 200, 'eigener Weg darf nicht brechen'
    assert _foto(client) == url


# ── NACHBESSERUNG (Review MT-2b, Befund 2 MITTEL) ───────────────────────────
# Verteidigung in der Tiefe: `foto_mit_praefix` reichte JEDEN relativen Wert
# durch (`base_path.datei_url` laesst Unbekanntes stehen). Ein Altbestand, der
# vor dem Schreibschutz in die Spalte gelangt ist, ging damit weiter an alle
# Betrachter. Jetzt gilt: relativer Wert muss `_datei_url_muster()` erfuellen,
# sonst `""`.


@pytest.mark.parametrize('altlast', [
    '/etc/passwd',
    '/files/../../etc/passwd',
    '/x/y/files/foto.jpg',
    'files/foto.jpg',              # ohne fuehrenden Schraegstrich
    '/diakronos/diakronos/files/foto.jpg',   # Doppelpraefix
    '/files/foto.jpg?x=1',
    '/files/<script>.jpg',
])
def test_fremder_altbestand_wird_nicht_ausgeliefert(altlast, praefix):
    """MITTEL (Review MT-2b): unpassende relative Werte -> leerer Wert."""
    from diakronos_app.api.profile import foto_mit_praefix

    assert foto_mit_praefix(altlast) == '', altlast


@pytest.mark.parametrize('gut,erwartet', [
    ('/files/foto.jpg', '/diakronos/files/foto.jpg'),
    ('/private/files/foto.jpg', '/diakronos/private/files/foto.jpg'),
    ('/diakronos/files/foto.jpg', '/diakronos/files/foto.jpg'),   # idempotent
    ('https://cdn.example.org/foto.jpg', 'https://cdn.example.org/foto.jpg'),
    ('//cdn.example.org/foto.jpg', '//cdn.example.org/foto.jpg'),
    ('', ''),
    (None, ''),
])
def test_praefigierer_laesst_nur_gueltige_formen_durch(gut, erwartet, praefix):
    """Gegenprobe zu oben: die zwei erlaubten Formen und absolute Adressen."""
    from diakronos_app.api.profile import foto_mit_praefix

    assert foto_mit_praefix(gut) == erwartet


def test_leser_liefern_fremden_altbestand_nicht_aus(
        client, leserwelt, set_user, dateien, praefix):
    """Ein Altbestand wie `/files/../../etc/passwd` in der Spalte kommt leer an.

    Dieselbe Stelle wie `foto_mit_praefix` versorgt alle Leser — der Test
    belegt das am Endpunkt, nicht nur an der Funktion.
    """
    _foto_setzen(leserwelt, '/files/../../etc/passwd')

    for name, werte in _fotos(client, set_user, '').items():
        assert werte, f'{name}: kein `foto` in der Antwort gefunden'
        for wert in werte:
            assert wert == '', f'{name}: {wert!r}'


# ── NACHBESSERUNG (Review MT-2b, Befund 3 NIEDRIG) ──────────────────────────
# `user_image` (Boot-Objekt, `get_current_user_context`, `get_session_info`)
# ist ebenfalls eine Datei-Adresse und bekam keinen Praefix.


@pytest.mark.parametrize('praefix', ['/diakronos'], indirect=True)
def test_user_image_bekommt_den_praefix(praefix):
    """Boot, User-Context und Session-Info nutzen denselben Praefigierer."""
    from diakronos_app.api.kronos.permissions import _bild_mit_praefix as kronos
    from diakronos_app.api.session import _bild_mit_praefix as sitzung
    from diakronos_app.spa import _bild_mit_praefix as boot

    for stelle in (boot, sitzung, kronos):
        assert stelle('/files/u.jpg') == '/diakronos/files/u.jpg'
        assert stelle('/diakronos/files/u.jpg') == '/diakronos/files/u.jpg'
        assert stelle('/etc/passwd') == ''
        assert stelle(None) == ''


def test_boot_und_session_info_liefern_das_bild_mit_praefix(
        client, zwei, set_user, praefix):
    """Endpunkt-Beleg: `user_image` kommt praefigiert bzw. leer an."""
    from diakronos_app.models.core import User

    zwei.get(User, ANNA).user_image = '/files/anna-u.jpg'
    zwei.commit()
    set_user(ANNA)

    for endpoint in ('session.get_current_user_context', 'kronos.permissions.get_session_info'):
        antwort = client.post(f'/api/method/{endpoint}', json={})
        assert antwort.status_code == 200, f'{endpoint}: {antwort.text}'
        assert antwort.json()['message']['user_image'] == '/diakronos/files/anna-u.jpg'

    # Boot-Objekt (HTML-Einbettung): derselbe Wert, dieselbe Stelle.
    from diakronos_app.spa import boot_fuer_request

    boot = boot_fuer_request()
    assert boot['user_image'] == '/diakronos/files/anna-u.jpg'


# ── MT-2c (zweites Review) ──────────────────────────────────────────────────
# Befund 1 MITTEL: absolute Adressen wurden per TEILSTRING erkannt
# (`if "://" in wert`). `'/files/../../etc/passwd?a=://'` und
# `'/x/y/z?u=http://a'` gingen damit ungeprueft durch — der Altbestand-Schutz
# aus MT-2b war umgehbar. Geprueft wird jetzt nur der ANFANG.


@pytest.mark.parametrize('boese', [
    '/files/../../etc/passwd?a=://',      # Teilstring `://` im Query
    '/x/y/z?u=http://a',                  # Teilstring `http://` im Query
    '/files/../../etc/passwd?a=//',       # Teilstring `//` im Query
    '/files/../../etc/passwd#http://a',   # Fragment statt Query
    ' /files/../../etc/passwd?a=://',     # fuehrender Leerraum, dann kein //
])
def test_absolute_adresse_wird_nur_am_anfang_erkannt(boese):
    """MITTEL (MT-2c): ein `://` irgendwo im Wert ist KEINE absolute Adresse."""
    from diakronos_app.api.profile import foto_mit_praefix

    assert foto_mit_praefix(boese) == '', boese


@pytest.mark.parametrize('gut,erwartet', [
    ('http://cdn.example.org/foto.jpg', 'http://cdn.example.org/foto.jpg'),
    ('https://cdn.example.org/foto.jpg', 'https://cdn.example.org/foto.jpg'),
    ('HTTPS://cdn.example.org/foto.jpg', 'HTTPS://cdn.example.org/foto.jpg'),
    ('//cdn.example.org/foto.jpg', '//cdn.example.org/foto.jpg'),
])
def test_echte_absolute_adresse_bleibt_unangetastet(gut, erwartet, praefix):
    """Gegenprobe: echte Adressen AM ANFANG gehen weiter unveraendert durch."""
    from diakronos_app.api.profile import foto_mit_praefix

    assert foto_mit_praefix(gut) == erwartet


@pytest.mark.parametrize('praefix', ['', '/diakronos'], indirect=True)
def test_eigenes_profil_prueft_das_format(
        client, zwei, set_user, dateien, praefix):
    """NIEDRIG (MT-2c, Befund 2): `get_my_profile` nutzt `foto_mit_praefix`.

    Vorher lief die Ausgabe des EIGENEN Profils ueber den Alias
    `_datei_mit_praefix` (ohne Formatpruefung) — ein Altbestand in der Spalte
    ging dort weiter hinaus, waehrend alle anderen Leser ihn schon leerten.
    """
    for altlast in ('/etc/passwd', '/files/../../etc/passwd',
                    '/files/../../etc/passwd?a=://'):
        _foto_setzen(zwei, altlast)
        set_user(ANNA)
        assert _foto(client) == '', altlast

    # Gegenprobe: die normale DB-Form kommt weiter (mit Praefix) an.
    _foto_setzen(zwei, '/files/anna.jpg')
    set_user(ANNA)
    assert _foto(client) == praefix + '/files/anna.jpg'


#: Die generischen Wege, die `foto` frueher UNGEPRUEFT setzten. Alle sechs
#: laufen durch `frappe_compat.api_helpers._pruefe_mitglied_schreibzugriff`
#: (die zentrale Schranke) — genau dort haengt `pruefe_foto_schreibweg`.
GENERISCHE_WEGE = [
    'resource_put_fremd',   # PUT auf ein FREMDES Mitglied
    'resource_put_eigen',   # PUT auf das EIGENE Mitglied
    'resource_post',        # POST (anlegen)
    'client_insert',        # frappe.client.insert
    'doc_save',             # doc.foto = ...; doc.save()
    'update_doc',           # api_helpers._update_doc
]


def _sm(client, zwei, set_user, email: str = ANNA) -> None:
    """Gibt dem Konto die Rolle System Manager (Schreibrecht auf /api/resource).

    MT-2c (Review, Befund 3): OHNE diese Rolle scheitern die generischen Wege
    schon an der allgemeinen Rechtepruefung — ein Test dagegen waere gruen,
    egal was die `foto`-Schranke tut.
    """
    from diakronos_app.models.core import HasRole

    zwei.add(HasRole(name=f'HR-mt2c-{email}', parent=email, parenttype='User',
                     parentfield='roles', role='System Manager',
                     docstatus=0, idx=1))
    zwei.commit()
    set_user(email)


def _bruno_laedt_hoch(client, set_user) -> tuple[str, str]:
    """Eine ECHTE `File`-Zeile, die BRUNO gehoert — (file_url, gespeicherte Form).

    Nur so ist der Besitz pruefbar: `/private/files/bruno.jpg` als blosser
    String waere auch ohne Schranke abgelehnt worden (keine Zeile).
    """
    from diakronos_app.models.core import FileModel

    set_user(BRUNO)
    antwort = _upload(client, 'bruno.jpg')
    assert antwort.status_code == 200, antwort.text
    url = antwort.json()['message']['file_url']
    name = url.rsplit('/', 1)[-1]
    # Die DB-Zeile liegt praefixfrei (`/files/<name>`), genau wie bei Anna.
    return url, f'/files/{name}'


def _generisch(client, zwei, weg: str, foto: str, dateiname: str):
    """Fuehrt einen GENERISCHEN Schreibweg aus.

    Gibt ``(status, geaendert)`` zurueck: ``status`` ist der HTTP-Code (oder
    ``None`` ohne HTTP) und ``geaendert`` das Feld, das der Aufruf zusaetzlich
    setzt — so ist „abgelehnt“ von „gar nichts geschrieben“ unterscheidbar.
    Die Wege OHNE HTTP muessen werfen (``FrappeCompatError``).
    """
    from diakronos_app.api import frappe_core
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    from diakronos_app.frappe_compat.exceptions import FrappeCompatError
    from diakronos_app.frappe_compat.query import get_doc

    if weg == 'resource_put_fremd':
        antwort = client.put('/api/resource/Mitglied/M-0002',
                             json={'foto': foto, 'wohnort': 'Esslingen'})
        return antwort.status_code, antwort
    if weg == 'resource_put_eigen':
        antwort = client.put('/api/resource/Mitglied/M-0001',
                             json={'foto': foto, 'wohnort': 'Esslingen'})
        return antwort.status_code, antwort
    if weg == 'resource_post':
        antwort = client.post('/api/resource/Mitglied',
                              json={'vorname': 'Neu', 'nachname': 'Person',
                                    'foto': foto})
        return antwort.status_code, antwort
    if weg == 'client_insert':
        with pytest.raises(FrappeCompatError):
            frappe_core.insert({'doctype': 'Mitglied', 'vorname': 'Neu',
                                'nachname': 'Person', 'foto': foto})
        return None, None
    if weg == 'doc_save':
        doc = get_doc('Mitglied', 'M-0001')
        doc.foto = foto
        doc.wohnort = 'Esslingen'
        with pytest.raises(FrappeCompatError):
            doc.save()
        return None, None
    assert weg == 'update_doc', weg
    with pytest.raises(FrappeCompatError):
        _update_doc('Mitglied', 'M-0001',
                    {'foto': foto, 'wohnort': 'Esslingen'})
    return None, None


@pytest.mark.parametrize('weg', GENERISCHE_WEGE)
def test_generische_wege_setzen_fremdes_foto_nicht(
        client, zwei, set_user, dateien, praefix, weg):
    """MITTEL (MT-2c, Befund 3): eine ECHTE fremde `File`-Zeile bleibt gesperrt.

    Aufbau (Review-Vorgabe): Bruno laedt wirklich hoch, Anna ist System
    Managerin. Ohne die `foto`-Schranke nimmt JEDER dieser sechs Wege die
    Adresse an — auf `85bafa2a` nachweislich mit 200 und gespeichertem Wert.
    Mit Schranke: 403 (bzw. ``FrappeCompatError`` ohne HTTP), `foto` bleibt
    auf beiden Mitgliedern leer und das zweite Feld kommt NICHT an (der
    Aufruf wird als Ganzes abgelehnt, nicht halb geschrieben).
    """
    from diakronos_app.models.diakonos import Mitglied

    url, _ = _bruno_laedt_hoch(client, set_user)
    _sm(client, zwei, set_user, ANNA)

    status, antwort = _generisch(client, zwei, weg, url, 'bruno.jpg')

    if status is not None:
        assert status == 403, f'{weg}: {antwort.text}'
    zwei.expire_all()
    assert zwei.get(Mitglied, 'M-0001').foto is None, f'{weg}: gespeichert'
    assert zwei.get(Mitglied, 'M-0002').foto is None, f'{weg}: gespeichert'
    # Der Aufruf wurde als Ganzes abgelehnt — kein halb geschriebener Datensatz.
    assert zwei.get(Mitglied, 'M-0001').wohnort == 'Stuttgart', f'{weg}: halb geschrieben'
    assert zwei.query(Mitglied).count() == 2, f'{weg}: Zeile angelegt'


@pytest.mark.parametrize('weg', GENERISCHE_WEGE)
@pytest.mark.parametrize('boese', [
    '/private/files/bruno.jpg',       # fremde Adresse (keine eigene Zeile)
    '/files/../../etc/passwd',        # Ausbruch
    '/files/../../etc/passwd?a=://',  # MT-2c: Teilstring-Trick
    'https://fremd.example.org/x.jpg',
])
def test_generische_wege_setzen_manipulierte_adressen_nicht(
        client, zwei, set_user, dateien, praefix, weg, boese):
    """Dieselben Wege mit Werten, die KEINE eigene Datei benennen — 403, nichts geschrieben."""
    from diakronos_app.models.diakonos import Mitglied

    _sm(client, zwei, set_user, ANNA)
    status, antwort = _generisch(client, zwei, weg, boese, 'profilbild.jpg')
    if status is not None:
        assert status == 403, f'{weg}/{boese}: {antwort.text}'

    zwei.expire_all()
    assert zwei.get(Mitglied, 'M-0001').foto is None, f'{weg}: {boese}'
    assert zwei.get(Mitglied, 'M-0002').foto is None, f'{weg}: {boese}'
    assert zwei.query(Mitglied).count() == 2, f'{weg}: {boese}'


@pytest.mark.parametrize('weg', ['resource_put_eigen', 'doc_save', 'update_doc'])
def test_generischer_weg_speichert_das_eigene_bild_in_db_form(
        client, zwei, set_user, dateien, praefix, weg):
    """Gegenprobe: die EIGENE Datei bleibt erlaubt — und landet in der DB-Form.

    Die Schranke prueft Besitz, sie sperrt `foto` nicht pauschal (sonst waere
    jedes Verwaltungsformular mit Bild unbedienbar). Gespeichert wird
    `/files/<name>` — die praefigierte Upload-Adresse (`/diakronos/files/…`)
    gehoert NICHT in die Spalte (Befund 4: der `Document`-Weg schrieb bisher
    den rohen Client-Wert).
    """
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    from diakronos_app.frappe_compat.query import get_doc
    from diakronos_app.models.diakonos import Mitglied

    _sm(client, zwei, set_user, ANNA)
    url = _upload(client).json()['message']['file_url']
    erwartet = _ohne_praefix(url, praefix)

    if weg == 'resource_put_eigen':
        antwort = client.put('/api/resource/Mitglied/M-0001', json={'foto': url})
        assert antwort.status_code == 200, antwort.text
    elif weg == 'doc_save':
        doc = get_doc('Mitglied', 'M-0001')
        doc.foto = url
        doc.save()
    else:
        _update_doc('Mitglied', 'M-0001', {'foto': url})

    zwei.expire_all()
    gespeichert = zwei.get(Mitglied, 'M-0001').foto
    assert gespeichert == erwartet, f'{weg}: {gespeichert!r} != {erwartet!r}'
    assert gespeichert.startswith('/files/'), f'{weg}: praefigiert gespeichert'


def test_generischer_weg_laesst_unveraendertes_foto_stehen(
        client, zwei, set_user, dateien, praefix):
    """Ein PUT mit der GANZEN Zeile (foto unveraendert) bleibt 200 und aendert nichts.

    Das Frappe-Formular schickt alle Felder mit; ein unveraendertes `foto`
    darf den Aufruf nicht mit 403 abbrechen.
    """
    from diakronos_app.models.diakonos import Mitglied

    _foto_setzen(zwei, '/files/anna-eigen.jpg')
    _sm(client, zwei, set_user)

    antwort = client.put('/api/resource/Mitglied/M-0001',
                         json={'foto': '/files/anna-eigen.jpg',
                               'wohnort': 'Esslingen'})
    assert antwort.status_code == 200, antwort.text

    zwei.expire_all()
    anna = zwei.get(Mitglied, 'M-0001')
    assert anna.foto == '/files/anna-eigen.jpg'
    assert anna.wohnort == 'Esslingen'


@pytest.mark.parametrize('weg', GENERISCHE_WEGE)
def test_generische_wege_ohne_foto_bleiben_offen(
        client, zwei, set_user, dateien, praefix, weg):
    """Die Schranke greift NUR bei `foto` — andere Felder bleiben schreibbar.

    MT-2d (drittes Review, NIEDRIG 5): die sechs Wege sind hier wirklich
    GETRENNT — frueher liefen vier davon in denselben
    `frappe_core.insert`-Zweig (und `resource_put_fremd` schrieb auf die
    EIGENE Zeile M-0001). Jetzt: PUT auf die FREMD-Zeile, PUT auf die eigene,
    POST, `frappe.client.insert`, `doc.save()` und `_update_doc` — jeder Weg
    mit Erfolgsbeweis an der Stelle, die er tatsaechlich schreibt.
    """
    from diakronos_app.models.diakonos import Mitglied

    _sm(client, zwei, set_user)

    if weg == 'resource_put_fremd':
        antwort = client.put('/api/resource/Mitglied/M-0002',
                             json={'wohnort': 'Stuttgart'})
        assert antwort.status_code == 200, antwort.text
        zwei.expire_all()
        assert zwei.get(Mitglied, 'M-0002').wohnort == 'Stuttgart'
        assert zwei.get(Mitglied, 'M-0001').wohnort == 'Stuttgart'
        # Die FREMD-Zeile gehoert Bruno — hier beweist der Test zusaetzlich,
        # dass die Schreibrechte (System Manager) greifen, nicht der Besitz.
    elif weg == 'resource_put_eigen':
        antwort = client.put('/api/resource/Mitglied/M-0001',
                             json={'wohnort': 'Esslingen'})
        assert antwort.status_code == 200, antwort.text
        zwei.expire_all()
        assert zwei.get(Mitglied, 'M-0001').wohnort == 'Esslingen'
        assert zwei.get(Mitglied, 'M-0002').wohnort == 'Esslingen'
    elif weg == 'resource_post':
        antwort = client.post('/api/resource/Mitglied',
                              json={'vorname': 'Neu', 'nachname': 'Person',
                                    'wohnort': 'Esslingen'})
        assert antwort.status_code in (200, 201), antwort.text
        zwei.expire_all()
        assert zwei.query(Mitglied).count() == 3
        assert zwei.query(Mitglied).filter(
            Mitglied.vorname == 'Neu').one().wohnort == 'Esslingen'
    elif weg == 'client_insert':
        from diakronos_app.api import frappe_core

        antwort = frappe_core.insert({'doctype': 'Mitglied', 'vorname': 'Neu',
                                      'nachname': 'Person',
                                      'wohnort': 'Esslingen'})
        assert antwort
        neu = antwort.get('name') if isinstance(antwort, dict) else antwort
        zwei.expire_all()
        assert zwei.query(Mitglied).count() == 3
        assert zwei.get(Mitglied, neu).wohnort == 'Esslingen', antwort
    elif weg == 'doc_save':
        from diakronos_app.frappe_compat.query import get_doc

        doc = get_doc('Mitglied', 'M-0001')
        doc.wohnort = 'Esslingen'
        doc.save()
        zwei.expire_all()
        assert zwei.get(Mitglied, 'M-0001').wohnort == 'Esslingen'
    else:
        assert weg == 'update_doc', weg
        from diakronos_app.frappe_compat.api_helpers import _update_doc

        _update_doc('Mitglied', 'M-0001', {'wohnort': 'Esslingen'})
        zwei.expire_all()
        assert zwei.get(Mitglied, 'M-0001').wohnort == 'Esslingen'


# ── MT-2d: `doc.save()` umging die Schranke bei gleichzeitiger E-Mail-Aenderung
# DER BEFUND (drittes Review)
# ---------------------------
# `frappe_compat.doc._pruefe_mitglied` kuerzte den Payload nach der
# E-Mail-Normalisierung auf `{"email"}`. Die Schranke
# (`_pruefe_mitglied_schreibzugriff`) sah danach NUR noch `email` — ein
# `doc.foto = <fremder Upload>` bzw. `doc.website_einwilligung = True` im
# SELBEN `save()` kam ungeprueft durch und wurde roh gespeichert. Dieselbe
# Luecke betraf in `main` die Einwilligung (BS-3a), obwohl der Kommentar
# darunter das Gegenteil behauptet.
#
# GEPRUEFT WIRD: der ganze Weg mit System Manager (ohne die Rolle scheitert
# der Aufruf schon an der Rechtepruefung, siehe `_sm`), je ein Feld
# zusaetzlich zur E-Mail.


@pytest.mark.parametrize('feld,wert', [
    ('foto', 'fremd'),                    # echte fremde `File`-Zeile (Bruno)
    ('website_einwilligung', True),       # BS-3a
    ('website_einwilligung_foto', True),  # BS-3a: zweites Einwilligungsfeld
])
def test_doc_save_mit_email_umgeht_die_schranke_nicht(
        client, zwei, set_user, dateien, praefix, feld, wert):
    """MITTEL (MT-2d): E-Mail + gesperrtes Feld im selben `doc.save()` -> 403.

    Beide Proben sind auf dem Stand VOR dem Fix gruen-durchgelaufen (kein
    Fehler, fremde Datei bzw. `True` roh gespeichert). Nach dem Fix wirft der
    Aufruf `FrappeCompatError`, und KEINES der beiden Felder ist geschrieben —
    auch die E-Mail nicht (der Aufruf wird als Ganzes abgelehnt).
    """
    from diakronos_app.frappe_compat.exceptions import FrappeCompatError
    from diakronos_app.frappe_compat.query import get_doc
    from diakronos_app.models.diakonos import Mitglied

    foto_url, _ = _bruno_laedt_hoch(client, set_user)
    _sm(client, zwei, set_user, ANNA)
    if wert == 'fremd':
        wert = foto_url

    doc = get_doc('Mitglied', 'M-0001')
    doc.email = 'anna.neu@example.org'
    setattr(doc, feld, wert)
    with pytest.raises(FrappeCompatError):
        doc.save()

    zwei.expire_all()
    anna = zwei.get(Mitglied, 'M-0001')
    assert anna.email == ANNA, f'{feld}: E-Mail trotzdem geschrieben'
    assert getattr(anna, feld) in (None, False, 0), \
        f'{feld}: gesperrtes Feld trotzdem geschrieben ({getattr(anna, feld)!r})'


def test_doc_save_ohne_gesperrtes_feld_bleibt_offen(
        client, zwei, set_user, dateien, praefix):
    """Gegenprobe: eine reine E-Mail-Aenderung per `doc.save()` bleibt erlaubt."""
    from diakronos_app.frappe_compat.query import get_doc
    from diakronos_app.models.diakonos import Mitglied

    _sm(client, zwei, set_user, ANNA)

    doc = get_doc('Mitglied', 'M-0001')
    doc.email = 'anna.neu@example.org'
    doc.save()

    zwei.expire_all()
    assert zwei.get(Mitglied, 'M-0001').email == 'anna.neu@example.org'


# ── MT-2d (drittes Review, NIEDRIG 5): Operator-Entscheidung als Test ───────
# Der LESER bleibt wie in `main`: `oeffentlich_api._bild_datei` prueft keinen
# Besitz. Der Schreibweg ist die Verteidigung (siehe
# `test_generische_wege_setzen_fremdes_foto_nicht`). KONSEQUENZ, bewusst
# entschieden: setzt eine Verwaltung (System Manager) IHR EIGENES Upload als
# Bild einer anderen Person, ist das erlaubt — und die Website liefert es aus
# (200). Frueher stand hier die Gegenannahme („nur Dateien des Mitglieds“).


def test_operator_entscheidung_fremd_gesetztes_admin_bild_wird_ausgeliefert(
        client, zwei, set_user, dateien, praefix):
    """Operator-Entscheidung: Admin-Bild bei einer Person -> `/website/bild/...` 200.

    Aufbau: ANNA (System Managerin) laedt ein Bild hoch und setzt es per
    `PUT /api/resource` auf das Mitglied M-0002 (nicht ihres). Danach ist
    M-0002 oeffentlicher Ansprechpartner mit Einwilligung + Foto-Zustimmung.
    Der Bild-Endpunkt liefert 200 — der Leser prueft keinen Besitz, und das
    ist die Entscheidung des Operators (nicht der Befund).
    """
    from diakronos_app.models.diakonos import (
        Dienstbereich, DienstbereichVerantwortlicher, Mitglied,
    )
    from diakronos_app.models.website_ansprechpartner import WebsiteAnsprechpartner
    from diakronos_app.website import oeffentlich_auswahl as auswahl

    _sm(client, zwei, set_user, ANNA)
    antwort = _upload(client, 'admin.png')
    assert antwort.status_code == 200, antwort.text
    url = antwort.json()['message']['file_url']

    put = client.put('/api/resource/Mitglied/M-0002', json={'foto': url})
    assert put.status_code == 200, put.text

    zwei.expire_all()
    bruno = zwei.get(Mitglied, 'M-0002')
    assert bruno.foto, 'Bild nicht gespeichert'
    bruno.website_einwilligung = True
    bruno.website_einwilligung_foto = True
    zwei.add(WebsiteAnsprechpartner(art='dienstbereich', funktion='musik',
                                    bezeichnung='', postfach=None, sortierung=1))
    zwei.add(DienstbereichVerantwortlicher(name='dbv-mt2d', parent='musik',
                                           parenttype='Dienstbereich',
                                           parentfield='verantwortliche',
                                           user=BRUNO, idx=1))
    zwei.add(Dienstbereich(name='musik', ministry='Musik', sortierung=1))
    zwei.commit()

    kennung = auswahl.oeffentliche_kennung('person', 'M-0002')
    bild = client.get(f'/website/bild/person/{kennung}')
    assert bild.status_code == 200, bild.text


# ── MT-2c (zweites Review, NIEDRIG 5) / MT-2d (drittes Review, NIEDRIG 3):
# `base_path.datei_url` ─────────────────────────────────────────────────────
# `datei_url` erkannte „absolut“ per TEILSTRING (`"://" in wert`) und
# uebersprang damit die Praefigierung; geprueft wird jetzt nur der ANFANG.
# MT-2d: `datei_url` praefigiert ausserdem DIREKT (nicht mehr ueber `pfad()`,
# das den Teilstring-Test noch hat) — `'/files/a.jpg?u=http://x'` bekommt
# damit den Praefix, wie der Docstring es sagt.


@pytest.mark.parametrize('pfad_wert', [
    '/files/a.jpg', '/private/files/a.jpg',
])
def test_datei_url_praefigiert_ueber_pfad(pfad_wert):
    """Die normalen DB-Formen laufen weiter ueber `pfad` (Praefix davor).

    Nur `/files/…` und `/private/files/…` sind Datei-Adressen; jeder andere
    relative Pfad bleibt unangetastet (unveraendertes Bestandsverhalten).
    """
    from diakronos_app import base_path

    alt = base_path.aktiver_praefix()
    base_path.setze_praefix('/diakronos')
    try:
        assert base_path.datei_url(pfad_wert) == '/diakronos' + pfad_wert
    finally:
        base_path.setze_praefix(alt)


@pytest.mark.parametrize('wert', [
    '/files/a.jpg?u=http://x',      # Teilstring `://` im Query
    '/private/files/a.jpg?a=://',
    '/files/../../etc/passwd?a=://',
])
def test_datei_url_prueft_absolut_nur_am_anfang(wert):
    """MITTEL (MT-2c) / NIEDRIG (MT-2d): der Teilstring im Query ist KEIN absoluter Wert.

    Verhalten, nicht Muster: `datei_url` fragte frueher `"://" in wert` —
    damit galten diese Pfade DIESER Installation als „absolut“ und blieben
    unpraefigiert (toter Link). Geprueft wird der ANFANG; der Praefix kommt
    davor (MT-2d: direkt, `pfad()` haette den Wert wieder durchgelassen).
    """
    from diakronos_app import base_path

    alt = base_path.aktiver_praefix()
    base_path.setze_praefix('/diakronos')
    try:
        assert base_path.datei_url(wert) == '/diakronos' + wert, wert
    finally:
        base_path.setze_praefix(alt)


@pytest.mark.parametrize('wert', [
    'http://cdn.example.org/a.jpg',
    'https://cdn.example.org/a.jpg',
    'HTTPS://cdn.example.org/a.jpg',
    '//cdn.example.org/a.jpg',
    'anders/relativ.jpg',
])
def test_datei_url_erkennt_absolut_nur_am_anfang(wert):
    """Gegenprobe: echte absolute Adressen (am ANFANG) bleiben unangetastet.

    Die Kartenentscheidung selbst („Teilstring im Query ist NICHT absolut“)
    haelt `test_datei_url_prueft_absolut_nur_am_anfang` fest.
    """
    from diakronos_app import base_path

    alt = base_path.aktiver_praefix()
    base_path.setze_praefix('/diakronos')
    try:
        assert base_path.datei_url(wert) == wert, wert
    finally:
        base_path.setze_praefix(alt)
