"""P0-4/UXD-R2: Registrierungslinks ohne Token nachtragen.

Revision ID: p04_reglink_token
Revises: bf1c_moderation_widget
Create Date: 2026-10-16

Befund (Nachtpruefung UXD-R2): ``create_link`` schrieb weder ``slug`` noch
``link_anzeige`` noch ``anmeldungen_count``. Jeder NEU angelegte Link war
damit unbrauchbar — ``validate_token`` sucht ``{"slug": token}`` und fand
nichts; die Oberflaeche zeigte eine leere Adresse, „Kopieren" kopierte
nichts.

Diese Migration traegt die fehlenden Werte fuer BESTEHENDE Zeilen nach:
  * ``slug``            — Zufallstoken (nur wenn leer)
  * ``anmeldungen_count`` — 0 (nur wenn NULL)
  * ``link_anzeige``    — ``/diakonos/<seite>?token=<slug>``
    (auch fuer Altzeilen, deren Anzeige noch der relative Frappe-Pfad
    ``/registrierung?token=…`` ist — UXD-R3).

Idempotent: laeuft auf frischer UND auf bestehender DB sauber. Zeilen mit
bereits gesetztem Slug behalten ihn. Fuer die Anzeige wird nur dann neu
gebildet, wenn der gespeicherte Wert nicht schon die erwartete Form hat.
``downgrade`` setzt die nachgetragenen Werte nicht zurueck (der Verlust des
Tokens waere eine Verschlechterung); es ist bewusst ein No-op.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p04_reglink_token"
down_revision: Union[str, None] = "bf1c_moderation_widget"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "registrierungslink"


def _spalten(bind) -> set[str]:
    insp = sa.inspect(bind)
    if not insp.has_table(TABELLE):
        return set()
    return {c["name"] for c in insp.get_columns(TABELLE)}


def _token() -> str:
    import secrets

    return secrets.token_urlsafe(10)


def _seite(typ) -> str:
    return "gast" if str(typ or "") == "Gast-Anmeldung" else "registrierung"


def _anzeige(typ, slug: str) -> str:
    return f"/diakonos/{_seite(typ)}?token={slug}"


def upgrade() -> None:
    bind = op.get_bind()
    spalten = _spalten(bind)
    if not spalten or "slug" not in spalten:
        return

    zeilen = bind.execute(
        sa.text(
            f"SELECT name, typ, slug, link_anzeige, anmeldungen_count FROM {TABELLE}"
        )
    ).fetchall()

    for name, typ, slug, anzeige, count in zeilen:
        neuer_slug = (slug or "").strip() or _token()
        werte: dict[str, object] = {}
        if neuer_slug != (slug or ""):
            werte["slug"] = neuer_slug
        if count is None:
            werte["anmeldungen_count"] = 0
        erwartet = _anzeige(typ, neuer_slug)
        if (anzeige or "") != erwartet:
            werte["link_anzeige"] = erwartet
        if not werte:
            continue
        setz = ", ".join(f"{k} = :{k}" for k in werte)
        bind.execute(
            sa.text(f"UPDATE {TABELLE} SET {setz} WHERE name = :name"),
            {**werte, "name": name},
        )


def downgrade() -> None:
    """Kein Rueckweg.

    Den nachgetragenen Token wieder zu entfernen wuerde benutzbare Links
    zerstoeren (genau der Zustand aus UXD-R2). Die Migration ist damit
    einseitig — das ist die Absicht, nicht eine Luecke.
    """
