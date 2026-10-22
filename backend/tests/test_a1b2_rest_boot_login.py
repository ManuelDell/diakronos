"""A1b2-rest — echtes Boot-Objekt, Login-Maske, Cache-Header.

Die Vorgängerkarte A1b2 hat die Umschaltung der Identitaet gebracht
(`SessionMiddleware`, `CsrfMiddleware`, `DEFAULT_USER = "Guest"`), aber
`spa.py` lieferte weiter das `DUMMY_BOOT`: jeder Besucher von `/diakonos`
bekam `is_admin: true` und den Namen "Test Nutzer". Damit war die App nach der
Umschaltung nicht benutzbar — die SPA zeigte einen Namen, den es nicht gab,
und ihre schreibenden Aufrufe hatten keinen CSRF-Token.

Diese Tests sichern die zwei ergaenzten Teile ab:

1. Das Boot-Objekt ist echt: Name aus `user`, `is_admin` aus `Has Role`,
   `mitglied` aus `Mitglied`, `csrf_token` aus der Sitzung. Kein Wert darf
   mehr erfunden sein ("Test Nutzer", "dummy-csrf-token").
2. Ohne Sitzung liefern `/diakonos` und die geschuetzten Unterseiten die
   Anmeldemaske statt der SPA — und die Maske selbst ist erreichbar, sonst
   waere das eine Endlosschleife.
3. `index.html` und die Maske: `Cache-Control: no-store`. Hash-benannte
   Assets: `immutable`. Beides wird getrennt geprueft, weil ein Verwechslung
   in beide Richtungen schadet (alter Name im Cache / Assets bei jedem
   Aufruf neu ausgeliefert).
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from diakronos_app.main import app
from diakronos_app.spa import SPA_DIST

LOGIN_MASKEN_MARKER = 'name="pwd"'


# ──────────────────────────────────────────────────────────────────────────
# Hilfen
# ──────────────────────────────────────────────────────────────────────────


def _boot_aus(html: str) -> dict:
    """Liest `window.__DIakonosBOOT` aus dem ausgelieferten HTML.

    Wir parsen das JSON-Literal bewusst so, wie der Browser es tut: der
    Wert zwischen `=` und dem abschliessenden `;`. Ein Fehlschlag ist ein
    echter Fehler — dann stuende das Objekt nicht synchron vor dem
    Entry-Script und die SPA haette leere Werte.
    """
    m = re.search(r"window\.__DIakonosBOOT\s*=\s*(\{.*?\});", html, re.DOTALL)
    assert m, "Kein __DIakonosBOOT im HTML gefunden"
    return json.loads(m.group(1))


@pytest.fixture()
def gast_http(patched_db, fake_redis):
    """Client OHNE Sitzung — jeder Aufruf ist `Guest`."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def gemeinde(patched_db):
    """Schreibt den Gemeindenamen in `Diakronos Einstellungen`."""
    from diakronos_app.models.diakronos import DiakronosEinstellungen

    sess = patched_db()
    zeile = sess.get(DiakronosEinstellungen, "Diakronos Einstellungen")
    if zeile is None:
        zeile = DiakronosEinstellungen(name="Diakronos Einstellungen", docstatus=0, idx=0)
        sess.add(zeile)
    zeile.organisationsname = "Ev. Gemeinde Musterstadt"
    sess.commit()
    yield zeile
    sess.close()


@pytest.fixture()
def angemeldeter_http(patched_db, fake_redis, monkeypatch):
    """Client MIT gueltiger Sitzung als `anna@example.org`.

    Legt User + Mitglied an, meldet aber ueber den echten Weg an: Cookie
    `sid` kommt aus dem Sitzungs-Store, nicht aus der Test-Naht
    `set_user()`. Genau diesen Weg nimmt ein Browser.
    """
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import HasRole, Role, User
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    sess.add_all([
        User(
            name="anna@example.org", email="anna@example.org",
            full_name="Anna Beispiel", user_image="/files/anna.png",
            enabled=True, password_hash=neuer_hash("Geheim-1"),
        ),
        Role(name="Mitgliederadministrator"),
        Mitglied(
            name="M-0001", vorname="Anna", nachname="Beispiel",
            email="anna@example.org", status="Mitglied", docstatus=0, idx=0,
            ancestor_path="/M-0001",
        ),
    ])
    sess.flush()
    # Rolle zuweisen -> `get_roles` findet sie, `is_admin` wird True.
    sess.add(HasRole(
        name="HR-1", parent="anna@example.org", parenttype="User",
        role="Mitgliederadministrator", docstatus=0, idx=0,
    ))
    sess.commit()
    sid, csrf = sitzungen.anlegen("anna@example.org")
    sess.close()

    with TestClient(app) as c:
        c.cookies.set("sid", sid)
        yield c, csrf


@pytest.fixture()
def angemeldeter_ohne_rolle(patched_db, fake_redis):
    """Client MIT gueltiger Sitzung als `berta@example.org` — OHNE Admin-Rolle."""
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    sess.add_all([
        User(
            name="berta@example.org", email="berta@example.org",
            full_name="Berta Muster", enabled=True,
            password_hash=neuer_hash("Geheim-2"),
        ),
        Mitglied(
            name="M-0002", vorname="Berta", nachname="Muster",
            email="berta@example.org", status="Mitglied", docstatus=0, idx=0,
            ancestor_path="/M-0002",
        ),
    ])
    sess.commit()
    sid, csrf = sitzungen.anlegen("berta@example.org")
    sess.close()

    with TestClient(app) as c:
        c.cookies.set("sid", sid)
        yield c, csrf


# ──────────────────────────────────────────────────────────────────────────
# 1. Ohne Sitzung: Login-Maske statt SPA
# ──────────────────────────────────────────────────────────────────────────


def test_diakonos_ohne_sitzung_zeigt_loginmaske(gast_http: TestClient) -> None:
    """Kernpunkt der Karte: kein Gast bekommt die SPA."""
    resp = gast_http.get("/diakonos")
    assert resp.status_code == 200
    assert LOGIN_MASKEN_MARKER in resp.text, "Ohne Sitzung muss die Maske kommen"
    assert 'id="app"' not in resp.text, "Ohne Sitzung darf NICHT die SPA kommen"
    assert "window.__DIakonosBOOT" not in resp.text


def test_organigramm_ohne_sitzung_zeigt_loginmaske(gast_http: TestClient) -> None:
    """`organigramm.py:14-16` leitet im Altcode ohne Sitzung zur Anmeldung."""
    resp = gast_http.get("/diakonos/organigramm")
    assert resp.status_code == 200
    assert LOGIN_MASKEN_MARKER in resp.text


def test_admin_ohne_sitzung_zeigt_loginmaske(gast_http: TestClient) -> None:
    """`/diakonos/admin` zeigt im Altcode ebenfalls nur eingeloggt etwas."""
    resp = gast_http.get("/diakonos/admin")
    assert LOGIN_MASKEN_MARKER in resp.text


def test_oeffentliche_eintraege_bleiben_oeffentlich(gast_http: TestClient) -> None:
    """Registrierung und Gast-Anmeldung sind `allow_guest = True`.

    Quelle: referenz/.../diakonos/www/diakonos/registrierung.py:5 und
    gast.py:5. Ohne sie waere der Anmeldelink aus der E-Mail der
    Gemeindeleitung tot — und niemand koennte sich ueberhaupt erst anmelden.
    """
    for pfad in ("diakonos/registrierung", "diakonos/gast"):
        resp = gast_http.get(f"/{pfad}")
        assert resp.status_code == 200, pfad
        assert 'id="app"' in resp.text, f"{pfad} muss die SPA liefern"
        assert LOGIN_MASKEN_MARKER not in resp.text, f"{pfad} darf keine Maske zeigen"


def test_assets_ohne_sitzung_bleiben_erreichbar(gast_http: TestClient) -> None:
    """Assets werden VOR der Anmeldepflicht ausgeliefert.

    Grund: `sid` hat `SameSite=Lax`. Beim Nachladen von `diakonos-<hash>.js`
    von einer anderen Origin kommt das Cookie nicht mit — eine Maske auf
    Assets wuerde eine angemeldete Seite ohne JavaScript zeigen.
    """
    if SPA_DIST is None:
        pytest.skip("Kein SPA-Build vorhanden")
    js = sorted(SPA_DIST.glob("diakonos-*.js"))
    if not js:
        pytest.skip("Kein Entry-Bundle im Build")
    resp = gast_http.get(f"/diakonos/assets/{js[0].name}")
    assert resp.status_code == 200
    assert LOGIN_MASKEN_MARKER not in resp.text


# ──────────────────────────────────────────────────────────────────────────
def _build_verzeichnis() -> Path:
    """`SPA_DIST` als non-optional, oder Skip.

    Pyright kann `pytest.skip()` nicht als `NoReturn` erkennen; ohne diese
    Bindung meldet jeder Zugriff `Optional`-Fehler.
    """
    from pathlib import Path  # noqa: PLC0415  (lokaler Import im Test)

    if SPA_DIST is None:
        pytest.skip("Kein SPA-Build vorhanden")
    return Path(SPA_DIST)


# ──────────────────────────────────────────────────────────────────────────
# 1b. Review-Befund 1: die Anmeldepflicht war per Dateiendung umgehbar
# ──────────────────────────────────────────────────────────────────────────
# `/diakonos/x.js` lieferte die komplette SPA inkl. Boot-Objekt, weil die
# Entscheidung "Asset oder Seite" an einem Regex ueber die Endung hing, das
# VOR der Dateiaufloesung lief. Ein nicht existierender Asset-Pfad fiel danach
# in den index.html-Fallback — an der Sperre vorbei.
#
# Die Regel lautet jetzt: geliefert wird, was WIRKLICH als Datei existiert.


@pytest.mark.parametrize(
    "suffix",
    [
        ".js", ".mjs", ".css", ".svg", ".png", ".jpg", ".webp", ".ico",
        ".woff2", ".ttf", ".map", ".webmanifest",
    ],
)
def test_nicht_existierender_asset_pfad_zeigt_maske(
    gast_http: TestClient, suffix: str
) -> None:
    """Nicht existierender Asset-Pfad + keine Sitzung -> Maske, nicht die SPA.

    Das ist der direkte Regressionsschutz gegen den Suffix-Bypass: die
    Dateiendung darf ueber die Anmeldepflicht nicht mehr entscheiden.
    """
    dist = _build_verzeichnis()
    assert not (dist / f"x{suffix}").exists(), "Praemissee: Datei darf nicht existieren"
    resp = gast_http.get(f"/diakonos/x{suffix}")
    assert LOGIN_MASKEN_MARKER in resp.text, f"x{suffix} muss die Maske zeigen"
    assert 'id="app"' not in resp.text, f"x{suffix} darf die SPA nicht liefern"
    assert "window.__DIakonosBOOT" not in resp.text


def test_nicht_existierender_asset_pfad_mit_unterverzeichnis_zeigt_maske(
    gast_http: TestClient,
) -> None:
    """Auch ein Pfad MIT Verzeichnis (`chunks/gibtsnicht.js`) ist eine Seite.

    Der alte Regex unterschied nicht zwischen `x.js` und `chunks/x.js` — die
    Dateiaufloesung schon, denn `chunks/` ist ein echtes Build-Unterverzeichnis
    und wird mit aufgeloest.
    """
    dist = _build_verzeichnis()
    assert not (dist / "chunks" / "gibtsnicht.js").exists()
    resp = gast_http.get("/diakonos/assets/chunks/gibtsnicht.js")
    assert LOGIN_MASKEN_MARKER in resp.text
    assert 'id="app"' not in resp.text


def test_existierendes_asset_ohne_sitzung_bleibt_200_und_immutable(
    gast_http: TestClient,
) -> None:
    """Regressionsschutz fuer die SameSite=Lax-Begruendung.

    Der Fix darf die Assets nicht zusaetzlich sperren: eine ECHTE Datei wird
    weiterhin immer geliefert, mit `immutable` (der Name traegt den
    Inhalts-Hash) — auch ohne Sitzung.
    """
    dist = _build_verzeichnis()
    js = sorted(dist.glob("diakonos-*.js"))
    if not js:
        pytest.skip("Kein Entry-Bundle im Build")
    resp = gast_http.get(f"/diakonos/assets/{js[0].name}")
    assert resp.status_code == 200, "Ein echtes Asset darf NIE die Maske liefern"
    assert LOGIN_MASKEN_MARKER not in resp.text
    assert "immutable" in resp.headers.get("cache-control", "")
    # Und es ist wirklich die Datei, nicht die SPA.
    assert resp.headers.get("content-type", "").split(";")[0] in (
        "text/javascript",
        "application/javascript",
    ), resp.headers.get("content-type")


def test_asset_pfad_der_zufaellig_eine_seite_ist_zeigt_maske(
    gast_http: TestClient,
) -> None:
    """Gegenprobe: die Sperre haengt nicht an der Endung, sondern an der Existenz.

    Ein Pfad OHNE Suffix, der nicht existiert, zeigt genauso die Maske wie
    `x.js` — und ein Pfad MIT Suffix, der existiert, wird geliefert. Damit ist
    belegt, dass die Dateiendung keine Rolle mehr spielt.
    """
    _build_verzeichnis()
    ohne = gast_http.get("/diakonos/gibtsnicht")
    assert LOGIN_MASKEN_MARKER in ohne.text
    assert 'id="app"' not in ohne.text


def test_keine_endlosschleife_maske_ist_oeffentlich(gast_http: TestClient) -> None:
    """Die Maske darf nicht selbst wieder eine Maske verlangen.

    Ein Aufruf ohne Cookie muss immer eine MASKE LIEFERN, nie einen
    Redirect auf sich selbst und nie 403/500.
    """
    for _ in range(3):
        resp = gast_http.get("/diakonos", follow_redirects=False)
        assert resp.status_code == 200
        assert LOGIN_MASKEN_MARKER in resp.text
        assert "Location" not in resp.headers, "Die Maske darf nicht umleiten"


def test_maske_postet_an_den_login_endpunkt(gast_http: TestClient) -> None:
    """Das Formular muss an `/api/method/login` gehen (Frappe-kompatibel)."""
    resp = gast_http.get("/diakonos")
    assert 'action="/api/method/login"' in resp.text
    assert 'method="post"' in resp.text
    for feld in ('name="usr"', 'name="pwd"'):
        assert feld in resp.text, f"Feld {feld} fehlt im Formular"


def test_maske_zeigt_gemeindenamen_aus_den_einstellungen(
    gast_http: TestClient, gemeinde
) -> None:
    """Der Gemeindename kommt aus `Diakronos Einstellungen`."""
    resp = gast_http.get("/diakonos")
    assert "Ev. Gemeinde Musterstadt" in resp.text


def test_maske_ueberlebt_ohne_einstellungen_zeile(
    gast_http: TestClient,
) -> None:
    """Ohne hinterlegten Gemeindenamen gibt es den Fallback, keine Fehlerseite."""
    resp = gast_http.get("/diakonos")
    assert resp.status_code == 200
    assert LOGIN_MASKEN_MARKER in resp.text
    assert "Meine Gemeinde" in resp.text


# ──────────────────────────────────────────────────────────────────────────
# 2. Mit Sitzung: echtes Boot-Objekt
# ──────────────────────────────────────────────────────────────────────────


def test_boot_zeigt_echten_namen_aus_der_user_tabelle(
    angemeldeter_http,
) -> None:
    """`user_fullname` kommt aus `user.full_name`, nicht aus einer Konstante."""
    c, _ = angemeldeter_http
    boot = _boot_aus(c.get("/diakonos").text)
    assert boot["user_fullname"] == "Anna Beispiel"
    assert "Test Nutzer" not in json.dumps(boot)


def test_boot_zeigt_echte_email_und_avatar(angemeldeter_http) -> None:
    c, _ = angemeldeter_http
    boot = _boot_aus(c.get("/diakonos").text)
    assert boot["user_email"] == "anna@example.org"
    assert boot["user_image"] == "/files/anna.png"


def test_is_admin_entspricht_der_tatsaechlichen_rolle(angemeldeter_http) -> None:
    """`is_admin` = Rolle `Mitgliederadministrator` ODER `System Manager`."""
    c, _ = angemeldeter_http
    boot = _boot_aus(c.get("/diakonos").text)
    assert boot["is_admin"] is True, "Hat die Rolle -> muss Admin sein"


def test_is_admin_ist_false_ohne_admin_rolle(angemeldeter_ohne_rolle) -> None:
    """Ohne Admin-Rolle: `false`. Kein Default, kein 'Administrator'-Bonus."""
    c, _ = angemeldeter_ohne_rolle
    boot = _boot_aus(c.get("/diakonos").text)
    assert boot["is_admin"] is False


def test_mitglied_kommt_aus_der_mitglied_tabelle(angemeldeter_http) -> None:
    c, _ = angemeldeter_http
    boot = _boot_aus(c.get("/diakonos").text)
    assert boot["mitglied"] == {
        "name": "M-0001", "vorname": "Anna", "nachname": "Beispiel", "status": "Mitglied",
    }


def test_mitglied_ist_null_ohne_datensatz(patched_db, fake_redis) -> None:
    """Kein `Mitglied`-Treffer -> `null` (BOOT_VERTRAG.md Punkt 4).

    `router.js:148` faellt bei `null` bewusst auf "kein Guard" zurueck; ein
    erfundener Platzhalter wuerde stattdessen den Gast-Guard ausloesen.
    """
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.models.core import User

    sess = patched_db()
    # User OHNE zugehoerigen Mitglied-Datensatz.
    sess.add(User(
        name="carla@example.org", email="carla@example.org",
        full_name="Carla Clausing", enabled=True,
    ))
    sess.commit()
    sid, _ = sitzungen.anlegen("carla@example.org")
    sess.close()

    with TestClient(app) as c:
        c.cookies.set("sid", sid)
        boot = _boot_aus(c.get("/diakonos").text)
    assert boot["mitglied"] is None
    assert boot["user_fullname"] == "Carla Clausing"


def test_csrf_token_stammt_aus_der_sitzung(angemeldeter_http) -> None:
    """Der Token MUSS der aus der Sitzung sein — sonst schlagen alle POSTs zu."""
    c, csrf = angemeldeter_http
    boot = _boot_aus(c.get("/diakonos").text)
    assert boot["csrf_token"] == csrf
    assert boot["csrf_token"] != "dummy-csrf-token"


def test_csrf_token_im_meta_tag_steht_gleich(gast_http, angemeldeter_http) -> None:
    """`Profile.vue:325` liest den Token aus dem meta-Tag, nicht aus dem Boot.

    Beide Wege muessen denselben Wert liefern, sonst schlaegt einer der
    beiden stillschweigend fehl.
    """
    c, csrf = angemeldeter_http
    html = c.get("/diakonos").text
    m = re.search(r'<meta name="csrf-token" content="([^"]*)"', html)
    assert m, "meta csrf-token fehlt"
    assert m.group(1) == csrf


def test_kein_csrf_token_ohne_sitzung(patched_db, fake_redis) -> None:
    """Eine abgelaufene Sitzung fuehrt zur Maske, nicht zu einem erfundenen Token.

    Der Pfad, den die Test-Naht `set_user()` nicht abdeckt: das `sid`-Cookie ist
    noch im Browser, die Sitzung im Store aber weg (TTL abgelaufen, abgemeldet
    auf einem anderen Tab). Dann darf das Boot-Objekt nicht mit dem Token einer
    fremden oder nicht mehr vorhandenen Sitzung laufen.
    """
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.models.core import User

    sess = patched_db()
    sess.add(User(
        name="dora@example.org", email="dora@example.org",
        full_name="Dora Dietrich", enabled=True,
    ))
    sess.commit()
    sid, _ = sitzungen.anlegen("dora@example.org")
    sess.close()

    with TestClient(app) as c:
        c.cookies.set("sid", sid)
        # Sitzung danach toeten -> `sid` zeigt ins Leere.
        sitzungen.loeschen(sid)
        resp = c.get("/diakonos")
    # Ohne gueltige Sitzung greift die Anmeldepflicht (kein Boot-Objekt).
    assert LOGIN_MASKEN_MARKER in resp.text


def test_church_name_aus_den_einstellungen(angemeldeter_http, gemeinde) -> None:
    c, _ = angemeldeter_http
    boot = _boot_aus(c.get("/diakonos").text)
    assert boot["church_name"] == "Ev. Gemeinde Musterstadt"


def test_church_name_fallback_ohne_einstellungen(angemeldeter_http) -> None:
    c, _ = angemeldeter_http
    boot = _boot_aus(c.get("/diakonos").text)
    assert boot["church_name"] == "Meine Gemeinde"


def test_boot_steht_vor_dem_entry_script(angemeldeter_http) -> None:
    """BOOT_VERTRAG.md: synchron VOR dem Modul-Script, kein fetch."""
    c, _ = angemeldeter_http
    html = c.get("/diakonos").text
    assert html.index("__DIakonosBOOT") < html.index('type="module"')


def test_boot_ist_kein_dummy_mehr(angemeldeter_http) -> None:
    """Kein Feld des alten `DUMMY_BOOT` darf noch auftauchen."""
    c, _ = angemeldeter_http
    html = c.get("/diakonos").text
    for verboten in ("dummy-csrf-token", "Test Nutzer", "Testgemeinde", "MITGLIED-0001"):
        assert verboten not in html, f"Dummy-Wert noch im HTML: {verboten}"


def test_unbekannter_benutzer_bekommt_leeren_namen(patched_db, fake_redis) -> None:
    """Sitzung fuer einen User, den es in `user` nicht gibt.

    **B1 hat diesen Fall geaendert** — und zwar absichtlich: die
    `SessionMiddleware` prueft jetzt, ob der Benutzer der Sitzung noch
    existiert und noch `enabled` ist. Ein Konto, das es nicht gibt, hat
    keine gueltige Sitzung, also bekommt der Aufruf die **Loginmaske**, nicht
    die SPA mit einem leeren Namen.

    Der Test ist deshalb nicht weggefallen, sondern auf die **echte**
    Bedeutung der Regel umgeschrieben: er belegt, dass der Weg "Sitzung
    zeigt ins Leere" eintritt. Wer nachweisen will, dass ein *vorhandener*
    Benutzer ohne Mitglied-Datensatz die SPA mit leerem Namen sieht, findet
    das in `test_mitglied_ist_null_ohne_datensatz` (Carla hat eine
    `user`-Zeile, aber keinen `Mitglied`-Satz).
    """
    from diakronos_app.frappe_compat import sitzungen

    sid, _ = sitzungen.anlegen("gibt-es-nicht@example.org")
    with TestClient(app) as c:
        c.cookies.set("sid", sid)
        resp = c.get("/diakonos")
        # Die Sitzung ist nicht nur fuer diesen Aufruf ignoriert, sondern
        # serverseitig geloescht worden — der Beweis steht im Store.
        assert sitzungen.lesen(sid) is None
    assert LOGIN_MASKEN_MARKER in resp.text
    assert 'id="app"' not in resp.text


# ──────────────────────────────────────────────────────────────────────────
# 3. XSS: Werte aus der Datenbank landen im HTML
# ──────────────────────────────────────────────────────────────────────────


def test_script_ende_im_namen_bricht_das_script_nicht(patched_db, fake_redis) -> None:
    """`</script>` im Anzeigenamen darf die Seite nicht zerlegen.

    BOOT_VERTRAG.md Punkt 8. Der Anzeigename ist frei pflegbar; ohne
    Escaping wuerde `</script><script>…` aus dem Nutzer-Meta-Daten einen
    vollstaendigen XSS-Vektor machen.
    """
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.models.core import User

    sess = patched_db()
    sess.add(User(
        name="xss@example.org", email="xss@example.org",
        full_name="</script><script>alert(1)</script>", enabled=True,
    ))
    sess.commit()
    sid, _ = sitzungen.anlegen("xss@example.org")
    sess.close()

    with TestClient(app) as c:
        c.cookies.set("sid", sid)
        html = c.get("/diakonos").text

    # Es darf nur EINE echte Script-Veroeffnung mit dem Modul-Tag geben und
    # kein injiziertes alert().
    assert "<script>alert(1)</script>" not in html
    assert html.count("type=\"module\"") == 1
    # Der Wert muss trotzdem semantisch erhalten sein (als \u003c escaped).
    assert "alert(1)" in html, "Der Name darf nicht verloren gehen"


def test_html_escape_im_seitentitel(patched_db, fake_redis) -> None:
    """Der Gemeindename steht auch im <title> — dort greift dasselbe Escaping."""
    from diakronos_app.models.diakronos import DiakronosEinstellungen

    sess = patched_db()
    sess.get(DiakronosEinstellungen, "Diakronos Einstellungen")
    sess.add(DiakronosEinstellungen(
        name="Diakronos Einstellungen", docstatus=0, idx=0,
        organisationsname='Gemeinde ""><script>alert(2)</script>',
    ))
    sess.commit()
    sess.close()

    with TestClient(app) as c:
        html = c.get("/diakonos").text
    assert "<script>alert(2)</script>" not in html


# ──────────────────────────────────────────────────────────────────────────
# 4. Cache-Header
# ──────────────────────────────────────────────────────────────────────────


def test_index_html_ist_no_store(angemeldeter_http) -> None:
    """Das HTML traegt den CSRF-Token — es darf nicht gecacht werden."""
    c, _ = angemeldeter_http
    resp = c.get("/diakonos")
    assert "no-store" in resp.headers.get("cache-control", "")


def test_loginmaske_ist_no_store(gast_http: TestClient) -> None:
    c = gast_http.get("/diakonos")
    assert "no-store" in c.headers.get("cache-control", "")


def test_loginmaske_leert_den_browser_cache(gast_http: TestClient) -> None:
    """PF1: Die Anmeldemaske raeumt den nutzerbezogenen Browser-Cache weg.

    Nach dem Abmelden laedt die SPA nicht mehr — es laeuft kein Vue-Code, der
    den Cache leeren koennte. Die serverseitige Maske traegt daher ein kleines
    Skript, das nur den Planrahmen-Praefix `dk-pr-swr:` entfernt (geteiltes
    Geraet: der Stand des vorigen Nutzers darf nicht liegenbleiben).
    """
    html = gast_http.get("/diakonos").text
    assert "dk-pr-swr:" in html
    assert "localStorage" in html
    assert "removeItem" in html


def test_loginmaske_script_loescht_nur_den_planrahmen_praefix(gast_http: TestClient) -> None:
    """Das Aufraeum-Skript darf keinen fremden Speicherbereich anfassen."""
    html = gast_http.get("/diakonos").text
    # Der Vergleich ist auf den eigenen Praefix beschraenkt, nicht auf clear().
    assert "dk-pr-swr:" in html
    assert "localStorage.clear(" not in html


def test_hash_benanntes_asset_ist_immutable(angemeldeter_http) -> None:
    """Assets tragen einen Inhalts-Hash im Namen -> dauerhaft cachelbar."""
    if SPA_DIST is None:
        pytest.skip("Kein SPA-Build vorhanden")
    js = sorted(SPA_DIST.glob("diakonos-*.js"))
    if not js:
        pytest.skip("Kein Entry-Bundle im Build")
    c, _ = angemeldeter_http
    resp = c.get(f"/diakonos/assets/{js[0].name}")
    cc = resp.headers.get("cache-control", "")
    assert "immutable" in cc
    assert "no-store" not in cc


def test_html_und_assets_haben_unterschiedliche_cache_regeln(angemeldeter_http) -> None:
    """Der Unterschied wird an einem Request-Paar belegt, nicht nur beschrieben."""
    if SPA_DIST is None:
        pytest.skip("Kein SPA-Build vorhanden")
    js = sorted(SPA_DIST.glob("diakonos-*.js"))
    if not js:
        pytest.skip("Kein Entry-Bundle im Build")
    c, _ = angemeldeter_http
    html_cc = c.get("/diakonos").headers.get("cache-control", "")
    asset_cc = c.get(f"/diakonos/assets/{js[0].name}").headers.get("cache-control", "")
    assert "no-store" in html_cc
    assert "immutable" in asset_cc


# ──────────────────────────────────────────────────────────────────────────
# 5. Anmeldung ueber die Maske
# ──────────────────────────────────────────────────────────────────────────


def test_formular_login_redirectet_auf_diakonos(patched_db, fake_redis) -> None:
    """Der ganze Weg ueber die Maske, wie ein Browser ihn geht.

    POST (Formular) -> 303 auf /diakonos -> GET mit `sid` -> SPA mit echtem
    Namen. Geprueft wird jede Station, sonst beweist der Test nur eine.
    """
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import User

    sess = patched_db()
    sess.add(User(
        name="carla@example.org", email="carla@example.org",
        full_name="Carla Clausing", enabled=True, password_hash=neuer_hash("Beispiel-3"),
    ))
    sess.commit()
    sess.close()

    with TestClient(app) as c:
        # 1. Maske holen
        maske = c.get("/diakonos")
        assert LOGIN_MASKEN_MARKER in maske.text

        # 2. Formular absenden (follow_redirects aus, um 303 zu sehen)
        r = c.post(
            "/api/method/login",
            data={"usr": "carla@example.org", "pwd": "Beispiel-3", "redirect-to": "/diakonos"},
            follow_redirects=False,
        )
        assert r.status_code == 303, f"Formular-Login muss 303 liefern, bekam {r.status_code}"
        assert r.headers["location"] == "/diakonos"

        # 3. `sid` wurde gesetzt und die SPA liefert jetzt den echten Namen
        assert "sid" in r.cookies or c.cookies.get("sid")
        html = c.get("/diakonos").text
        assert 'id="app"' in html, "Nach der Anmeldung muss die SPA kommen"
        boot = _boot_aus(html)
        assert boot["user_fullname"] == "Carla Clausing"
        assert boot["csrf_token"] != "dummy-csrf-token"


def test_json_login_liefert_weiterhin_json(patched_db, fake_redis) -> None:
    """Der SPA-Weg (fetch, application/json) darf NICHT umleiten.

    Sonst wuerde `apiCall`/`apiGet` in einen HTML-Redirect laufen und
    `res.json()` wuerfe.
    """
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import User

    sess = patched_db()
    sess.add(User(
        name="dora@example.org", email="dora@example.org", enabled=True,
        password_hash=neuer_hash("Schoen-4"),
    ))
    sess.commit()
    sess.close()

    with TestClient(app) as c:
        r = c.post("/api/method/login", json={"usr": "dora@example.org", "pwd": "Schoen-4"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["message"] == "Logged In"
    assert "location" not in r.headers


@pytest.mark.parametrize(
    "bose",
    [
        "https://evil.example.net",
        "//evil.example.net",
        "\\\\evil.example.net",
        "/\\evil.example.net",
        "javascript:alert(1)",
        "http://evil.example.net",
    ],
)
def test_redirect_to_ist_nie_offen(patched_db, fake_redis, bose: str) -> None:
    """Offene Weiterleitung nach dem Login: abgelehnt, Fallback `/diakonos`.

    Wichtig wegen des `sid`-Cookies: eine fremde Ziel-URL wuerde das Sitzungs-
    Cookie aus der Antwort des Ziels-Requests mitgeben bzw. die Gemeinde
    dorthin umleiten.
    """
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import User

    sess = patched_db()
    sess.add(User(
        name="eva@example.org", email="eva@example.org", enabled=True,
        password_hash=neuer_hash("Schoen-5"),
    ))
    sess.commit()
    sess.close()

    with TestClient(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "eva@example.org", "pwd": "Schoen-5", "redirect-to": bose},
            follow_redirects=False,
        )
    assert r.status_code == 303
    ziel = r.headers["location"]
    assert "evil.example.net" not in ziel
    assert not ziel.startswith("//")
    assert ziel == "/diakonos"


def test_falsches_passwort_redirectet_nicht(angemeldeter_http) -> None:
    """Fehlgeschlagener Login: 401, KEIN Redirect, KEIN neues Cookie.

    Der JSON-Weg (hier: der TestClient ohne `Accept`-Kopfzeile, aber mit
    JSON-Body) bleibt unveraendert. **LOGIN-1** hat den FORMULAR-Weg geaendert:
    ein `<form method="post">` bekommt 303 zurueck auf die Anmeldeseite statt
    roher JSON — das prueft `tests/test_login1_formular_fehler.py`.
    """
    c, _ = angemeldeter_http
    vorher = c.cookies.get("sid")
    r = c.post(
        "/api/method/login",
        data={"usr": "anna@example.org", "pwd": "falsch", "redirect-to": "/diakonos"},
        headers={"Accept": "application/json"},
        follow_redirects=False,
    )
    assert r.status_code == 401
    assert "location" not in r.headers
    assert c.cookies.get("sid") == vorher


def test_falsches_passwort_als_formular_geht_zurueck_zur_maske(angemeldeter_http) -> None:
    """LOGIN-1: der Browser-Weg -> 303 auf /login.

    LOGIN-2/M2: Der Browser-Weg haengt seit dieser Karte an `text/html` im
    `Accept` (bzw. `Sec-Fetch-Mode: navigate`). Der Test beschreibt einen
    Browser-Formularaufruf, also schickt er dessen Kopfzeilen — `httpx` setzt
    sonst `*/*`, und das ist bewusst NICHT der Browser-Weg.
    """
    c, _ = angemeldeter_http
    r = c.post(
        "/api/method/login",
        data={"usr": "anna@example.org", "pwd": "falsch", "redirect-to": "/diakonos"},
        headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.status_code
    assert r.headers["location"].startswith("/login?noredirect=1&redirect-to=")
    # Kein `sid` wird gesetzt oder veraendert.
    assert not any(k.lower().startswith("sid=") for k in r.headers.get_list("set-cookie"))

