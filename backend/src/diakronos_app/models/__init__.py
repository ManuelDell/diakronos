"""Modelle — generiert von tools/gen_models.py."""
from __future__ import annotations

from diakronos_app.models.base import Base
from diakronos_app.models.datenschutz import Loeschantrag
from diakronos_app.models.gemeinde import (
    DATENSCHUTZ_TEXT_NAME,
    DATENSCHUTZ_VEROEFFENTLICHT_NAME,
    GEMEINDE_EINSTELLUNGEN_NAME,
    DatenschutzText,
    DatenschutzTextVeroeffentlicht,
    GemeindeEinstellungen,
)
from diakronos_app.models.passwortzugang import Passwortzugang
from diakronos_app.models.sicherung import Sicherungseinstellungen, Sicherungslauf
from diakronos_app.models.smtp import SmtpEinstellungen
from diakronos_app.models.auth_oidc import Anmeldeeinstellungen
from diakronos_app.models.auth_oidc import GruppenRolleZuordnung
from diakronos_app.models.auth_oidc import OidcIdentitaet
from diakronos_app.models.auth_oidc import ZuordnungsAblehnung
from diakronos_app.models.core import (
    DocType,
    DynamicLinkModel,
    EventParticipants,
    FileModel,
    HasRole,
    NotificationLog,
    Role,
    User,
    UserNotificationPreference,
    UserRole,
)

from diakronos_app.models.diakonos import Anmeldeformular
from diakronos_app.models.diakonos import AnmeldeformularDokument
from diakronos_app.models.diakonos import AnmeldeformularFeld
from diakronos_app.models.diakonos import Anmeldung
from diakronos_app.models.diakonos import AnmeldungAntwort
from diakronos_app.models.diakonos import AnmeldungKind
from diakronos_app.models.diakonos import AuditLog
from diakronos_app.models.diakonos import AuditPolicy
from diakronos_app.models.diakonos import Beitrag
from diakronos_app.models.diakonos import BeitragKommentar
from diakronos_app.models.diakonos import BugReport
from diakronos_app.models.diakonos import DSGVOEinwilligung
from diakronos_app.models.diakonos import DashboardWidget
from diakronos_app.models.diakonos import DashboardWidgetUserConfig
from diakronos_app.models.diakonos import Dienstbereich
from diakronos_app.models.diakonos import DienstbereichVerantwortlicher
from diakronos_app.models.diakonos import Dienstplan
from diakronos_app.models.diakonos import DienstplanMitwirkender
from diakronos_app.models.diakonos import DienstplanPosition
from diakronos_app.models.diakonos import DienstplanPositionMitglied
from diakronos_app.models.diakonos import DienstplanTeilnehmer
from diakronos_app.models.diakonos import DienstplanTermin
from diakronos_app.models.diakonos import DienstplanVorlage
from diakronos_app.models.diakonos import DienstplanVorlageGruppe
from diakronos_app.models.diakonos import DienstplanVorlageKategorie
from diakronos_app.models.diakonos import DienstplanVorlageSlot
from diakronos_app.models.diakonos import Dienstrolle
from diakronos_app.models.diakonos import Gruppe
from diakronos_app.models.diakonos import GruppeVerantwortlicher
from diakronos_app.models.diakonos import GruppenAnkuendigung
from diakronos_app.models.diakonos import GruppenAufgabe
from diakronos_app.models.diakonos import Gruppenmitgliedschaft
from diakronos_app.models.diakonos import Gruppenrolle
from diakronos_app.models.diakonos import Gruppentyp
from diakronos_app.models.diakonos import Mitglied
from diakronos_app.models.diakonos import MitgliedBereich
from diakronos_app.models.diakonos import MitgliedBeziehung
from diakronos_app.models.diakonos import Registrierungslink
from diakronos_app.models.diakonos import RessourcenBuchung
from diakronos_app.models.diakonos import Rollenbesetzung
from diakronos_app.models.diakonos import SichererAnhang
from diakronos_app.models.diakonos import Untergruppe
from diakronos_app.models.diakonos import UntergruppeVerantwortlicher
from diakronos_app.models.diakonos import Untergruppenmitgliedschaft
from diakronos_app.models.diakonos import WikiArtikel
from diakronos_app.models.diakronos import DiakronosEinstellungen
from diakronos_app.models.diakronos import DiakronosModulEinstellung
from diakronos_app.models.diakronos import DiakronosModulRolle
from diakronos_app.models.diakronos import Nutzereinzelrechte
from diakronos_app.models.id1 import MitgliedKennung
from diakronos_app.models.kronos import Ablaufplan
from diakronos_app.models.kronos import AblaufplanPosition
from diakronos_app.models.kronos import Element
from diakronos_app.models.kronos import ElementAenderung
from diakronos_app.models.kronos import ElementMitarbeiter
from diakronos_app.models.kronos import ElementRessource
from diakronos_app.models.kronos import Eventkategorie
from diakronos_app.models.kronos import GoogleKalenderEinstellungen
from diakronos_app.models.kronos import Kalender
from diakronos_app.models.kronos import KalenderModerator
from diakronos_app.models.kronos import KronosEinstellungen
from diakronos_app.models.kronos import KronosKanbanZustand
from diakronos_app.models.kronos import Ressource
from diakronos_app.models.planrahmen import Abwesenheit
from diakronos_app.models.planrahmen import Eintrag
from diakronos_app.models.planrahmen import Merkmal
from diakronos_app.models.planrahmen import MerkmalWert
from diakronos_app.models.planrahmen import Plan
from diakronos_app.models.planrahmen import Plantyp
from diakronos_app.models.planrahmen import PlantypVersion
from diakronos_app.models.planrahmen import Sammlung
from diakronos_app.models.planrahmen import SammlungEintrag
from diakronos_app.models.planrahmen import Termin
from diakronos_app.models.planrahmen import Verlauf
from diakronos_app.models.psalmos import Lied
from diakronos_app.models.psalmos import LiedAnlass
from diakronos_app.models.psalmos import LiedGruppenzuordnung
from diakronos_app.models.psalmos import LiedKategorie
from diakronos_app.models.psalmos import LiedMaterial
from diakronos_app.models.psalmos import Liedanlass
from diakronos_app.models.psalmos import Liedfassung
from diakronos_app.models.psalmos import Liedgruppe
from diakronos_app.models.psalmos import LiedgruppeLied
from diakronos_app.models.psalmos import LiedgruppeRolle
from diakronos_app.models.psalmos import Liedkategorie
from diakronos_app.models.psalmos import Liedstrophe
from diakronos_app.models.devmodus import (
    DevBefund,
    DevEreignis,
    DevSitzung,
)

__all__ = [
    "DATENSCHUTZ_TEXT_NAME",
    "DATENSCHUTZ_VEROEFFENTLICHT_NAME",
    "GEMEINDE_EINSTELLUNGEN_NAME",
    "DatenschutzText",
    "DatenschutzTextVeroeffentlicht",
    "GemeindeEinstellungen",
    "Ablaufplan",
    "AblaufplanPosition",
    "Abwesenheit",
    "Anmeldeeinstellungen",
    "Anmeldeformular",
    "AnmeldeformularDokument",
    "AnmeldeformularFeld",
    "Anmeldung",
    "AnmeldungAntwort",
    "AnmeldungKind",
    "AuditLog",
    "AuditPolicy",
    "Beitrag",
    "BeitragKommentar",
    "BugReport",
    "DSGVOEinwilligung",
    "DashboardWidget",
    "DashboardWidgetUserConfig",
    "DiakronosEinstellungen",
    "DiakronosModulEinstellung",
    "DiakronosModulRolle",
    "Dienstbereich",
    "DienstbereichVerantwortlicher",
    "Dienstplan",
    "DienstplanMitwirkender",
    "DienstplanPosition",
    "DienstplanPositionMitglied",
    "DienstplanTeilnehmer",
    "DienstplanTermin",
    "DienstplanVorlage",
    "DienstplanVorlageGruppe",
    "DienstplanVorlageKategorie",
    "DienstplanVorlageSlot",
    "Dienstrolle",
    "DocType",
    "DynamicLinkModel",
    "Eintrag",
    "Element",
    "ElementMitarbeiter",
    "ElementRessource",
    "ElementAenderung",
    "EventParticipants",
    "Eventkategorie",
    "FileModel",
    "GoogleKalenderEinstellungen",
    "Gruppe",
    "GruppeVerantwortlicher",
    "GruppenAnkuendigung",
    "GruppenAufgabe",
    "GruppenRolleZuordnung",
    "Gruppenmitgliedschaft",
    "Gruppenrolle",
    "Gruppentyp",
    "HasRole",
    "Kalender",
    "KalenderModerator",
    "KronosEinstellungen",
    "KronosKanbanZustand",
    "Lied",
    "LiedAnlass",
    "LiedGruppenzuordnung",
    "LiedKategorie",
    "LiedMaterial",
    "Liedanlass",
    "Liedfassung",
    "Liedgruppe",
    "LiedgruppeLied",
    "LiedgruppeRolle",
    "Liedkategorie",
    "Liedstrophe",
    "Mitglied",
    "MitgliedBereich",
    "MitgliedBeziehung",
    "MitgliedKennung",
    "NotificationLog",
    "Nutzereinzelrechte",
    "OidcIdentitaet",
    "ZuordnungsAblehnung",
    "Plantyp",
    "PlantypVersion",
    "Registrierungslink",
    "Ressource",
    "RessourcenBuchung",
    "Role",
    "Rollenbesetzung",
    "Sammlung",
    "SammlungEintrag",
    "SichererAnhang",
    "Merkmal",
    "MerkmalWert",
    "Plan",
    "Termin",
    "Untergruppe",
    "UntergruppeVerantwortlicher",
    "Untergruppenmitgliedschaft",
    "User",
    "DevBefund",
    "DevEreignis",
    "DevSitzung",
    "UserNotificationPreference",
    "UserRole",
    "Verlauf",
    "WikiArtikel",
    "Sicherungseinstellungen",
    "Sicherungslauf",
]
