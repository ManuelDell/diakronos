"""P2-4c: Freigabe und Gelesen-Markierung duerfen keine Nachrichten verlieren."""
from sqlalchemy import select

from diakronos_app.frappe_compat.api_helpers import _create
from diakronos_app.models.core import NotificationLog
from test_p2_4b_benachrichtigungen import (
    _moderator_welt, _notifications, _speichere_termin, anmelden,
)

AUDIT = "/api/method/diakronos.diakonos.api.audit."


def test_nur_angezeigte_eigene_nachrichten_gelesen(client, patched_db):
    _moderator_welt(patched_db)
    eigene = [_create("Notification Log", {
        "subject": f"Nachricht {i}", "for_user": "talente", "read": 0,
    }) for i in range(31)]
    fremde = _create("Notification Log", {
        "subject": "Fremd", "for_user": "moderator", "read": 0,
    })
    anmelden(client, "talente")
    angezeigt = client.post(AUDIT + "get_my_notifications", json={"limit": 30})
    assert angezeigt.status_code == 200, angezeigt.text
    namen = [n["name"] for n in angezeigt.json()["message"]["data"]]
    assert len(namen) == 30
    r = client.post(AUDIT + "mark_notifications_read", json={"names": namen + [fremde]})
    assert r.status_code == 200, r.text
    with patched_db() as s:
        assert sum(bool(s.get(NotificationLog, n).read) for n in eigene) == 30
        assert not s.get(NotificationLog, fremde).read
    assert client.post(AUDIT + "get_unread_notifications").json()["message"]["unread_count"] == 1


def test_ohne_liste_wird_nichts_gelesen(client, patched_db):
    _moderator_welt(patched_db)
    _create("Notification Log", {"subject": "Ungesehen", "for_user": "talente", "read": 0})
    anmelden(client, "talente")
    r = client.post(AUDIT + "mark_notifications_read", json={})
    assert r.status_code == 400, r.text
    assert "neu laden" in r.json()["message"]
    assert client.post(AUDIT + "get_unread_notifications").json()["message"]["unread_count"] == 1


def test_vorschlag_freigabe_benachrichtigt_einmal(client, patched_db):
    from diakronos_app.models.kronos import ElementAenderung
    _moderator_welt(patched_db)
    # Ein Schreiber, der nicht selbst Moderator ist.
    from diakronos_app.models.core import HasRole, User
    with patched_db.begin() as s:
        s.add(User(name="schreiber", email="schreiber", enabled=True))
        s.add(HasRole(name="r-sch", parent="schreiber", parenttype="User",
                      parentfield="roles", role="Mitglied"))
    anmelden(client, "schreiber")
    _speichere_termin(client, element_name="Gottesdienst", element_start="2026-12-06 14:00:00",
                      element_end="2026-12-06 15:00:00")
    assert _notifications(patched_db, "talente") == []
    with patched_db() as s:
        vorschlag = s.scalar(select(ElementAenderung.name))
    assert vorschlag
    anmelden(client, "moderator")
    r = client.post("/api/method/diakronos.kronos.api.event_crud.aenderung_freigeben",
                    json={"name": vorschlag})
    assert r.status_code == 200, r.text
    assert len(_notifications(patched_db, "talente")) == 1
