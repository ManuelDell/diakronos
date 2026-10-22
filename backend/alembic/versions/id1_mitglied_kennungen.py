"""ID-1: Mitglied-Kennungen vom Klarnamen auf zufällige IDs umschlüsseln.

Revision ID: id1_mitglied_kennungen
Revises: dsgvo2a_antrag_ablehnung
Create Date: 2026-10-21

DAS PROBLEM
-----------
Im Betrieb ist `mitglied.name` bei 24 von 25 Mitgliedern der KLARNAME
(„Mira Blank“, Altbestand aus Frappe). Die Kennung steht in API-Antworten,
URLs, Protokollen und JSON-Werten — der Name sickert damit überall durch, auch
dort, wo die Anzeige gekürzt ist. Neue Mitglieder bekommen seit P1b eine
zufällige Kennung (`frappe_compat/api_helpers.py::_new_name` ->
`str(uuid.uuid4())[:10]`, also 10 Hex-Zeichen MIT Bindestrichen).

WAS DIESE MIGRATION TUT
-----------------------
Jedes Mitglied, dessen `name` nicht diesem Muster entspricht, bekommt eine
neue Zufallskennung im SELBEN Format. Alle Verweise werden in DERSELBEN
Transaktion umgehängt:

* **Fremdschlüssel** auf `mitglied.name` — die Liste kommt aus `pg_constraint`,
  nicht aus einer Handliste (Wiederverwendung der Mechanik aus DSGVO-1b,
  `dsgvo_anonymisierung.verweise()`): `mitglied.ehepartner`/`elternteil`,
  `gruppenmitgliedschaft`, `dienstplan*`, `rollenbesetzung`,
  `element_mitarbeiter`, `pr_abwesenheit`, `pr_plan.verantwortlich`,
  `dsgvo_einwilligung`, `loeschantrag` (Nachweis, Art. 17/7), `anmeldung`,
  `bug_report`, `sicherer_anhang`, `mitglied_beziehung.beziehung_zu`, …
* **Kindtabellen und Verweisspalten OHNE Fremdschlüssel** (`KIND_SPALTEN`):
  `mitglied_beziehung.parent` und `mitglied_bereich.parent` (jeweils nur bei
  `parenttype = 'Mitglied'`), `dynamic_link.link_name` (nur bei
  `link_doctype = 'Mitglied'`). Sie tragen die Kennung des ELTERN-Dokuments
  bzw. des Verweisziels, stehen aber in keinem `pg_constraint` — Frappe legt
  Kindtabellen ohne FK an (R-ID-1, Blocker B1: 3 Beziehungszeilen verwaisten).
* **Spalten ohne Fremdschlüssel** (`WERT_SPALTEN`):
  `pr_merkmal_wert.ziel_id`, `audit_log.target_name` (nur bei
  `target_doctype = 'Mitglied'`), `notification_log.document_name` (nur bei
  `document_type = 'Mitglied'`), `file.attached_to_name` (nur bei
  `attached_to_doctype = 'Mitglied'`) — ganze Werte; `pr_eintrag.wert`,
  `pr_verlauf.vorher`/`nachher`, `pr_plan.veroeffentlichter_stand`,
  `pr_sammlung_eintrag.daten`, `dm_befund.*` (JSON).
  Verglichen wird der GANZE Wert bzw. der JSON-Wert — keine Teilstring-Suche
  (die Lehre aus R-DSGVO-1/K2).

ABbildungstabelle `id1_mitglied_kennung`
----------------------------------------
`alt` -> `neu`, angelegt in `upgrade`, gefüllt in derselben Transaktion.

* `downgrade` schreibt den `name` über die Abbildung ZURÜCK und räumt danach
  die Tabelle auf: die Rückkehr ist nur EINE Stufe tief und braucht die
  Abbildung danach nicht mehr. Bliebe sie stehen, läge die alte
  Klarname-Kennung dauerhaft in einer Tabelle — genau das, was diese Karte
  beseitigt. (Eine spätere, eigene Migration kann die Tabelle in einem
  Wartungsfenster entfernen; ein `downgrade` über diese Stufe hinaus ist dann
  bewusst nicht mehr möglich — die Klarnamen wären nicht mehr herstellbar.
  Das ist richtig so: nach ID-1 IST der Klarname nicht mehr die Kennung.)
* Abgelehnt wird der Rückweg, sobald ein `neu` inzwischen anderweitig belegt
  ist (jemand hat die alte Klarname-Kennung neu angelegt): dann bricht die
  Migration mit einer verständlichen Meldung ab, statt eine Zeile zu
  überschreiben.

IDEMPOTENZ
----------
Ein zweiter Lauf (der Entrypoint migriert bei JEDEM Start, Lehre P3-2) darf
nichts mehr ändern: die Auswahl greift nur bei Zeilen, deren `name` NICHT dem
Muster neuer Kennungen entspricht (`^[0-9a-f]{8}-[0-9a-f]$`, z. B.
`1a2b3c4d-5`). Auf einer frisch migrierten DB ist die Auswahl leer.

WAS BEWUSST NICHT ANGEFASST WIRD
--------------------------------
* `mitglied.email` bleibt WERTGLEICH — auch der Alt-Platzhalter `-` (O2:
  keine Datenbereinigung). Nur der Umweg über den UNIQUE-Index
  (`uq_mitglied_email_normalisiert`) schreibt ihn zwischenzeitlich auf NULL
  und setzt ihn unmittelbar danach unverändert zurück.
* `user.name` (Konto) ist die E-Mail. `mitglied.user` bleibt unverändert.
* `mitglied.ancestor_path` (Gruppenpfade, `"/Diakonie/|/Musik/"`) und
  `mitglied.adressbuch_sichtbarkeit` (JSON: Konten) sowie
  `ressourcen_buchung.gebucht_von(_name)` tragen im Betrieb KEINE
  Mitglied-Kennung (am Dump geprüft) — sie bleiben, und I3 belegt das mit
  Zahlen.
* Kalender: CalDAV ist LESEND, `UID:{element.name}@diakronos`
  (`caldav/ical.py`) hängt am Termin, nicht am Mitglied.
"""

from typing import Sequence, Union

import uuid

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "id1_mitglied_kennungen"
down_revision: Union[str, None] = "dsgvo2a_antrag_ablehnung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ABBILDUNG = "id1_mitglied_kennung"

#: Nachweiszeilen, deren SCHLÜSSEL den Klarnamen trägt (N3, R-ID-1).
#: `(tabelle, spalte, praefixe)`: im Betrieb heißt eine
#: Einwilligungs-Nachweiszeile „DSGVO-Mira Blank-0002“ bzw.
#: „EINW-Mira Blank-0293“ — am Dump geprüft, 9 Zeilen (8 `DSGVO-`, 1 `EINW-`).
#: Der Name wanderte damit in eine Tabelle, die eine Löschung ausdrücklich
#: überlebt. Verweise auf den Schlüssel gibt es NICHT (0 Fremdschlüssel auf
#: `dsgvo_einwilligung`, am Betrieb über `pg_constraint` geprüft) — es genügt,
#: die Zeile umzubenennen; der Bezug zur Person ist die Spalte `mitglied`.
EINWILLIGUNG_SPALTEN: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("dsgvo_einwilligung", "name", ("DSGVO-", "EINW-")),
)

#: Spalten ohne Fremdschlüssel, die Mitglied-Kennungen als WERT tragen.
#: Art `wert` = ganze Spalte, `json` = JSON-Baum (jeder Wert gleich der alten
#: Kennung wird ersetzt), `json_text` = dasselbe, aber als TEXT-Ersatz auf den
#: exakten JSON-String (Spalten vom Typ `json`, NICHT `jsonb` — s. N5).
#: Quelle: `dsgvo_anonymisierung.WERT_SPALTEN` (DSGVO-1b, dort gegen
#: `pg_constraint` und die Betriebs-DB geprüft), ergänzt um den Doctype-Filter
#: aus R-ID-1/N1.
#:
#: DAS VIERTE FELD IST DER DOCTYPE-FILTER: `(spalte_fuer_den_doctype, wert)`.
#: Ohne ihn würde eine Kennung wie `max@x.org` (O1-Kandidat) auch dort
#: umgeschrieben, wo sie einen ANDEREN DocType bezeichnet — `audit_log`
#: enthält z. B. `target_name = 'Test-Policy DSGVO'` zu `target_doctype =
#: 'Audit Policy'`. Ein Konto-Name als Ziel eines Fremd-DocTypes bleibt
#: unangetastet.
WERT_SPALTEN: tuple[tuple[str, str, str, str | None], ...] = (
    ("pr_merkmal_wert", "ziel_id", "wert", None),
    ("audit_log", "target_name", "wert", "target_doctype"),
    ("notification_log", "document_name", "wert", "document_type"),
    ("file", "attached_to_name", "wert", "attached_to_doctype"),
    ("pr_eintrag", "wert", "json", None),
    ("pr_verlauf", "vorher", "json", None),
    ("pr_verlauf", "nachher", "json", None),
    ("pr_plan", "veroeffentlichter_stand", "json", None),
    ("pr_sammlung_eintrag", "daten", "json", None),
    ("dm_befund", "fehlerumfeld", "json_text", None),
    ("dm_befund", "element", "json_text", None),
    ("dm_befund", "bilder", "json_text", None),
)

#: Wert des Doctype-Feldes, an dem ein Mitglied-Bezug erkannt wird.
MITGLIED = "Mitglied"

#: KIND- UND VERWEISSPALTEN OHNE FREMDschlüssel — die Lücke aus R-ID-1/B1.
#: `(tabelle, spalte, doctype_spalte)`: umgehängt wird nur, wo die
#: Doctype-Spalte `'Mitglied'` sagt. Frappe legt Kindtabellen (`parent`)
#: grundsätzlich ohne Fremdschlüssel an, `dynamic_link` ist ein generischer
#: Verweis — `pg_constraint` kennt sie deshalb NICHT, sie müssen benannt sein.
#:
#: Nachgeprüft über `pg_catalog` (alle Spalten mit `parent`/`parenttype` über
#: alle Tabellen, Schnittmenge mit den Tabellen, in denen eine
#: Mitglied-Kennung stehen kann) und über die Modelle
#: (`models/diakonos.py`: `MitgliedBereich`, `MitgliedBeziehung`;
#: `models/core.py`: `DynamicLinkModel`). Weitere Kandidaten gibt es nicht:
#: `element_mitarbeiter`/`dienstplan_*` tragen ihre Kennung in einer eigenen
#: Spalte MIT Fremdschlüssel, `reference_doctype`/`referenz_doctype`-Paare
#: ohne Mitgliedsbezug bleiben außen vor.
KIND_SPALTEN: tuple[tuple[str, str, str], ...] = (
    ("mitglied_beziehung", "parent", "parenttype"),
    ("mitglied_bereich", "parent", "parenttype"),
    ("dynamic_link", "link_name", "link_doctype"),
)


#: Alte Mitglied-Kennung -> neue. Wird VOR dem Umschlüsseln gefüllt (die
#: JSON-Spalten brauchen die Abbildung ganz).
ALT_NEU = "alt_neu"

#: Spalten der `mitglied`-Tabelle, die NOT NULL sind und KEINEN Vorgabewert
#: tragen: sie brauchen beim Kopieren einen Wert. Aus `information_schema`
#: (Stand ID-1) — eine künftige Pflichtspalte ohne Vorgabe würde das Kopieren
#: sonst mit „null value in column ... violates not-null constraint“ abbrechen.
_OHNE_VORGABE = frozenset({"docstatus", "idx"})


def _standardwert(spalte: str) -> str:
    """Ersatzwert für eine Pflichtspalte ohne Vorgabewert."""
    return {"docstatus": "0", "idx": "0"}.get(spalte, "0")


def _kennung(bind) -> str:
    """Neue Zufallskennung im Format von `_new_name` — und sicher frei.

    Dieselbe Form wie `frappe_compat/api_helpers.py::_new_name`
    (``str(uuid.uuid4())[:10]``): 8 Zeichen, Bindestrich, 1 Zeichen
    („8+1+1 = 10“ — so verteilt `uuid4()` seine Striche).
    """
    while True:
        kandidat = str(uuid.uuid4())[:10]
        belegt = bind.execute(
            sa.text("SELECT 1 FROM mitglied WHERE name = :n"), {"n": kandidat}
        ).first()
        if belegt is None:
            return kandidat



def _fk_spalten(bind) -> list[tuple[str, str, bool, str]]:
    """Alle Fremdschlüssel-Spalten auf `mitglied.name` — aus `pg_constraint`.

    Liest die DATENBANK, nicht die Modelle: eine Spalte, die nur im Betrieb
    existiert (Overlay aus der Frappe-Historie), muss genauso umgehängt werden.
    Rückgabe: ``(tabelle, spalte, nullable, delete_regel)``.
    """
    zeilen = bind.execute(
        sa.text(
            "SELECT c.conrelid::regclass::text AS tabelle, a.attname AS spalte, "
            "       a.attnotnull AS notnull, c.confdeltype AS regel "
            "FROM pg_constraint c "
            "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey) "
            "WHERE c.contype = 'f' AND c.confrelid = 'mitglied'::regclass "
            "ORDER BY 1, 2"
        )
    ).mappings().all()
    return [
        (str(z["tabelle"]), str(z["spalte"]), not bool(z["notnull"]), str(z["regel"]))
        for z in zeilen
    ]


def _kandidaten(bind) -> list[str]:
    """Mitglieder, deren Kennung NICHT dem Muster neuer Kennungen entspricht.

    Kandidatenregel (Operator-Entscheidung O1): umgeschlüsselt wird JEDES
    Mitglied, dessen `name` nicht exakt ``^[0-9a-f]{8}-[0-9a-f]$`` erfüllt —
    also dem Muster, das `_new_name` (``str(uuid4())[:10]``) erzeugt. Keine
    Namens- oder Leerzeichen-Heuristik: „MaxMuster“ und „max@x.org“ tragen
    ebenso einen Klarnamen wie „Anna Beispiel“, „1a2b3c4d-5“ dagegen ist
    bereits zufällig und bleibt.

    Auf einer frisch migrierten DB ist die Auswahl leer (Idempotenz: der
    Entrypoint migriert bei jedem Start).
    """
    return list(
        bind.execute(
            sa.text(
                "SELECT name FROM mitglied WHERE name IS NULL OR "
                "name !~ '^[0-9a-f]{8}-[0-9a-f]$' ORDER BY name"
            )
        ).scalars().all()
    )



def _abbildung_anlegen(bind) -> None:
    # `now()` ist PostgreSQL; SQLite kennt es nicht (ID-1e-Tests laufen auf
    # SQLite ohne Alembic-Kontext). `CURRENT_TIMESTAMP` gilt in beiden.
    bind.execute(
        sa.text(
            f"CREATE TABLE IF NOT EXISTS {ABBILDUNG} ("
            " alt VARCHAR(140) PRIMARY KEY,"
            " neu VARCHAR(140) NOT NULL UNIQUE,"
            " umgeschluesselt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    _abbildung_anlegen(bind)
    # Laufzeit-Tabelle aus einem abgebrochenen Lauf (P3-2: der Entrypoint
    # migriert bei jedem Start) — `CREATE TEMP TABLE` bricht sonst ab.
    bind.execute(sa.text(f"DROP TABLE IF EXISTS {ALT_NEU}"))

    alte = _kandidaten(bind)
    if not alte:
        # N3: Auch ohne offene Mitglieder kann eine Nachweiszeile den Namen
        # tragen (ein Vorlauf hat die Person schon umgeschlüsselt) — die
        # Abbildung hat dann ihren Stand und der Schritt läuft trotzdem.
        _einwilligungen_umbenennen(bind)
        return

    # 1) Abbildung füllen — in DIESER Transaktion, damit die JSON-Spalten und
    #    ein `downgrade` dieselbe Wahrheit sehen.
    for alt in alte:
        bind.execute(
            sa.text(f"INSERT INTO {ABBILDUNG} (alt, neu) VALUES (:a, :n) "
                    "ON CONFLICT (alt) DO NOTHING"),
            {"a": alt, "n": _kennung(bind)},
        )
    bind.execute(
        sa.text(
            f"CREATE TEMP TABLE IF NOT EXISTS {ALT_NEU} ON COMMIT DROP AS "
            f"SELECT alt, neu FROM {ABBILDUNG}"
        )
    )

    # 2) Die NEUEN Zeilen entstehen NEBEN den alten: `mitglied` hat zwei
    #    Selbstbezüge (ehepartner/elternteil) — deren Verweise lassen sich erst
    #    umhängen, wenn beide Zeilen existieren. Die Zeile wird VOLLSTÄNDIG
    #    kopiert (nur `name` wechselt); die Spaltenliste kommt aus
    #    `information_schema`, damit auch eine Spalte, die nur im Betrieb
    #    existiert, mitkommt — inklusive NOT-NULL-Spalten ohne Vorgabewert.
    #
    #    Adressen: `uq_mitglied_email_normalisiert` ist ein UNIQUE-Index über
    #    `lower(trim(email))` — solange die alte Zeile steht, darf die neue
    #    dieselbe Adresse nicht tragen. Die neue Zeile entsteht deshalb OHNE
    #    Adresse (Spalte `email` -> NULL, `NULL` verletzt den Index nicht) und
    #    erhält sie in Schritt 2e unverändert, nachdem die alte Zeile gefallen
    #    ist. Keine Bereinigung: der Alt-Platzhalter `-` bleibt `-` (O2).
    spalten = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = 'mitglied' "
            "ORDER BY ordinal_position"
        )
    ).scalars().all()
    _mitglieder_umhaengen(bind, None, spalten=spalten)


def _mitglieder_umhaengen(bind, abbildung: dict | None = None,
                          *, spalten: list[str] | None = None,
                          fks: list[tuple[str, str, bool, str]] | None = None,
                          json_pfade: bool = True) -> None:
    """Alle Mitglieder der Abbildung umschlüsseln (Schritt 2 aus `upgrade`).

    `abbildung` ist die Zuordnung alt->neu (Vorgabe: die Tabelle `ABBILDUNG`
    samt temporärer Kopie `ALT_NEU`). `spalten` sind die Spalten von
    `mitglied`, `fks` die Fremdschlüssel (Vorgabe: aus `information_schema`
    bzw. `pg_constraint` gelesen; ohne PostgreSQL muss beides herein).
    ``json_pfade=False`` lässt die JSON-Spalten aus (sie lesen ihren
    Primärschlüssel aus `pg_index`, s. `_json_umhaengen`).
    Eigene Funktion, damit der Schritt auch ohne Alembic-Kontext prüfbar ist
    (ID-1e).
    """
    if abbildung is None:
        _abbildung_anlegen(bind)
        bind.execute(
            sa.text(
                f"CREATE TEMP TABLE IF NOT EXISTS {ALT_NEU} ON COMMIT DROP AS "
                f"SELECT alt, neu FROM {ABBILDUNG}"
            )
        )
        paare = bind.execute(sa.text(f"SELECT alt, neu FROM {ALT_NEU} ORDER BY alt")).all()
    else:
        # Ohne Alembic-Kontext (Tests, ID-1e): die Zuordnung kommt herein und
        # steht danach in der Abbildungstabelle — dort, wo der Rückweg sie
        # sucht (`downgrade` liest sie ebenfalls von dort).
        paare = list(abbildung.items())
        _abbildung_anlegen(bind)
        for alt, neu in paare:
            bind.execute(
                sa.text(f"DELETE FROM {ABBILDUNG} WHERE alt = :a"), {"a": alt},
            )
            bind.execute(
                sa.text(f"INSERT INTO {ABBILDUNG} (alt, neu) VALUES (:a, :n)"),
                {"a": alt, "n": neu},
            )
    if spalten is None:
        spalten = bind.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'mitglied' "
                "ORDER BY ordinal_position"
            )
        ).scalars().all()
    kopieren = [s for s in spalten if s != "name"]
    ziel = ", ".join(f'"{s}"' for s in kopieren)
    auswahl = ", ".join(
        f'COALESCE(m."{s}", {_standardwert(s)})' if s in _OHNE_VORGABE
        else "NULL" if s == "email"                     # erst nach dem Löschen
        else f'm."{s}"'
        for s in kopieren
    )
    fks = _fk_spalten(bind) if fks is None else fks

    for alt, neu in paare:
        # 2a) Die Adresse der Person VOR dem Kopieren merken (die neue Zeile
        #     entsteht ohne Adresse, s. o.).
        fremd = bind.execute(
            sa.text('SELECT "email" FROM mitglied WHERE name = :a'), {"a": alt}
        ).scalar()
        # 2b) Neue Zeile anlegen — Kopie der alten, unter der Zufallskennung.
        bind.execute(
            sa.text(
                f"INSERT INTO mitglied (name, {ziel}) "
                f"SELECT :neu, {auswahl} FROM mitglied m WHERE m.name = :alt"
            ),
            {"neu": neu, "alt": alt},
        )
        # 2b) Kind- und Verweisspalten ohne FK (B1): nur wo der DocType
        #     Mitglied ist.
        _kind_umhaengen(bind, alt, neu)
        # 2c) Fremdschlüssel auf `mitglied.name` umhängen.
        for tabelle, spalte, _nullable, _regel in fks:
            bind.execute(
                sa.text(f'UPDATE "{tabelle}" SET "{spalte}" = :n WHERE "{spalte}" = :a'),
                {"n": neu, "a": alt},
            )
        # 2c) Wert-Spalten ohne FK — mit Doctype-Filter (N1).
        for eintrag in WERT_SPALTEN:
            tabelle, spalte, art, doctype_spalte = eintrag
            if art != "wert":
                continue
            bedingung = (
                f' AND "{doctype_spalte}" = :d' if doctype_spalte else ""
            )
            bind.execute(
                sa.text(
                    f'UPDATE "{tabelle}" SET "{spalte}" = :n '
                    f'WHERE "{spalte}" = :a{bedingung}'
                ),
                {"n": neu, "a": alt, "d": MITGLIED},
            )
        # 2d) JSON-Spalten: jeder Wert, der GENAU die alte Kennung ist.
        for tabelle, spalte, art, _doctype in WERT_SPALTEN:
            if not json_pfade or art not in ("json", "json_text"):
                continue
            _json_umhaengen(bind, tabelle, spalte, {alt: neu},
                            als_text=(art == "json_text"))
        # 2e) Alte Zeile löschen — erst jetzt, sonst zeigt ein Verweis ins Leere.
        bind.execute(sa.text("DELETE FROM mitglied WHERE name = :a"), {"a": alt})
        # 2f) Die Adresse UNVERÄNDERT an die neue Zeile — jetzt ist sie frei.
        bind.execute(
            sa.text('UPDATE mitglied SET "email" = :e WHERE name = :n'),
            {"e": fremd, "n": neu},
        )

    # 3) Die Nachweiszeilen der Einwilligungen (N3): danach, nicht in der
    #    Schleife — sie brauchen die GANZE Abbildung.
    _einwilligungen_umbenennen(bind)


def _einwilligungen_umbenennen(bind, abbildung: dict | None = None,
                               *, zurueck: bool = False) -> None:
    """Schlüssel der Einwilligungs-Nachweise: Klarname -> Kennung (N3).

    Im Betrieb heißt der Nachweis der Einwilligung (Art. 7) „DSGVO-Mira
    Blank-0002“, der Widerruf dazu „EINW-Mira Blank-0293“: der Klarname steht
    damit im SCHLÜSSEL einer Tabelle, die eine Löschung ausdrücklich überlebt.
    Der Namensanteil wird die Kennung der Person, die laufende Nummer bleibt
    („DSGVO-<Kennung>-0002“). Beim Anlegen neuer Zeilen passiert das ohnehin
    nicht mehr (`frappe_compat/api_helpers._new_name` als Schlüssel).

    `abbildung` ist die Zuordnung alt->neu (Vorgabe: die gefüllte Tabelle
    `ABBILDUNG`). ``zurueck=True`` ist der Downgrade: die Zuordnung wird
    umgedreht übergeben.

    Umbenannt wird NUR, wo der Namensanteil GENAU eine Kennung aus der
    Abbildung ist — eine Zeile zu einer Person, deren Kennung sich nicht
    ändert, und eine Zeile ohne Mitglied bleiben, was sie sind. Verweise auf
    den Schlüssel gibt es nicht (s. `EINWILLIGUNG_SPALTEN`).
    """
    if abbildung is None:
        abbildung = dict(
            bind.execute(sa.text(f"SELECT alt, neu FROM {ABBILDUNG}")).all()
        )
    if not abbildung:
        return
    # Der längste Name zuerst: „Anna Beispiel“ darf „Anna“ nicht zerschneiden.
    namen = sorted(abbildung, key=len, reverse=True)
    for tabelle, spalte, praefixe in EINWILLIGUNG_SPALTEN:
        vorhanden = [
            str(z) for z in bind.execute(
                sa.text(f'SELECT "{spalte}" FROM "{tabelle}"')
            ).scalars().all()
            if z is not None
        ]
        for alt in vorhanden:
            neu = _einwilligung_neu(alt, abbildung, namen, praefixe)
            if neu is None or neu == alt:
                continue
            # Eindeutigkeit: der Zielschlüssel könnte schon stehen (eine Zeile
            # mit der Kennung, eine mit dem Namen). Dann Zusatz, wie in
            # `dsgvo_anonymisierung._eigene_schluessel_ersetzen`.
            kandidat, nr = neu, 0
            belegt = set(vorhanden)
            while kandidat in belegt and kandidat != alt:
                nr += 1
                kandidat = f"{neu}-{nr}"
            bind.execute(
                sa.text(f'UPDATE "{tabelle}" SET "{spalte}" = :neu WHERE "{spalte}" = :alt'),
                {"neu": kandidat, "alt": alt},
            )
            # Für die nächsten Zeilen ist der alte Schlüssel frei, der neue belegt.
            vorhanden = [kandidat if z == alt else z for z in vorhanden]


def _einwilligung_neu(alt: str, abbildung: dict, namen: list[str],
                      praefixe: tuple[str, ...]) -> str | None:
    """Neuer Schlüssel einer Nachweiszeile — ``None``, wenn keine Person passt.

    Aufbau im Betrieb: ``<Präfix><Name>-<laufende Nummer>``. Erkannt wird nur
    diese Form: das Präfix muss passen, die Nummer aus Ziffern bestehen, und
    der Namensanteil GENAU eine Kennung aus der Abbildung sein. Alles andere
    (Altzeilen ohne Namen, Zeilen zu fremden Dokumenten) bleibt unangetastet.
    """
    for praefix in praefixe:
        if not alt.startswith(praefix):
            continue
        rest = alt[len(praefix):]
        stamm, trenner, nummer = rest.rpartition("-")
        if not trenner or not nummer.isdigit():
            continue
        for name in namen:
            if stamm == name:
                return f"{praefix}{abbildung[name]}-{nummer}"
    return None


def _kind_umhaengen(bind, alt: str, neu: str) -> None:
    """Kind-/Verweisspalten ohne FK umhängen, nur bei DocType `Mitglied` (B1).

    `mitglied_beziehung.parent` und `mitglied_bereich.parent` tragen den
    ELTERN-Namen des Dokuments, `dynamic_link.link_name` das Verweisziel. Sie
    stehen in keinem `pg_constraint` (Frappe: Kindtabellen ohne FK), deshalb
    benennt `KIND_SPALTEN` sie. Die Doctype-Spalte schützt davor, eine
    Gleichnamigkeit mit einem anderen Dokumenttyp umzuschreiben.
    """
    for tabelle, spalte, doctype_spalte in KIND_SPALTEN:
        bind.execute(
            sa.text(
                f'UPDATE "{tabelle}" SET "{spalte}" = :n '
                f'WHERE "{spalte}" = :a AND "{doctype_spalte}" = :d'
            ),
            {"n": neu, "a": alt, "d": MITGLIED},
        )



def _json_umhaengen(bind, tabelle: str, spalte: str, abbildung: dict | None = None,
                    als_text: bool = False) -> None:
    """Ersetzt in einer JSON-Spalte jeden Wert, der GENAU eine alte Kennung ist.

    `abbildung` ist die Zuordnung alt->neu. Rückwärts (downgrade) wird sie
    zeilenweise hereingereicht — dort steht sie im Aufruf, nicht in der
    temporären Tabelle.

    `als_text=True` (N5): Spalten vom Typ `json` — NICHT `jsonb`, z. B.
    `dm_befund.*`. `cast(:w AS jsonb)` normalisiert Schlüsselreihenfolge und
    Leerraum; der Downgrade wäre danach nicht mehr byte-genau. Solche Spalten
    werden deshalb TEXTUELL behandelt: gelesen, in Python ersetzt, als String
    zurückgeschrieben — die Darstellung bleibt in allem anderen unberührt.

    `jsonb_each`/`jsonb_array_elements` wäre je Verschachtelungstiefe ein
    eigener Ausdruck; der Baum wird deshalb in Python gelaufen (dieselbe
    Funktion wie in DSGVO-1b, nur hier lokal — eine Migration darf sich nicht
    auf Anwendungscode verlassen, der sich später ändert).
    """
    import json

    pk = str(
        bind.execute(
            sa.text(
                "SELECT a.attname FROM pg_index i "
                "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0] "
                "WHERE i.indrelid = cast(:t AS regclass) AND i.indisprimary AND i.indnatts = 1"
            ),
            {"t": tabelle},
        ).scalars().first()
        or "id"
    )
    abbildung = abbildung if abbildung is not None else dict(
        bind.execute(sa.text(f"SELECT alt, neu FROM {ALT_NEU}")).all()
    )
    if not abbildung:
        return
    zeilen = bind.execute(
        sa.text(f'SELECT "{pk}", "{spalte}"::text FROM "{tabelle}" WHERE "{spalte}" IS NOT NULL')
    ).all()
    for schluessel, wert in zeilen:
        roh = wert
        if isinstance(roh, str):
            try:
                roh = json.loads(roh)
            except ValueError:
                continue
        neu = _ersetze(roh, abbildung)
        if neu == roh:
            continue
        neuer_text = json.dumps(neu)
        if als_text:
            # Byte-genau: nur den Textwert austauschen, kein `cast(... jsonb)`.
            bind.execute(
                sa.text(f'UPDATE "{tabelle}" SET "{spalte}" = :w WHERE "{pk}" = :k'),
                {"w": neuer_text, "k": schluessel},
            )
        elif bind.dialect.name == "postgresql":
            bind.execute(
                sa.text(
                    f'UPDATE "{tabelle}" SET "{spalte}" = cast(:w AS jsonb) '
                    f'WHERE "{pk}" = :k'
                ),
                {"w": neuer_text, "k": schluessel},
            )
        else:
            bind.execute(
                sa.text(f'UPDATE "{tabelle}" SET "{spalte}" = :w WHERE "{pk}" = :k'),
                {"w": neuer_text, "k": schluessel},
            )


def _ersetze(wert, abbildung: dict):
    """JSON-Baum: jeder String, der GENAU eine alte Kennung ist, wird ersetzt."""
    if isinstance(wert, str):
        return abbildung.get(wert, wert)
    if isinstance(wert, list):
        return [_ersetze(x, abbildung) for x in wert]
    if isinstance(wert, dict):
        return {k: _ersetze(v, abbildung) for k, v in wert.items()}
    return wert


def downgrade() -> None:
    """Rückweg über die Abbildung — nur ZEILENWEISE, nie als Massen-UPDATE.

    Warum zeilenweise: `uq_mitglied_email_normalisiert` ist ein UNIQUE-Index
    über `lower(trim(email))`. Ein Massen-UPDATE prüft die Eindeutigkeit je
    Zeile gegen den AKTUELLEN Stand — die neue Zeile hat dieselbe Adresse wie
    die alte, die alte ist aber noch nicht umgeschrieben. Erst `name` der alten
    Zeile und `name` der neuen Zeile tauschen, DANN die Verweise umhängen, dann
    die neue Zeile löschen: in jedem Zwischenschritt ist jede Adresse genau
    einmal vergeben.
    """
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(ABBILDUNG):
        return

    paare = bind.execute(
        sa.text(f"SELECT alt, neu FROM {ABBILDUNG} ORDER BY alt")
    ).all()
    if not paare:
        bind.execute(sa.text(f"DROP TABLE {ABBILDUNG}"))
        return

    # Rückweg nur, solange kein `neu` inzwischen anderweitig belegt ist.
    belegt = bind.execute(
        sa.text(
            f"SELECT a.alt, a.neu FROM {ABBILDUNG} a "
            f"JOIN mitglied m ON m.name = a.alt"
        )
    ).all()
    if belegt:
        raise RuntimeError(
            "ID-1 kann nicht zurückgenommen werden: "
            f"{len(belegt)} alte Kennung(en) sind inzwischen neu belegt "
            f"(z. B. {belegt[0][0]!r}). Bitte zuerst diese Zeilen prüfen."
        )

    spalten = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = 'mitglied' "
            "ORDER BY ordinal_position"
        )
    ).scalars().all()
    kopieren = [s for s in spalten if s != "name"]
    ziel = ", ".join(f'"{s}"' for s in kopieren)
    auswahl = ", ".join(
        f'COALESCE(m."{s}", {_standardwert(s)})' if s in _OHNE_VORGABE
        else "NULL" if s == "email"                     # erst nach dem Löschen
        else f'm."{s}"'
        for s in kopieren
    )
    fks = _fk_spalten(bind)

    # 0) Die Einwilligungs-Schlüssel ZUERST zurück (N3) — solange die
    #    Abbildung noch vollständig ist und die Mitglieder ihre neuen
    #    Kennungen tragen.
    _einwilligungen_umbenennen(
        bind, {neu: alt for alt, neu in paare}, zurueck=True,
    )

    for alt, neu in paare:
        # 1) Die Adresse VOR dem Kopieren merken — die Zeile unter der alten
        #    Kennung entsteht ohne Adresse (der UNIQUE-Index duldet sie nicht
        #    doppelt) und bekommt sie erst, wenn die neue Zeile gefallen ist.
        fremd = bind.execute(
            sa.text('SELECT "email" FROM mitglied WHERE name = :n'), {"n": neu}
        ).scalar()
        bind.execute(
            sa.text(
                f"INSERT INTO mitglied (name, {ziel}) "
                f"SELECT :alt, {auswahl} FROM mitglied m WHERE m.name = :neu"
            ),
            {"alt": alt, "neu": neu},
        )
        # 2) Kind-/Verweisspalten ohne FK (B1) und alle Verweise zurück.
        _kind_umhaengen(bind, neu, alt)
        for tabelle, spalte, _nullable, _regel in fks:
            bind.execute(
                sa.text(f'UPDATE "{tabelle}" SET "{spalte}" = :a WHERE "{spalte}" = :n'),
                {"a": alt, "n": neu},
            )
        for tabelle, spalte, art, doctype_spalte in WERT_SPALTEN:
            if art != "wert":
                continue
            bedingung = (
                f' AND "{doctype_spalte}" = :d' if doctype_spalte else ""
            )
            bind.execute(
                sa.text(
                    f'UPDATE "{tabelle}" SET "{spalte}" = :a '
                    f'WHERE "{spalte}" = :n{bedingung}'
                ),
                {"a": alt, "n": neu, "d": MITGLIED},
            )
        for tabelle, spalte, art, _doctype in WERT_SPALTEN:
            if art not in ("json", "json_text"):
                continue
            _json_umhaengen(bind, tabelle, spalte, {neu: alt},
                            als_text=(art == "json_text"))
        # 3) Die Zeile unter der NEUEN Kennung fällt.
        bind.execute(sa.text("DELETE FROM mitglied WHERE name = :n"), {"n": neu})
        # 4) Die Adresse der Person zurück auf die alte Kennung.
        bind.execute(
            sa.text('UPDATE mitglied SET "email" = :e WHERE name = :a'),
            {"e": fremd, "a": alt},
        )

    # Die Abbildung hat ihren Zweck erfüllt: sie enthielte sonst dauerhaft die
    # alten Klarname-Kennungen (genau der Zustand, den ID-1 beseitigt).
    bind.execute(sa.text(f"DROP TABLE {ABBILDUNG}"))
