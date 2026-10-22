"""Alembic-Umgebung — liest die DB-URL aus der ENV-Variable DATABASE_URL.

Enthaelt einen `process_revision_directives`-Hook, der bei
`--autogenerate` die FOREIGN-KEY-Constraints aus den CREATE TABLE-Statements
herauszieht und als ALTER TABLE ADD CONSTRAINT hinter alle Tabellen stellt.

Grund: das Frappe-Schema enthaelt echte FK-Zyklen (z. B. Element<->Ablaufplan,
Element<->Registrierungslink, Mitglied->Mitglied). Eine topologische
Tabellen-Sortierung ist damit unmoeglich; ohne den Hook schlaegt
`alembic upgrade head` mit `UndefinedTable` fehl.
"""

from logging.config import fileConfig

from alembic import context
from alembic.operations import ops
from sqlalchemy import Column, ForeignKeyConstraint, engine_from_config, pool

from diakronos_app.db import Base
from diakronos_app.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DB-URL aus der Anwendungs-Konfiguration (die wiederum ENV / .env liest).
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata

#: Ausdrucks-Indizes, die NICHT aus der Metadaten-Deklaration abgeleitet werden
#: sollen. `alembic check` vergleicht sonst die gerenderte Deklaration
#: (`lower(trim(email))`) mit der tatsaechlichen Datenbankdefinition
#: (`lower(TRIM(BOTH FROM email))`) und meldet dauerhaft „remove_index +
#: add_index“, obwohl der Index korrekt ist. Angelegt und gepflegt wird er
#: von der Migration `sec2_email_eindeutig`.
_AUSGENOMMENE_INDIZES = {"uq_mitglied_email_normalisiert"}

#: Tabellen, die NUR eine Migration anlegt (kein Modell): die Abbildung
#: `alt -> neu` der Kennungen aus ID-1. Sie ist ein Umzugsprotokoll, kein
#: Fachdatum — ohne Eintrag hier meldet `alembic check` dauerhaft
#: „remove_table“ und der Abnahme-Lauf bricht ab. Angelegt und (im
#: `downgrade`) geloescht wird sie von `id1_mitglied_kennungen`.
_NUR_MIGRATION_TABELLEN = {"id1_mitglied_kennung"}


def _include_object(obj, name, type_, reflected, compare_to):
    """Autogenerate-Vergleich: Ausdrucks-Indizes und Umzugsprotokolle ausblenden."""
    if type_ == "index" and name in _AUSGENOMMENE_INDIZES:
        return False
    if type_ == "table" and name in _NUR_MIGRATION_TABELLEN:
        return False
    return True


def _fk_pairs(table_name: str):
    """Liefert (name, source_table, referent_table, [local], [remote]) je FK.

    Quelle ist die Metadata-Tabelle — nicht `op.to_table()`, das mit dem
    schema-Kwarg kollidiert.
    """
    table = target_metadata.tables.get(table_name)
    if table is None:
        return []
    pairs = []
    for constraint in table.foreign_key_constraints:
        pairs.append((
            constraint.name,
            table.name,
            constraint.elements[0].column.table.name,
            [e.parent.name for e in constraint.elements],
            [e.column.name for e in constraint.elements],
        ))
    return pairs


def _strip_fk_columns(op: "ops.CreateTableOp", table_name: str) -> None:
    """Entfernt FK-Klauseln aus den Spalten-Definitionen eines create_table.

    Die Spalten-Objekte in `op.columns` tragen `ForeignKey`-Objekte in
    `column.foreign_keys`. Diese werden entfernt; NULL/NOT NULL und Typ
    bleiben erhalten.
    """
    for column in op.columns:
        if isinstance(column, Column):
            if column.foreign_keys:
                for fk in list(column.foreign_keys):
                    column.foreign_keys.discard(fk)

    # Tabellenweite FK-Constraints aus dem CREATE TABLE entfernen — sie
    # werden spaeter als ALTER TABLE ADD CONSTRAINT gesetzt.
    op.columns = [
        c for c in op.columns if not isinstance(c, ForeignKeyConstraint)
    ]


def _detach_foreign_keys(context_, revision, directives) -> None:
    """Zieht FKs aus create_table heraus -> separate create_foreign_key danach."""
    if not directives:
        return
    directive = directives[0]
    if not isinstance(directive, ops.MigrationScript):
        return

    upgrade_ops = directive.upgrade_ops
    detached: list = []
    kept: list = []

    for op in upgrade_ops.ops:
        if isinstance(op, ops.CreateTableOp):
            for (name, st, rt, lc, rc) in _fk_pairs(op.table_name):
                detached.append(
                    ops.CreateForeignKeyOp(
                        constraint_name=name,
                        source_table=st,
                        referent_table=rt,
                        local_cols=lc,
                        remote_cols=rc,
                    )
                )
            _strip_fk_columns(op, op.table_name)
            kept.append(op)
        else:
            kept.append(op)

    # Erst alle Tabellen, dann die FKs.
    upgrade_ops.ops = kept + detached


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=_detach_foreign_keys,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=_detach_foreign_keys,
            include_object=_include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
