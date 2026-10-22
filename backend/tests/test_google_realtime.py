"""Authenticated Socket.IO delivery, including progress from RQ processes."""
import asyncio
import threading

import httpx
import pytest
import socketio

from diakronos_app.frappe_compat import realtime, sitzungen


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
    import os
    import subprocess
    import time
    import uvicorn
    import socket

    got = threading.Event()
    messages = []
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    _, socket_app = realtime.create_socket_server()
    server = uvicorn.Server(uvicorn.Config(socket_app, host="127.0.0.1", port=port, log_level="warning", timeout_graceful_shutdown=2))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    receiver = socketio.Client()
    @receiver.on("gcal_import_progress")
    def receive(data):
        messages.append(data)
        got.set()
    try:
        for _ in range(200):
            if server.started:
                break
            time.sleep(.02)
        assert server.started
        receiver.connect(f"http://127.0.0.1:{port}", headers={"Cookie": "sid=" + client.cookies.get("sid")}, transports=["polling"])
        subprocess.run(["python", "-c", "from diakronos_app.frappe_compat.realtime import publish_realtime; publish_realtime('gcal_import_progress', {'status':'done'}, user='Administrator')"], check=True, env=os.environ.copy())
        assert got.wait(5), "Worker process publication not received by ASGI client"
        assert messages == [{"status": "done"}]
    finally:
        receiver.disconnect()
        server.should_exit = True
        thread.join(5)
