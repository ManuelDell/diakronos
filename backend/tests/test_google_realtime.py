"""Authenticated Socket.IO delivery, including progress from RQ processes."""
import asyncio
import threading

import httpx
import pytest
import socketio

from diakronos_app.frappe_compat import realtime, sitzungen

#: ZEIT-1 (Review): Der globale `pytest-timeout` aus `pyproject.toml` (60 s)
#: haette den Test abgebrochen, BEVOR die eigenen Wartegrenzen greifen
#: (Uvicorn-Start 30 s + Handshake 30 s + Nachricht 45 s). Der globale Wert
#: bleibt die Haenger-Bremse der Suite; hier gilt ein eigenes Budget fuer
#: genau diese Datei: laengste eigene Frist (45 s) + Reserve.
pytestmark = pytest.mark.timeout(150)


def test_socket_cannot_claim_another_user(client, monkeypatch):
    rooms = []
    async def enter(sid, room):
        rooms.append(room)
    monkeypatch.setattr(realtime.sio, "enter_room", enter)
    sid = client.cookies.get("sid")
    assert asyncio.run(realtime.connect("fake", {"HTTP_COOKIE": "sid=" + sid}, {"user": "victim@example.org"}))
    assert rooms == ["user:Administrator"]
    assert not asyncio.run(realtime.connect("fake", {}, {"user": "Administrator"}))


def test_worker_process_progress_arrives_over_socket(client):
    """Fortschritt aus einem SEPARATEN Prozess kommt beim ASGI-Client an.

    SEC-11c (R4) — zwei Races, die den Test unter Last wackeln liessen:

      1. **Beitritt vs. Publish.** `receiver.connect(...)` kehrt zurueck,
         sobald der Handshake durch ist; das `enter_room` des Servers laeuft
         aber im ASGI-Prozess und ist damit NICHT garantiert abgeschlossen.
         Wurde in diesem Fenster publiziert, ging die Nachricht an einen
         Raum, in dem noch niemand sass — der Test fiel um, ohne dass etwas
         kaputt war. Jetzt wird gemessen statt gewartet:
         `_warten_bis_empfangsbereit` publiziert eine Sonde (eigener
         Ereignisname) ueber den ECHTEN Redis-Weg, bis der Client sie erhaelt.

      2. **Fehlercode statt Vermutung.** `publish_realtime` im Unterprozess
         laeuft ueber `_emit_from_sync` -> `socketio.RedisManager`; wirft der,
         faengt `_emit_from_sync` das und loggt nur („best effort"). Der Test
         prueft deshalb den Exitcode des Publish-Prozesses selbst und zitiert
         stdout/stderr im Fehlerfall, statt auf eine Nachricht zu warten, die
         nie kommen kann.

    Netz: der Socket-Server und der Unterprozess benutzen `settings.redis_url`
    — im Test der private Redis des Stacks (`conftest._test_env`);
    `--network none` bleibt Pflicht (Kartenregel 11).
    """
    import os
    import socket
    import subprocess
    import time

    import uvicorn

    got = threading.Event()
    messages = []
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    _, socket_app = realtime.create_socket_server()
    server = uvicorn.Server(uvicorn.Config(
        socket_app, host="127.0.0.1", port=port, log_level="warning",
        timeout_graceful_shutdown=2))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    receiver = socketio.Client(reconnection=False)

    @receiver.on("gcal_import_progress")
    def receive(data):
        messages.append(data)
        got.set()

    try:
        # ZEIT-1: dieselbe Frist wie in `_warten_bis_empfangsbereit` — 200 x
        # 20 ms (4 s) war unter Last zu kurz, und der Fehlschlag sagte nichts
        # ueber die Realtime-Zustellung aus.
        _startbereit(server, frist=30)
        # ZEIT-1: `socketio.Client.wait()` ist 1 s. Unter Last (Engine.IO-
        # Handshake + Redis-Manager im ASGI-Thread) reisst das; die Aussage
        # des Tests verlangt nur, dass verbunden wird — nicht in welcher
        # Sekunde.
        receiver.connect(
            f"http://127.0.0.1:{port}",
            headers={"Cookie": "sid=" + client.cookies.get("sid")},
            transports=["polling"], wait_timeout=30)
        # (1) Der Raum muss stehen, BEVOR die eigentliche Nachricht kommt.
        _warten_bis_empfangsbereit(receiver)

        prozess = subprocess.run(
            ["python", "-c",
             "from diakronos_app.frappe_compat.realtime import publish_realtime; "
             "publish_realtime('gcal_import_progress', {'status':'done'}, "
             "user='Administrator')"],
            check=False, capture_output=True, text=True,
            env=os.environ.copy(), timeout=120)
        assert prozess.returncode == 0, (
            "Der Publish-Unterprozess scheiterte: "
            f"{prozess.returncode}\n{prozess.stdout[-800:]}\n{prozess.stderr[-800:]}")

        # (2) Nachricht abwarten — unter Last braucht Redis/EngineIO Laengeres.
        # ZEIT-1: Kommt sie nicht an, wird NACHGEMESSEN statt geraten: die
        # Sonde aus (1) ging denselben Weg und kam an — also ist nicht die
        # Zustellung kaputt, sondern der Kanal (Ereignisname/Raum) der
        # eigentlichen Nachricht. Beides steht dann im Fehlertext.
        if not got.wait(45):
            raise AssertionError(
                "Worker-Emission nicht beim ASGI-Client angekommen "
                "(Befund: die Sonde kam an, der Client ist im Raum "
                "user:Administrator und empfaengt ueber Redis; fehlt nur "
                "'gcal_import_progress' aus dem Unterprozess). Prozess: "
                f"{prozess.returncode}, stdout={prozess.stdout[-300:]!r}, "
                f"stderr={prozess.stderr[-300:]!r}")
        assert messages == [{"status": "done"}]
    finally:
        # SEC-11c (R4): TEARDOWN-REIHENFOLGE. `receiver.disconnect()` wartet
        # auf die Bestaetigung des Servers und laeuft deshalb in einen
        # 30-Sekunden-Timeout, sobald der ASGI-Server schon abbaut (gemessen:
        # `disconnect()` = 30,0 s, das ganze Testfile 38 s fuer 2 Tests).
        # Erst den Server beenden, damit nichts mehr antworten muss, dann den
        # Client schliessen — der schickt seinen Disconnect ins Leere und
        # kehrt sofort zurueck.
        server.should_exit = True
        thread.join(5)
        try:
            receiver.disconnect()
        except Exception:  # noqa: BLE001 — der Client ist danach ohnehin weg
            pass


def _startbereit(server, frist: float = 30) -> None:
    """Wartet mit Frist auf `server.started` (ZEIT-1: statt 200 x 20 ms = 4 s).

    Gemessen wird weiterhin `server.started`; unter Last (Load 15–18) brauchte
    der Uvicorn-Thread laenger als die alte Schleife erlaubte, und der Test
    fiel aus einem Grund um, der nichts mit der Zustellung zu tun hat.
    """
    import time

    ende = time.monotonic() + frist
    while time.monotonic() < ende:
        if server.started:
            return
        time.sleep(.02)
    raise AssertionError(f"Uvicorn-Thread nach {frist} s nicht gestartet")


def _warten_bis_empfangsbereit(receiver, grenze: float = 15) -> None:
    """Wartet, bis der Client NACHWEISLICH Bereitstellungen empfaengt.

    SEC-11c (R4) — der Kern des Race: `receiver.connect(...)` ist zurueck,
    sobald der Engine.IO-Handshake steht. Der `connect`-Handler des Servers
    (der `enter_room` aufruft) laeuft danach und kann noch ausstehen. Ein
    `sleep()` waere eine Vermutung mit Zeitlimit, ein Handshake-Ping keine
    Aussage ueber den Raum.

    Deshalb wird GEMESSEN statt gewartet: der Server publiziert eine SONDE
    ueber den ECHTEN Redis-Weg (`publish_realtime`, hier im Thread — es laeuft
    keine Event-Loop, also nimmt `publish_realtime` den synchronen Zweig).
    Kommt sie im Client an, sitzt er im Raum `user:Administrator` und die
    eigentliche Nachricht kann nicht mehr an einen leeren Raum gehen.

    Die Sonde hat einen EIGENEN Ereignisnamen (`sec11c_sonde`), damit sie die
    Pruefung `messages == [{"status": "done"}]` nicht verfaelscht. Wiederholt
    wird, weil die erste Sonde genau das Fenster trifft, das geschlossen
    werden soll.
    """
    import time

    empfangen = threading.Event()

    def _sonde(_daten):
        empfangen.set()

    receiver.on("sec11c_sonde", _sonde)
    try:
        ende = time.monotonic() + grenze
        while time.monotonic() < ende:
            realtime.publish_realtime(
                "sec11c_sonde", {"bereit": True}, user="Administrator")
            if empfangen.wait(1.5):
                return
            time.sleep(0.1)
        raise AssertionError(
            f"Socket-Client nach {grenze} s nicht empfangsbereit — die Sonde "
            "kam nie an; Realtime-Zustellung pruefen, nicht den Test aufweichen")
    finally:
        try:
            receiver.handlers["/"].pop("sec11c_sonde", None)
        except Exception:  # noqa: BLE001 — Aufraeumen darf nie werfen
            pass
