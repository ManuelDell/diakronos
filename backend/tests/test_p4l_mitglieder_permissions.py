"""P4l — Beweise fuer die drei ehemaligen `TODO(P3)`-Platzhalter in
`api/mitglieder.py`.

Die Karte fordert fuer JEDE der drei Stellen beide Richtungen:
  * ein Nicht-Admin SIEHT Datensaetze SEINER Gruppe/seines Bereichs,
  * ein Nicht-Admin SIEHT Datensaetze einer FREMDEN Gruppe NICHT,
  * ein Admin sieht alles.

Die Hierarchie (2 Dienstbereiche + isolierte Fremdwelt DB-C, Gruppen,
Untergruppen, Verantwortliche) kommt aus `tests.test_permissions.hierarchie` —
dieselbe Fixture, die schon die 180er-Matrix treibt. Hier wird sie bewusst
nicht neu erfunden.

Stelle 1 = `get_mitglieder_liste` (Sichtbarkeitsfilter)
Stelle 2 = `_user_email` (Benutzer-/E-Mail-Aufloesung des Filters)
Stelle 3 = `_is_admin` (Rollenpruefung)

Die Tests laufen ueber den echten HTTP-Pfad (`/api/method/mitglieder.<fn>`),
nicht ueber `registry.lookup()`.
"""

from __future__ import annotations

import pytest

from tests.test_permissions import hierarchie  # noqa: F401 — Fixture


@pytest.fixture()
def sess(patched_db):
    """Die Session der Test-DB (die Hierarchie-Fixture legt ihre Zeilen darin ab)."""
    s = patched_db()
    yield s
    s.close()


def _namen(response) -> set[str]:
    return {e.get("name") for e in response.json()["message"]["data"]}


def _set_user(user: str) -> None:
    from diakronos_app.frappe_compat.session import set_user

    set_user(user)


# ════════════════════════════════════════════════════════════════════════════
# Stelle 1 — `get_mitglieder_liste`: ancestor_path-Segmente per OR-LIKE
# ════════════════════════════════════════════════════════════════════════════
#
# Vor der Aenderung stand hier `permission_filter_sql = "m.email = %(user_email)s"`;
# ein normales Mitglied sah ausschliesslich sich selbst. Das Original
# (mitglieder.py:47-70) laesst zusaetzlich alle Segmente seines ancestor_path
# durch — die Mitgliederliste war damit fuer Nicht-Admins faktisch leer.
#
# Fixture-Geometrie (tests/test_permissions.py):
#   mitglied-a@example.org  /G-A1/|/DB-A/
#      seine Welt:  M-gruppe-a1      /G-A1/|/DB-A/       (gleiche Gruppe)
#                   M-verantw-a      /G-A1/UG-A1/|/DB-A/ (gleiche Gruppe)
#                   M-untergruppe-a1 /UG-A1/G-A1/|/DB-A/ (gleicher Bereich)
#      fremd:       M-eigen-b        /G-B1/|/DB-B/       (anderer Bereich)
#                   M-gruppe-b1      /G-C1/|/DB-C/       (isolierte Fremdwelt)


def test_liste_nicht_admin_sieht_eigene_gruppe_und_bereich(client, hierarchie, sess):  # noqa: F811
    """Sichtbarkeit (Stelle 1): Gruppen- UND Bereichs-Segmente tragen."""
    _set_user("mitglied-a@example.org")
    r = client.get("/api/method/mitglieder.get_mitglieder_liste", params={"limit": 50})
    assert r.status_code == 200, r.text

    namen = _namen(r)
    # eigener Datensatz + gleiche Gruppe + gleicher Dienstbereich (als Untergruppe
    # erscheint M-untergruppe-a1 ueber das Bereichs-Segment DB-A)
    assert "M-gruppe-a1" in namen, f"eigenes Mitglied fehlt: {namen}"
    assert "M-verantw-a" in namen, f"gleiche Gruppe G-A1 fehlt: {namen}"
    assert "M-untergruppe-a1" in namen, f"gleicher Dienstbereich DB-A fehlt: {namen}"


def test_liste_nicht_admin_sieht_fremde_gruppe_nicht(client, hierarchie, sess):  # noqa: F811
    """Die Gegenrichtung (Stelle 1): fremde Bereiche bleiben unsichtbar."""
    _set_user("mitglied-a@example.org")
    r = client.get("/api/method/mitglieder.get_mitglieder_liste", params={"limit": 50})
    assert r.status_code == 200, r.text

    namen = _namen(r)
    assert "M-eigen-b" not in namen, f"DB-B-Mitglied darf nicht sichtbar sein: {namen}"
    assert "M-gruppe-b1" not in namen, f"DB-C-Mitglied darf nicht sichtbar sein: {namen}"


def test_liste_nicht_admin_in_fremdem_bereich_sieht_seinen_bereich(client, hierarchie, sess):  # noqa: F811
    """Kontrollprobe gegen die Fixture: B sieht seine eigene Welt (und nur die)."""
    _set_user("mitglied-b@example.org")
    r = client.get("/api/method/mitglieder.get_mitglieder_liste", params={"limit": 50})
    assert r.status_code == 200, r.text

    namen = _namen(r)
    assert "M-eigen-b" in namen, f"eigenes Mitglied fehlt: {namen}"
    assert "M-gruppe-a1" not in namen, f"DB-A-Mitglied darf nicht sichtbar sein: {namen}"
    assert "M-untergruppe-a1" not in namen
    assert "M-verantw-a" not in namen
    assert "M-gruppe-b1" not in namen, f"DB-C bleibt auch fuer B fremd: {namen}"


def test_liste_admin_sieht_alles(client, hierarchie, sess):  # noqa: F811
    """Admin-Sicht (Stelle 1): alle fuenf Mitglieder inkl. der Fremdwelt DB-C."""
    _set_user("admin@example.org")
    r = client.get("/api/method/mitglieder.get_mitglieder_liste", params={"limit": 50})
    assert r.status_code == 200, r.text
    assert {
        "M-gruppe-a1", "M-untergruppe-a1", "M-verantw-a", "M-eigen-b", "M-gruppe-b1",
    } <= _namen(r)


def test_liste_total_zaehlt_nur_sichtbare_zeilen(client, hierarchie, sess):  # noqa: F811
    """`total` speist sich aus DEMSELBEN Filter wie die Datenabfrage.

    Das Original benutzt fuer `count_query` denselben `permission_filter_sql`
    (mitglieder.py:106-119). Laeuft der Zaehler ohne Filter, verraet die
    Pagination die Existenz fremder Mitglieder.
    """
    _set_user("mitglied-a@example.org")
    r = client.get("/api/method/mitglieder.get_mitglieder_liste", params={"limit": 50})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["total"] == 3, f"total={msg['total']} — erwartet 3 (eigene Gruppe/Bereich)"
    assert len(msg["data"]) == 3, [e["name"] for e in msg["data"]]

    _set_user("admin@example.org")
    r = client.get("/api/method/mitglieder.get_mitglieder_liste", params={"limit": 50})
    assert r.json()["message"]["total"] == 5, "Admin muss alle fuenf zaehlen"


def test_liste_ohne_mitglied_faellt_auf_email_match_zurueck(client, hierarchie, sess):  # noqa: F811
    """Nicht-Admin OHNE eigenen Datensatz: nur der E-Mail-Fallback, nie mehr.

    Das ist der fail-closed-Zweig, der auch vor P4l schon galt — er darf durch
    die neue Verzweigung nicht verloren gehen.
    """
    _set_user("ohne-mitglied@example.org")
    r = client.get("/api/method/mitglieder.get_mitglieder_liste", params={"limit": 50})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["data"] == [], f"ohne Mitglied-Datensatz darf nichts sichtbar sein: {msg}"
    assert msg["total"] == 0


# ════════════════════════════════════════════════════════════════════════════
# Stelle 2 — `_user_email`: DocType `User` ist modelliert
# ════════════════════════════════════════════════════════════════════════════
#
# Vor der Aenderung stand im Docstring, der DocType `User` existiere nicht und
# der Filter koenne deshalb nur leerlaufen. Er existiert (`models/core.py`,
# `inventar/live_schema_ist.tsv`) — der E-Mail-Match greift.


def test_user_email_liest_echte_user_tabelle(client, hierarchie, sess):  # noqa: F811
    """`_user_email()` liefert die E-Mail aus `tabUser`, nicht den Loginnamen."""
    from diakronos_app.api.mitglieder import _user_email

    _set_user("mitglied-a@example.org")
    assert _user_email() == "mitglied-a@example.org"


def test_user_email_fallback_ohne_user_zeile(client, hierarchie, sess):  # noqa: F811
    """Benutzer OHNE `tabUser`-Zeile -> Fallback auf den Benutzernamen (Original: `or user`)."""
    from diakronos_app.api.mitglieder import _user_email

    _set_user("giant-nobody@example.org")
    assert _user_email() == "giant-nobody@example.org"


def test_user_email_traegt_den_email_fallback_der_liste(client, hierarchie, sess):  # noqa: F811
    """Ende-zu-Ende (Stelle 2): der Fallback-Zweig der Liste findet den eigenen Datensatz.

    Ein Benutzer ohne Mitglied-Datensatz, dessen Login der E-Mail eines
    Mitglieds entspricht — genau der Pfad, den der P2b-Platzhalter leerlaufen
    liess. `M-verantw-a` hat die E-Mail `verantw-a@example.org`, aber keine
    `tabUser`-Zeile; das ist Fallback UND Treffer in einem.
    """
    from diakronos_app.models.diakonos import Mitglied as _  # noqa: F401  (Modelle registriert)

    _set_user("verantw-a@example.org")
    r = client.get("/api/method/mitglieder.get_mitglieder_liste", params={"limit": 50})
    assert r.status_code == 200, r.text
    # `verantw-a@example.org` hat per Fixture keinen User-Datensatz, liefert also
    # ueber den Fallback die E-Mail und trifft damit das eigene Mitglied.
    assert "M-verantw-a" in _namen(r), _namen(r)


# ════════════════════════════════════════════════════════════════════════════
# Stelle 3 — `_is_admin`: die Rollenpruefung
# ════════════════════════════════════════════════════════════════════════════
#
# Vor der Aenderung stand hier nur der TODO-Kommentar; die Funktion selbst war
# bereits korrekt (has_role). Die Tests halten die Richtung in BEIDE Seiten
# fest — inklusive der beiden Rollen aus `ADMIN_ROLES` und der Gegenprobe,
# dass ein einfaches Mitglied nicht durchrutscht.


@pytest.mark.parametrize(
    "user,erwartet",
    [
        ("admin@example.org", True),             # System Manager
        ("mitarbadmin@example.org", True),       # Mitgliederadministrator
        ("mitglied-a@example.org", False),       # Mitglied, ohne Rolle
        ("ohne-mitglied@example.org", False),    # User ohne Rolle
        ("Guest", False),                        # kein Login
    ],
)
def test_is_admin_rollen(client, hierarchie, sess, user, erwartet):  # noqa: F811
    from diakronos_app.api.mitglieder import _is_admin

    _set_user(user)
    assert _is_admin() is erwartet, f"{user}: _is_admin()={_is_admin()}, erwartet {erwartet}"


def test_has_admin_role_ist_rollenpruefung_ohne_zweite_abfrage(client, hierarchie, sess):  # noqa: F811
    """`_has_admin_role(user, roles)` = `any(r in roles for r in ADMIN_ROLES)`.

    Dieselbe Antwort wie `_is_admin()`, nur auf bereits geholten Rollen — damit
    eine Funktion nicht zwei Rollenquellen mischt.
    """
    from diakronos_app.api.mitglieder import ADMIN_ROLES, _has_admin_role

    assert _has_admin_role("admin@example.org", ["System Manager"]) is True
    assert _has_admin_role("mitglied-a@example.org", ["Mitglied"]) is False
    assert _has_admin_role("admin@example.org", []) is False
    assert _has_admin_role("Guest", list(ADMIN_ROLES)) is False


def test_liste_rollen_entscheiden_nicht_der_benutzername(client, hierarchie, sess):  # noqa: F811
    """"Administrator" hat per Fixture KEINE Rolle -> kein Admin, kein Vollzugriff.

    Das ist die zentrale Regel der Rechtepruefung: die Admin-Sicht darf nicht an
    einem Default-Benutzernamen haengen. `is_admin()` kennt die Sonderbehandlung,
    `mitglieder._is_admin()`/`_has_admin_role()` bewusst nicht (wie das Original).
    """
    _set_user("Administrator")
    r = client.get("/api/method/mitglieder.get_mitglieder_liste", params={"limit": 50})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["data"] == [], r.text
