"""B3 regression tests: guest defaults, trusted uploads and authenticated files."""
import io
from pathlib import Path

import pytest

from diakronos_app.frappe_compat import registry
from diakronos_app.models.core import FileModel

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 24


@pytest.fixture
def files_dir(tmp_path, monkeypatch):
    from diakronos_app.settings import settings
    monkeypatch.setattr(settings, 'files_dir', str(tmp_path / 'files'))
    return tmp_path / 'files'


def upload(client, content=PNG, name='zz-b-test.png', mime='image/png', **data):
    return client.post('/api/method/upload_file',
                       files={'file': (name, io.BytesIO(content), mime)}, data=data)


def test_guest_default_is_false():
    def local_probe():
        return 'should never run for a guest'
    registry.whitelist()(local_probe)
    try:
        assert registry.options_for(local_probe)['allow_guest'] is False
    finally:
        for key, fn in list(registry._REGISTRY.items()):
            if fn is local_probe:
                registry._REGISTRY.pop(key)
        registry._OPTIONS.pop(id(local_probe), None)


def test_guest_ping_is_denied(guest_client):
    assert guest_client.get('/api/method/ping').status_code == 401


def test_guest_rejected_before_body_parsing(guest_client, monkeypatch):
    from diakronos_app.frappe_compat import router
    async def must_not_parse(request):
        pytest.fail('Unauthenticated multipart body was parsed')
    monkeypatch.setattr(router, '_read_args', must_not_parse)
    assert guest_client.post('/api/method/upload_file', content=b'large arbitrary body').status_code == 401


def test_guest_upload_is_denied(guest_client, files_dir):
    assert upload(guest_client).status_code == 401
    assert not files_dir.exists()


def test_guest_logout_stays_open(guest_client):
    assert guest_client.post('/api/method/logout').status_code == 200


@pytest.mark.parametrize('name,mime,content', [
    ('x.svg', 'image/svg+xml', b'<svg onload="alert(1)"/>'),
    ('x.png', 'image/png', b'<?php echo 1; ?>'),
    ('x.png', 'image/png', b'<html><script>alert(1)</script></html>'),
    ('x.jpg', 'image/jpeg', PNG),
    ('x.txt', 'text/plain', b'<svg onload="alert(1)"/>'),
    ('x.zip', 'application/zip', b'not a zip'),
])
def test_reject_untrusted_content(client, files_dir, name, mime, content):
    assert upload(client, content, name, mime).status_code == 417
    assert not files_dir.exists()


@pytest.mark.parametrize('name,mime,content', [
    ('x.png', 'image/png', PNG),
    ('x.jpg', 'image/jpeg', b'\xff\xd8\xff\xe0JPEG'),
    ('x.gif', 'image/gif', b'GIF89aGIF'),
    ('x.webp', 'image/webp', b'RIFF\x00\x00\x00\x00WEBP'),
    ('x.pdf', 'application/pdf', b'%PDF-1.4 test'),
])
def test_valid_upload_served_with_trusted_type(client, files_dir, name, mime, content):
    r = upload(client, content, name, mime)
    assert r.status_code == 200, r.text
    response = client.get(r.json()['message']['file_url'])
    assert response.status_code == 200
    assert response.content == content
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['content-type'].split(';')[0] == mime
    assert response.headers['content-disposition'].startswith('inline' if mime.startswith('image/') else 'attachment')


@pytest.mark.parametrize('character', ['ä', '€', '😀'])
def test_text_upload_download_across_sniff_boundary(client, files_dir, character):
    content = b'a' * 4095 + character.encode('utf-8') + b'tail'
    response = upload(client, content, 'zz-b-boundary.txt', 'text/plain')
    assert response.status_code == 200, response.text
    downloaded = client.get(response.json()['message']['file_url'])
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == content
    assert downloaded.headers['content-disposition'].startswith('attachment')
    assert downloaded.headers['x-content-type-options'] == 'nosniff'


@pytest.mark.parametrize('suffix', [b'\xff', b'<script>alert(1)</script>', b'\x00'])
def test_download_rejects_unsafe_text_beyond_sniff_boundary(client, files_dir, suffix):
    response = upload(client, b'plain text', 'zz-b-tampered.txt', 'text/plain')
    assert response.status_code == 200
    url = response.json()['message']['file_url']
    (files_dir / url.rsplit('/', 1)[1]).write_bytes(b'a' * 4096 + suffix)
    assert client.get(url).status_code == 403


def test_download_text_validation_is_size_bounded(client, files_dir, monkeypatch):
    from diakronos_app.settings import settings
    response = upload(client, b'plain text', 'zz-b-oversized.txt', 'text/plain')
    assert response.status_code == 200
    url = response.json()['message']['file_url']
    monkeypatch.setattr(settings, 'max_upload_bytes', 4096)
    (files_dir / url.rsplit('/', 1)[1]).write_bytes(b'a' * 4097)
    assert client.get(url).status_code == 403


def test_private_file_acl(client, files_dir, set_user):
    set_user('zz-b-owner@example.invalid')
    r = upload(client)
    assert r.status_code == 200
    url = r.json()['message']['file_url']
    assert client.get(url).status_code == 200
    assert client.get('/private/files/' + url.rsplit('/', 1)[1]).status_code == 200
    set_user('zz-b-other@example.invalid')
    assert client.get(url).status_code == 403
    set_user('Administrator')
    assert client.get(url).status_code == 200
    set_user('Guest')
    assert client.get(url).status_code == 403


def test_public_file_still_requires_login(client, files_dir, set_user):
    r = upload(client, is_private='0')
    url = r.json()['message']['file_url']
    set_user('zz-b-other@example.invalid')
    assert client.get(url).status_code == 200
    set_user('Guest')
    assert client.get(url).status_code == 403


@pytest.mark.parametrize('path', ['../outside.png', '%2e%2e%2foutside.png', '..%5coutside.png',
                                  '%252e%252e%252foutside.png', 'a/b.png'])
def test_file_traversal_denied(client, files_dir, path):
    files_dir.mkdir()
    (files_dir.parent / 'outside.png').write_bytes(PNG)
    r = client.get('/files/' + path)
    assert r.status_code in (403, 404)
    assert r.content != PNG


def test_file_symlink_denied(client, files_dir, patched_db):
    files_dir.mkdir()
    outside = files_dir.parent / 'outside.png'
    outside.write_bytes(PNG)
    (files_dir / 'link.png').symlink_to(outside)
    with patched_db() as db:
        db.add(FileModel(name='zz-b-link', file_name='link.png', file_url='/files/link.png', owner='Administrator', is_private=True))
        db.commit()
    assert client.get('/files/link.png').status_code == 404


def test_oversize_read_is_bounded(client, files_dir, monkeypatch):
    from diakronos_app.api.frappe_core import upload_file
    from diakronos_app.settings import settings
    from diakronos_app.frappe_compat.exceptions import ValidationError
    monkeypatch.setattr(settings, 'max_upload_bytes', 4)
    class Bounded(io.BytesIO):
        def read(self, size=-1):
            assert size == 5
            return super().read(size)
    class Upload:
        file = Bounded(b'0123456789')
        filename = 'large.txt'
        content_type = 'text/plain'
        def read(self, size=-1):
            return self.file.read(size)
    with pytest.raises(ValidationError, match='gross'):
        upload_file(file=Upload())


def test_profile_rejects_unowned_url(client, seed_mitglieder, set_user):
    from diakronos_app.models.diakonos import Mitglied
    m = seed_mitglieder.get(Mitglied, 'M-0001')
    m.user = 'Administrator'
    seed_mitglieder.commit()
    r = client.post('/api/method/profile.update_profile_picture', json={'file_url': '/files/foreign.png'})
    assert r.status_code == 403
    seed_mitglieder.expire_all()
    assert seed_mitglieder.get(Mitglied, 'M-0001').foto is None


def test_unknown_privacy_is_rejected(client, files_dir):
    assert upload(client, is_private='garbage').status_code == 417
    assert not files_dir.exists()


def test_direct_guest_upload_is_denied(patched_db, files_dir, set_user):
    from diakronos_app.api.frappe_core import upload_file
    from diakronos_app.frappe_compat.exceptions import PermissionError
    set_user('Guest')
    with pytest.raises(PermissionError):
        upload_file(file=PNG, filename='x.png')
    assert not files_dir.exists()


def test_attachment_cannot_be_forged(client, files_dir, set_user):
    set_user('zz-b-other@example.invalid')
    r = upload(client, doctype='Mitglied', docname='nonexistent')
    assert r.status_code == 403
    assert not files_dir.exists()


def test_private_attachment_read_permission(client, files_dir, patched_db, seed_mitglieder, set_user):
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.core import User
    with patched_db() as db:
        db.add(User(name='zz-b-viewer@example.invalid', email='anna@example.org', enabled=True))
        db.commit()
    # Administrator uploads to an existing member; the other user can see it.
    r = upload(client, doctype='Mitglied', docname='M-0001')
    assert r.status_code == 200, r.text
    set_user('zz-b-viewer@example.invalid')
    assert client.get(r.json()['message']['file_url']).status_code == 200
    # Permission is rechecked; a now-unlinked user must lose access.
    with patched_db() as db:
        db.get(User, 'zz-b-viewer@example.invalid').email = 'other@example.org'
        db.commit()
    assert client.get(r.json()['message']['file_url']).status_code == 403
