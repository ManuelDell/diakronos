"""N6: Datenschutz-Verwaltung; Antrag und Erledigung sind getrennte Vorgänge.

Die Anonymisierung betrifft den Personenstamm und das lokale Konto, nicht
Freitextnennungen in fremden Beiträgen/Dateien. Technische Kennungen und
Nachweise bleiben erhalten. Die Oberfläche benennt diese Grenzen ausdrücklich.
"""
from __future__ import annotations

FRAPPE_MODULE = "diakronos.diakonos.api.datenschutz"

from datetime import datetime
from uuid import uuid4

from sqlalchemy import and_, or_, select, update

from diakronos_app.api.admin_hub import _require_admin
from diakronos_app.db import als_aktuelle_sitzung
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import DoesNotExistError, ValidationError
from diakronos_app.frappe_compat.session import session
from diakronos_app.models.core import User
from diakronos_app.models.datenschutz import (
    GRUND_MAX, STATUS_ABGELEHNT, STATUS_AUSGEFUEHRT, STATUS_OFFEN, STATUS_WERTE,
    STATUS_ZURUECKGEZOGEN, Loeschantrag,
)
from diakronos_app.models.diakonos import Mitglied, DSGVOEinwilligung, AuditLog


def _post(request):
    if request is None or request.method != "POST":
        raise ValidationError("Bitte diesen Vorgang mit POST ausführen.")


def _person(s, name):
    m = s.scalar(select(Mitglied).where(Mitglied.name == name).with_for_update())
    if m is None:
        raise DoesNotExistError("Person nicht gefunden.")
    return m


def _zeile(obj):
    return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}


def _konten(m):
    from diakronos_app.frappe_compat.benutzer_status import wirksame_konten
    return wirksame_konten(_zeile(m))


@whitelist(allow_guest=False)
def auskunft(mitglied_id):
    """JSON-Auskunft mit Stamm, Konto und direkt zugeordneten Datensätzen.

    Keine Zugangsdaten/Token, keine Sitzungen, keine Daten anderer Konten.
    Dateien selbst sind nicht in JSON eingebettet, ihre Metadaten schon.
    """
    _require_admin()
    return _auskunft(mitglied_id)


@whitelist(allow_guest=False)
def meine_auskunft():
    """Gleiche Auskunft wie für Admins, Ziel ausschließlich aus der Sitzung."""
    from diakronos_app.api.profile import _get_my_mitglied
    return _auskunft(_get_my_mitglied())


@whitelist(allow_guest=False)
def mein_loeschantrag():
    """Stand des EIGENEN Löschantrags (D2). Ziel ausschließlich aus der Sitzung.

    Rückgabe ``None``, solange kein Antrag gestellt wurde. Sonst der Stand:
    ``status`` (``offen`` / ``zurueckgezogen`` / ``ausgefuehrt``),
    ``beantragt_am`` und — sofern zutreffend — ``zurueckgezogen_am`` bzw.
    ``anonymisiert_am``. Personenbezogene Werte anderer Personen enthält die
    Antwort nicht; der Nachweis nach der Ausführung nennt nur Zeitpunkte.
    """
    from diakronos_app.api.profile import _get_my_mitglied
    from diakronos_app.db import SessionLocal
    mid = _get_my_mitglied()
    with SessionLocal() as s:
        return _antrag_stand(s.get(Loeschantrag, mid))


def _antrag_stand(a) -> dict | None:
    """Die eine Form des Antrags-Stands — für Person und Verwaltung gleich.

    Seit DSGVO-2a auch die Ablehnung: die Person muss die Begründung lesen
    können (Art. 15 DSGVO), deshalb steht `ablehnung_grund` hier und nicht nur
    in der Verwaltungsliste. `abgelehnt_von` (Konto des Administrators) bleibt
    in der Antwort an die Person weg — es ist ein Beschäftigtendatum und für
    die Sachentscheidung nicht nötig; die Verwaltung sieht es über
    `get_loeschantraege`.
    """
    if a is None:
        return None
    return {
        "mitglied": a.mitglied,
        "beantragt_am": a.beantragt_am,
        "status": a.status or ("ausgefuehrt" if a.erledigt_am else STATUS_OFFEN),
        "zurueckgezogen_am": a.zurueckgezogen_am,
        "freigegeben_am": a.freigegeben_am,
        "abgelehnt_am": a.abgelehnt_am,
        "ablehnung_grund": a.ablehnung_grund,
        "anonymisiert_am": a.anonymisiert_am,
        "erledigt_am": a.erledigt_am,
        "erledigt_von": a.erledigt_von,
    }


def _auskunft(mitglied_id):
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.base import Base

    with SessionLocal() as s, als_aktuelle_sitzung(s):
        m = _person(s, mitglied_id)
        konten = _konten(m)
        bezug, taetigkeiten = {}, []
        # Subjekt und Tätigkeit sind verschieden: ein Bearbeiter erhält keine
        # fremden Stammdaten, Antworten, Auditwerte oder Dateimetadaten. Auch
        # echte FK wie zugeteilt_von/Leitung sind keine Subjektzuordnung.
        autorenfelder = {'owner', 'modified_by', 'actor', 'created_by', 'from_user'}
        nebenbezug = {'erstellt_von', 'zugeteilt_von', 'moderiert_von',
                     'leitung', 'verantwortlich', 'verantwortlicher', 'kontakt_abweichend'}
        dynamische_links = (
            ('target_doctype', 'target_name'),
            ('attached_to_doctype', 'attached_to_name'),
            ('reference_doctype', 'reference_docname'),
            ('link_doctype', 'link_name'),
            ('referenz_doctype', 'referenz_name'),
            ('quelle_doctype', 'quelle_name'),
            ('inhalt_doctype', 'inhalt_name'),
        )
        for mapper in sorted(Base.registry.mappers, key=lambda m: m.local_table.name):
            cls = mapper.class_
            t = mapper.local_table
            if cls in (Mitglied, User) or t.name == 'passwortzugang' or t.name.startswith(('auth_', 'oidc_', 'google_')):
                continue
            subjekt, referenzen = [], {}
            for c in t.columns:
                ziele = {f.target_fullname for f in c.foreign_keys}
                if 'mitglied.name' in ziele:
                    referenzen[c.key] = c == mitglied_id
                elif 'user.name' in ziele or c.key in autorenfelder:
                    referenzen[c.key] = c.in_(konten)
                else:
                    continue
                if c.key not in autorenfelder | nebenbezug:
                    subjekt.append(referenzen[c.key])
            for typ, name in dynamische_links:
                if typ in t.c and name in t.c:
                    subjekt.append(or_(
                        and_(t.c[typ] == 'Mitglied', t.c[name] == mitglied_id),
                        and_(t.c[typ] == 'User', t.c[name].in_(konten)),
                    ))
            if 'parent' in t.c and 'parenttype' in t.c:
                subjekt.append(or_(
                    and_(t.c.parenttype == 'Mitglied', t.c.parent == mitglied_id),
                    and_(t.c.parenttype == 'User', t.c.parent.in_(konten)),
                ))
                # Diese dedizierten Kindtabellen enthalten auch importierte
                # Zeilen ohne parenttype; keine Namenserkennung bei anderen.
                if t.name in ('mitglied_bereich', 'mitglied_beziehung', 'has_role'):
                    legacy = t.c.parent.in_(konten) if t.name == 'has_role' else t.c.parent == mitglied_id
                    subjekt.append(and_(or_(t.c.parenttype.is_(None), t.c.parenttype == ''), legacy))
            if not subjekt and not referenzen:
                continue
            ist_subjekt = or_(*subjekt) if subjekt else False
            for r, eigener_bezug in s.execute(select(cls, ist_subjekt).where(
                or_(ist_subjekt, *referenzen.values())
            )).all():
                if eigener_bezug:
                    bezug.setdefault(t.name, []).append({
                        k: v for k, v in _zeile(r).items()
                        if not any(w in k.lower() for w in ('password', 'secret', 'token', 'slug'))
                    })
                else:
                    # Nur die eigenen Referenzwerte, nie fremder Objektinhalt.
                    felder = {k: getattr(r, k) for k in referenzen
                              if getattr(r, k) in konten or getattr(r, k) == mitglied_id}
                    taetigkeiten.append({'tabelle': t.name,
                                         'kennung': {c.key: getattr(r, c.key) for c in t.primary_key},
                                         'felder': felder})
        # Registrierungsantworten sind Frappe-Kindzeilen ohne FK. Sie gehören
        # zur Auskunft, werden aber nicht über fremde Registrierungen eingesammelt.
        from diakronos_app.models.diakonos import AnmeldungAntwort, AnmeldungKind
        anmeldungen = [r['name'] for r in bezug.get('anmeldung', [])]
        for cls in (AnmeldungAntwort, AnmeldungKind):
            rows = s.scalars(select(cls).where(cls.parent.in_(anmeldungen))).all()
            if rows:
                bezug[cls.__tablename__] = [_zeile(r) for r in rows]
        return {
            'erstellt_am': datetime.utcnow(),
            'mitglied': _zeile(m),
            'konten': [
                {k: getattr(u, k) for k in ('name', 'email', 'full_name', 'enabled', 'user_image')}
                for u in s.scalars(select(User).where(User.name.in_(konten))).all()
            ],
            'bezug': bezug,
            'taetigkeiten': taetigkeiten,
            'hinweis': 'Dateien sind als Verweise enthalten. Tätigkeiten an fremden Objekten enthalten nur Kennung und eigene Referenzfelder, keine fremden Inhalte. Freitextnennungen ohne technische Zuordnung bitte gesondert prüfen.',
        }


@whitelist(allow_guest=False)
def loeschung_beantragen(bestaetigt=False, request=None):
    """Die Person stellt für SICH einen Löschantrag (D2).

    Nur die eigene Person: es gibt kein `mitglied_id`-Argument, das Ziel kommt
    ausschließlich aus der Sitzung (`profile._get_my_mitglied`). `bestaetigt`
    ist Pflicht — die Oberfläche fragt vorher nach (Profil → „Löschung
    beantragen“).

    Verhalten:
    * kein Antrag vorhanden → neuer Antrag `offen`, In-App-Meldung an alle
      Mitgliederadministratoren und System Manager (NotificationLog).
    * Antrag `offen` → unverändert zurück (idempotent, kein Datenverlust).
    * Antrag `zurueckgezogen` → wieder `offen` mit neuer `beantragt_am`
      (die Person darf es sich anders überlegen; der alte Zeitpunkt ist damit
      weg — der Vorgang zählt neu).
    * Antrag `ausgefuehrt` → abgelehnt: nach der Anonymisierung gibt es kein
      Konto mehr, an dem ein Antrag hängen könnte.
    * Antrag `abgelehnt` (DSGVO-2a) → wieder `offen` mit neuer `beantragt_am`;
      Ablehnungszeitpunkt, -konto und -begründung werden dabei gelöscht (der
      neue Vorgang beginnt unbeschrieben bei der Verwaltung).

    Die Verwaltung sieht den Antrag sofort unter `get_loeschantraege`; die
    Meldung ist Beiwerk und darf den Antrag nicht scheitern lassen
    (`benachrichtigungen.schreibe_meldung` schluckt Fehler).
    """
    _post(request)
    if bestaetigt is not True:
        raise ValidationError("Bitte den Löschantrag bestätigen.")
    from diakronos_app.api.profile import _get_my_mitglied
    from diakronos_app.db import SessionLocal

    mid = _get_my_mitglied()
    with SessionLocal.begin() as s:
        person = _person(s, mid)  # serialisiert parallele Anträge derselben Person
        if str(person.status or "") == "geloescht":
            raise ValidationError(
                "Diese Person ist bereits gelöscht — ein Antrag ist nicht mehr möglich."
            )
        a = s.get(Loeschantrag, mid)
        neu = a is None or (a.status or STATUS_OFFEN) == STATUS_ZURUECKGEZOGEN
        if a is None:
            a = Loeschantrag(mitglied=mid, beantragt_am=datetime.utcnow(), status=STATUS_OFFEN)
            s.add(a)
        elif (a.status or STATUS_OFFEN) == STATUS_AUSGEFUEHRT or a.erledigt_am:
            raise ValidationError("Der Löschantrag ist bereits ausgeführt und nicht wiederholbar.")
        elif (a.status or STATUS_OFFEN) == STATUS_ABGELEHNT:
            # DSGVO-2a: Die Ablehnung ist eine Entscheidung, kein Endzustand. Die
            # Person darf es erneut versuchen — dann zählt der Vorgang neu, und
            # die alte Begründung darf nicht am neuen Antrag stehen bleiben.
            neu = True
            a.status = STATUS_OFFEN
            a.beantragt_am = datetime.utcnow()
            a.zurueckgezogen_am = None
            a.abgelehnt_am = None
            a.abgelehnt_von = None
            a.ablehnung_grund = None
        elif neu:
            a.status = STATUS_OFFEN
            a.beantragt_am = datetime.utcnow()
            a.zurueckgezogen_am = None
        stand = _antrag_stand(a)
        if neu:
            _melde_antrag_an_verwaltung(s, person)
    return stand


#: Betreff der In-App-Meldung an die Verwaltung (eigene Konstante, weil drei
#: Stellen ihn brauchen: anlegen, zurückziehen, Nachweis).
MELDUNG_BETREFF = "Löschantrag nach DSGVO gestellt"

#: Nach der Ausführung: derselbe Vorgang, ohne den Namen der Person. Betreff
#: UND Text werden ersetzt — der Name stand im Text, nicht im Betreff.
MELDUNG_BETREFF_BESTAETIGT = "Löschantrag nach DSGVO ausgeführt"
MELDUNG_TEXT_BESTAETIGT = (
    "Der Löschantrag wurde bestätigt und ausgeführt: Die Person ist "
    "anonymisiert, ihr Benutzerkonto entfernt. Der Nachweis steht unter "
    "Datenschutz → Löschanträge."
)


def _melde_antrag_an_verwaltung(s, person) -> int:
    """In-App-Benachrichtigung an alle Verwaltungskonten (D2).

    Angesprochen werden Konten mit `System Manager` oder
    `Mitgliederadministrator` — dieselbe Rollenmenge wie `ADMIN_ROLES` in
    `api/mitglieder.py`. Der Text nennt die Person, denn die Verwaltung muss
    wissen, wen sie löschen soll; verschickt wird nichts (kein SMTP), die
    Meldung liegt in `notification_log` und ist an das Konto adressiert.
    """
    from diakronos_app.benachrichtigungen import schreibe_meldung
    from diakronos_app.frappe_compat.permissions import ist_user_zeile
    from diakronos_app.models.core import HasRole

    anzeige = " ".join(
        teil for teil in (str(person.vorname or ""), str(person.nachname or "")) if teil
    ).strip() or person.name
    zeilen = s.scalars(select(HasRole)).all()
    empfaenger = sorted({
        str(z.parent) for z in zeilen
        if z.role in ("System Manager", "Mitgliederadministrator")
        and z.parent and ist_user_zeile(z.parenttype)
    })
    anzahl = 0
    for konto in empfaenger:
        if schreibe_meldung(
            for_user=konto,
            subject=MELDUNG_BETREFF,
            inhalt=(
                f"{anzeige} hat die Löschung der eigenen Daten beantragt. "
                "Bitte prüfe den Antrag unter Datenschutz → Löschanträge und "
                "bestätige ihn dort. Erst nach der Bestätigung wird gelöscht."
            ),
            document_type="Mitglied",
            document_name=person.name,
            typ="Alert",
        ):
            anzahl += 1
    return anzahl


@whitelist(allow_guest=False)
def loeschantrag_zurueckziehen(bestaetigt=False, request=None):
    """Die Person zieht ihren Löschantrag zurück (D2), solange er `offen` ist.

    Danach darf sie jederzeit erneut beantragen. Ein bereits `ausgefuehrter`
    Antrag lässt sich nicht zurückziehen — die Daten sind weg, und ein
    „Rückzug“ würde eine Wiederherstellung vortäuschen.
    """
    _post(request)
    if bestaetigt is not True:
        raise ValidationError("Bitte den Rückzug bestätigen.")
    from diakronos_app.api.profile import _get_my_mitglied
    from diakronos_app.db import SessionLocal

    mid = _get_my_mitglied()
    with SessionLocal.begin() as s:
        _person(s, mid)
        a = s.get(Loeschantrag, mid)
        if a is None:
            raise ValidationError("Es liegt kein Löschantrag vor.")
        if (a.status or STATUS_OFFEN) == STATUS_AUSGEFUEHRT or a.erledigt_am:
            raise ValidationError(
                "Die Löschung ist bereits ausgeführt — der Antrag kann nicht "
                "zurückgezogen werden."
            )
        if (a.status or STATUS_OFFEN) == STATUS_ABGELEHNT:
            raise ValidationError(
                "Dieser Antrag wurde bereits von der Verwaltung abgelehnt. Du kannst "
                "einen neuen Antrag stellen."
            )
        if (a.status or STATUS_OFFEN) == STATUS_ZURUECKGEZOGEN:
            return _antrag_stand(a)  # idempotent
        a.status = STATUS_ZURUECKGEZOGEN
        a.zurueckgezogen_am = datetime.utcnow()
        _raeume_meldung_an_verwaltung_ab(s, mid)
        return _antrag_stand(a)


def _raeume_meldung_an_verwaltung_ab(s, mitglied_id: str) -> int:
    """Die In-App-Meldung „Löschantrag gestellt“ wieder entfernen.

    Sonst stünde in den Postfächern der Verwaltung weiter „X hat die Löschung
    beantragt“, obwohl X den Antrag zurückgezogen hat (oder die Verwaltung ihn
    abgelehnt hat, DSGVO-2a) — und nach der Anonymisierung bliebe X dort als
    Klartextname stehen (der Vollscan der Löschung sucht genau danach). Bezug
    ist der Dokumentname des Antrags.

    Entfernt werden nur DIESE Meldungen (`subject == MELDUNG_BETREFF`). Der
    Dokumentbezug allein reicht nicht: zum selben Mitglied liegen auch fremde
    Meldungen („Mitglied angelegt: …“ aus `admin_hub`) — die gehören einem
    anderen Vorgang und bleiben stehen (N1, R-DSGVO-2a).
    """
    from diakronos_app.models.core import NotificationLog

    with s.no_autoflush:
        betroffen = s.scalars(select(NotificationLog).where(
            NotificationLog.document_type == "Mitglied",
            NotificationLog.document_name == mitglied_id,
            NotificationLog.subject == MELDUNG_BETREFF,
        )).all()
        for zeile in betroffen:
            s.delete(zeile)
    return len(betroffen)


def _entpersonalisiere_verwaltungsmeldung(s, mitglied_id: str) -> int:
    """Die Meldung „Antrag gestellt“ trägt den Namen im Text.

    Sie bleibt als Zeile (Nachweis, dass es den Antrag gab), ihr Text wird
    aber ersetzt: nach der Löschung darf der Name nirgends mehr stehen — auch
    nicht im Postfach der Verwaltung. Bezug ist der Dokumentname des Antrags.

    Ersetzt wird NUR die Antragsmeldung (`subject == MELDUNG_BETREFF`): zum
    selben Mitglied liegen weitere Meldungen („Mitglied angelegt: …“ aus
    `admin_hub`), denen dieser Text nicht gehört (N1, R-DSGVO-2a).
    """
    from diakronos_app.models.core import NotificationLog

    return int(s.execute(
        update(NotificationLog)
        .where(NotificationLog.document_type == "Mitglied",
               NotificationLog.document_name == mitglied_id,
               NotificationLog.subject == MELDUNG_BETREFF)
        .values(subject=MELDUNG_BETREFF_BESTAETIGT, email_content=MELDUNG_TEXT_BESTAETIGT)
    ).rowcount or 0)


def _verwaltungs_konten(person) -> set[str]:
    """Wirksame Konten einer Person (`user`-Link UND eindeutige Adresse)."""
    return _konten(person)


def _pruefe_loeschberechtigung(konten: set[str]) -> None:
    """Darf der ANGEMELDETE Administrator diese Person löschen?

    Dieselben Regeln wie beim Sperren/Ausschließen (P1-8c/SEC*):

    * ein Konto mit Verwaltungsrolle darf nur ein System Manager löschen
      (`_verweigere_fremdes_admin_konto`);
    * der letzte aktive System Manager und der letzte aktive Administrator
      können nicht gelöscht werden (`_verweigere_letzten_admin_verlust*`);
    * gar kein aktives Verwaltungskonto übrig → abgelehnt (dieselbe Prüfung,
      die `_pruefe_mitglied_schreibzugriff` beim Schreiben noch einmal macht).
    """
    from diakronos_app.api.zugang import (
        _aktive_administratoren, _aktive_system_manager,
        _verweigere_fremdes_admin_konto, _verweigere_letzten_admin_verlust,
        _verweigere_letzten_admin_verlust_alle,
    )
    from diakronos_app.frappe_compat.exceptions import PermissionError

    for aktive in (_aktive_system_manager(), _aktive_administratoren()):
        if aktive and not (aktive - konten):
            raise PermissionError(
                "Der letzte aktive Verwaltungszugang darf nicht gelöscht werden — "
                "sonst ist die Verwaltung ausgesperrt."
            )
    for user in sorted(konten):
        _verweigere_fremdes_admin_konto(user)
        _verweigere_letzten_admin_verlust(user, "gelöscht")
        _verweigere_letzten_admin_verlust_alle(user, "gelöscht")


@whitelist(allow_guest=False)
def loeschung_bestaetigen(mitglied_id, bestaetigt=False, request=None):
    """Administrator bestätigt die Löschung auf Antrag (D4) — Reihenfolge zwingend.

    1. Nur ein OFFENER Antrag (`status='offen'`, nicht ausgeführt) ist
       bestätigbar; ohne Antrag gibt es nichts zu löschen.
    2. Mailversand muss eingerichtet sein. Ist SMTP nicht konfiguriert, wird
       NICHTS gelöscht: „Mailversand ist nicht eingerichtet — ohne ihn kann
       der Löschantrag nicht bearbeitet werden.“ (Ein Text für Bestätigen und
       Ablehnen, `mailversand.NICHT_EINGERICHTET`.)
    3. Die Mail an die hinterlegte Adresse geht VOR der vollständigen
       Anonymisierung raus (D4). Der Ablauf im Code ist: anonymisieren, dann
       `flush` (alle FK-/Constraint-Fehler treten hier auf), DANN die Mail,
       dann der Commit. Schlägt der Versand fehl, wird nichts committet und
       der Administrator erhält den Fehler (`MailVersandFehler`, 417) — der
       Vorgang bleibt `offen` und ist erneut versuchbar.
    4. Erst danach der Commit. Scheitert die Anonymisierung vorher, rollt
       alles zurück und der Administrator sieht den Fehler.

    Ein zweiter Versuch nach einem Anonymisierungsfehler ist unbedenklich: die
    Person ist dann noch nicht gelöscht, die Mail geht erneut raus (bewusst —
    der Nachweis „Meldung erfolgt“ gehört zu dem Versuch, der greift).

    Rückgabe: Zählung je Tabelle (`zaehler`) für Protokoll und Nachweis.
    """
    _require_admin()
    _post(request)
    if bestaetigt is not True:
        raise ValidationError("Bitte die Löschung bestätigen.")
    from diakronos_app import mailversand
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.benutzer_status import vergiss, widerrufe_sitzungen

    with SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        person = _person(s, mitglied_id)
        a = s.get(Loeschantrag, mitglied_id)
        if a is None or (a.status or STATUS_OFFEN) != STATUS_OFFEN or a.erledigt_am:
            raise ValidationError(
                "Es liegt kein offener Löschantrag vor. Die Löschung stellt das "
                "Mitglied selbst im Profil — der Administrator bestätigt sie hier."
            )
        if str(person.status or "") == "geloescht":
            raise ValidationError("Diese Person ist bereits gelöscht.")
        konten = _verwaltungs_konten(person)
        # N5 (R-DSGVO-1b): NUR die betroffenen Konto-Zeilen sperren, nicht alle
        # `user`-Zeilen — die Sperre hielt bisher den ganzen Mailversand (bis
        # 15 s) über jede Anmeldung im Betrieb auf. Reihenfolge stabil, damit
        # zwei Administratoren nicht gegeneinander laufen.
        if konten:
            s.scalars(select(User).where(User.name.in_(sorted(konten)))
                      .order_by(User.name).with_for_update()).all()
        _pruefe_loeschberechtigung(konten)

        adresse = str(person.email or "").strip()
        if not adresse:
            # Ohne Adresse keine Meldung — und ohne Meldung keine Löschung
            # (D4). Fail closed, statt still zu löschen.
            raise ValidationError(
                "Für diese Person ist keine E-Mail-Adresse hinterlegt — ohne Mail "
                "kann die Löschung nicht bestätigt werden."
            )
        if not mailversand.ist_konfiguriert():
            # N3: EIN neutraler Text für Bestätigen und Ablehnen
            # (`mailversand.NICHT_EINGERICHTET`) — der alte Satz behauptete
            # beim Ablehnen eine Bestätigung, die es dort nicht gibt.
            raise ValidationError(mailversand.NICHT_EINGERICHTET)

        # ── Schritt 1: Anonymisierung ausführen und FLUSHEN ───────────────
        # K3 (R-DSGVO-1): Erst rechnen, dann mailen. Der Flush in
        # `anonymisiere` löst alle FK-/Constraint-Fehler AUS, bevor eine Mail
        # rausgeht. Der Aufruf steckt in einem SAVEPOINT (`begin_nested`), damit
        # ein späterer Mailfehler NUR diesen Teil zurückrollen kann — die
        # Person steht dann unverändert da, auch wenn dazwischen schon eine
        # andere Schreiboperation gelaufen ist.
        _entpersonalisiere_verwaltungsmeldung(s, person.name)

        jetzt = datetime.utcnow()
        bisherige_kennung = person.name
        for typ, feld in (
            ("datenschutz", "datenschutz_einwilligung"),
            ("foto", "foto_einwilligung"),
            ("werbung", "werbeeinwilligung"),
        ):
            if getattr(person, feld):
                s.add(DSGVOEinwilligung(
                    name=uuid4().hex, mitglied=person.name, typ=typ,
                    aktion="widerrufen", widerrufen=True, zeitstempel=jetzt,
                ))
        from diakronos_app.dsgvo_anonymisierung import anonymisiere

        # Der Gemeindename für die Mail wird VOR dem SAVEPOINT gelesen:
        # `_gemeindename()` öffnet eine eigene Sitzung, und deren `close()`
        # würde auf einer Engine mit EINER Verbindung (SQLite-Tests) die offene
        # Transaktion samt SAVEPOINT mitreißen.
        gemeinde = mailversand._gemeindename()
        dateien: list[str] = []
        probe = s.begin_nested()
        ergebnis = anonymisiere(s, person.name, konten, dateien=dateien)
        kennung = ergebnis["kennung"]
        # Der Antrag ist der Nachweis und hängt an der Kennung — er wird mit
        # umgehängt, bevor die alte Zeile fällt (DSGVO-Architektur Punkt 1).
        _haenge_antrag_um(s, bisherige_kennung, kennung)
        a = s.get(Loeschantrag, kennung)
        a.benachrichtigt_am = jetzt
        a.freigegeben_am = jetzt
        a.freigegeben_von = session.user
        a.status = STATUS_AUSGEFUEHRT
        a.erledigt_am = jetzt
        a.erledigt_von = session.user
        a.anonymisiert_am = jetzt
        # N2 (R-DSGVO-2a): Eine Ablehnung EINIGE ZEIT VORHER am selben Antrag
        # darf nach der Löschung nicht als Freitext stehen bleiben — sie ist
        # für die Verwaltung geschrieben und nennt Personen („Frau X ist
        # erkrankt“). Nachweis der Entscheidung sind Status, Zeitpunkt und
        # Konto, nicht der Wortlaut. `abgelehnt_von` bleibt (Beschäftigtendatum,
        # wie `freigegeben_von`).
        a.ablehnung_grund = None
        a.abgelehnt_am = None
        s.add(AuditLog(
            name=uuid4().hex, actor=session.user, zeitstempel=jetzt,
            action_typ="Loeschung auf Antrag", target_doctype="Mitglied",
            target_name=kennung,
            consequence="Person vollständig anonymisiert; Konto entfernt",
        ))
        s.flush()

        # ── Schritt 2: Meldung an die Person ──────────────────────────────
        # Die Testnaht ist `mailversand.VERBINDUNG` (Standard None): Tests
        # setzen dort einen Fake-SMTP, damit kein Netz nötig ist.
        #
        # Der Fehler wird zur fachlichen Meldung (417), NICHT zur 500: der
        # Administrator soll lesen, dass nichts gelöscht wurde und er es erneut
        # versuchen kann (D4, Schritt 2).
        try:
            mailversand.sende_loeschbestaetigung(adresse, gemeinde=gemeinde)
            probe.commit()
        except mailversand.MailNichtEingerichtet as ex:
            probe.rollback()
            raise ValidationError(str(ex)) from None
        except mailversand.MailVersandFehler as ex:
            # NUR die Anonymisierung zurücknehmen — die Person steht danach
            # unverändert da, der Antrag bleibt offen, erneut versuchbar.
            probe.rollback()
            raise ValidationError(
                f"{ex} Es wurde NICHTS gelöscht — der Antrag bleibt offen, bitte "
                "erneut versuchen."
            ) from None

    # ── Nach dem Commit: Sitzungen weg, Caches vergessen, Dateien löschen ──
    for user in sorted(konten):
        widerrufe_sitzungen(user)
        vergiss(user)
    from diakronos_app.dsgvo_anonymisierung import dateien_entfernen

    # N-3: auch die Datei-Spalten der Bestandsaufnahme (Profilbild, Anhänge,
    # Screenshot) — `anonymisiere` sammelt sie in `bestand.dateien`, die
    # Rückgabeliste `dateien` enthielt bisher nur die `file`-Anhänge.
    entfernt = dateien_entfernen(set(dateien) | set(ergebnis["dateien"]))
    # M1 (R-DSGVO-1): KEINE Personendaten in der Antwort. Die Prüfliste des
    # Vollscans enthält genau die Werte, die gerade gelöscht wurden — sie bleibt
    # im Rückgabewert von `anonymisiere` (für Tests und Betriebsprüfung), nicht
    # in der HTTP-Antwort.
    return {
        "ok": True,
        "mitglied": kennung,
        "zaehler": ergebnis["zaehler"],
        "dateien_entfernt": entfernt,
    }


def _haenge_antrag_um(s, alt: str, kennung: str) -> None:
    """Löschantrag auf die neutrale Kennung umhängen (Primärschlüssel = mitglied)."""
    from sqlalchemy import text as _text

    s.execute(_text("UPDATE loeschantrag SET mitglied = :neu WHERE mitglied = :alt"),
              {"neu": kennung, "alt": alt})


@whitelist(allow_guest=False)
def loeschantrag_ablehnen(mitglied_id, begruendung="", bestaetigt=False, request=None):
    """Administrator lehnt den Löschantrag einer Person ab (DSGVO-2a).

    Dieselben Rechteregeln wie `loeschung_bestaetigen` (Mitgliederadministrator
    oder System Manager; ein Mitglied mit Verwaltungskonto darf nur ein System
    Manager ablehnen, und der letzte aktive Verwaltungszugang ist geschützt —
    `_pruefe_loeschberechtigung`). Die Sperren der betroffenen Kontozeilen
    werden wie dort gesetzt, damit Ablehnung und Bestätigung nicht
    gegeneinander laufen.

    Ablauf (Reihenfolge wie beim Bestätigen):
    1. Nur ein OFFENER Antrag ist ablehnbar — sonst gibt es nichts zu
       entscheiden.
    2. `begruendung` ist PFLICHT: nicht leer, ohne Steuerzeichen, höchstens
       `GRUND_MAX` Zeichen. Sie geht an die Person (Mail und `mein_loeschantrag`)
       und steht am Antrag; ins Audit-Log kommt sie NICHT (Art. 9 DSGVO).
    3. Mailversand muss eingerichtet sein — sonst wird NICHTS abgelehnt
       (fail closed, wie beim Bestätigen). Ohne hinterlegte Adresse ebenfalls
       nicht: die Person muss die Begründung erhalten.
    4. Status + Begründung + Zeitpunkt + Administrator setzen, `flush`, DANN die
       Mail, dann der Commit. Scheitert der Versand, rollt alles zurück und der
       Antrag bleibt `offen` — erneut versuchbar.

    Danach darf die Person sofort einen neuen Antrag stellen
    (`loeschung_beantragen` setzt ihn wieder auf `offen`).
    """
    _require_admin()
    _post(request)
    if bestaetigt is not True:
        raise ValidationError("Bitte die Ablehnung bestätigen.")
    grund = _pruefe_begruendung(begruendung)

    from diakronos_app import mailversand
    from diakronos_app.db import SessionLocal

    with SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        person = _person(s, mitglied_id)
        a = s.get(Loeschantrag, mitglied_id)
        if a is None or (a.status or STATUS_OFFEN) != STATUS_OFFEN or a.erledigt_am:
            raise ValidationError(
                "Es liegt kein offener Löschantrag vor — es gibt nichts abzulehnen."
            )
        if str(person.status or "") == "geloescht":
            raise ValidationError(
                "Diese Person ist bereits gelöscht — der Antrag ist abgeschlossen."
            )
        konten = _verwaltungs_konten(person)
        if konten:
            s.scalars(select(User).where(User.name.in_(sorted(konten)))
                      .order_by(User.name).with_for_update()).all()
        _pruefe_loeschberechtigung(konten)

        adresse = str(person.email or "").strip()
        if not adresse:
            raise ValidationError(
                "Für diese Person ist keine E-Mail-Adresse hinterlegt — ohne Mail "
                "kann der Antrag nicht abgelehnt werden."
            )
        if not mailversand.ist_konfiguriert():
            # N3: derselbe neutrale Text wie beim Bestätigen.
            raise ValidationError(mailversand.NICHT_EINGERICHTET)

        jetzt = datetime.utcnow()
        a.status = STATUS_ABGELEHNT
        a.abgelehnt_am = jetzt
        a.abgelehnt_von = session.user
        a.ablehnung_grund = grund
        # Die In-App-Meldung „Löschantrag gestellt“ liegt noch in den Postfächern
        # der Verwaltung; sie ist erledigt und wird abgeräumt (wie beim
        # Zurückziehen) — sonst stünde dort weiter ein offener Antrag. Vor dem
        # Protokolleintrag, damit nicht auch der als „Meldung“ gilt.
        _raeume_meldung_an_verwaltung_ab(s, person.name)
        # Protokoll OHNE Begründungstext: der kann Gesundheitsdaten enthalten,
        # und das Audit-Log ist einseh- und exportierbar.
        s.add(AuditLog(
            name=uuid4().hex, actor=session.user, zeitstempel=jetzt,
            action_typ="Loeschantrag abgelehnt", target_doctype="Mitglied",
            target_name=person.name,
            consequence="Antrag abgelehnt, keine Daten gelöscht; Person per Mail informiert",
        ))
        gemeinde = mailversand._gemeindename()
        # Der SAVEPOINT spannt Status, Protokoll UND den Versand: erst der
        # Flush (hier treten Constraint-Fehler auf), dann die Mail, dann der
        # Commit des SAVEPOINTS. Scheitert der Versand, wird NUR dieser Teil
        # zurückgenommen — der Antrag bleibt `offen` und die Ablehnung ist
        # erneut versuchbar. Der Stand wird davor gelesen, denn nach dem
        # Zurücknehmen ist er nicht mehr der, der zurückgegeben werden soll.
        stand = _antrag_stand(a)
        probe = s.begin_nested()
        try:
            s.flush()
            mailversand.sende_ablehnung(adresse, grund, gemeinde=gemeinde)
            probe.commit()
        except mailversand.MailNichtEingerichtet as ex:
            probe.rollback()
            raise ValidationError(str(ex)) from None
        except mailversand.MailVersandFehler as ex:
            probe.rollback()
            raise ValidationError(
                f"{ex} Es wurde nichts abgelehnt — der Antrag bleibt offen, bitte "
                "erneut versuchen."
            ) from None

    return {**(stand or {}), "ok": True}


def _pruefe_begruendung(begruendung) -> str:
    """Die Begründung der Ablehnung prüfen und zurückgeben (DSGVO-2a).

    Pflicht, nicht leer, ohne Steuerzeichen des C0-Bereichs (Ausnahme: TAB und
    Zeilenumbrüche, die in einem mehrzeiligen Freitext gewollt sind), höchstens
    `GRUND_MAX` Zeichen. Geprüft wird der Text NACH dem Trimmen — eine
    Begründung aus Leerzeichen ist keine.
    """
    if not isinstance(begruendung, str):
        raise ValidationError("Bitte eine Begründung für die Ablehnung angeben.")
    text = begruendung.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValidationError(
            "Bitte eine Begründung für die Ablehnung angeben — die Person erhält "
            "sie per E-Mail."
        )
    if any(zeichen in text for zeichen in _STEUERZEICHEN):
        raise ValidationError(
            "Die Begründung enthält unerlaubte Steuerzeichen. Bitte nur normalen "
            "Text eingeben."
        )
    if len(text) > GRUND_MAX:
        raise ValidationError(
            f"Die Begründung ist zu lang ({len(text)} Zeichen). Bitte auf "
            f"höchstens {GRUND_MAX} Zeichen kürzen."
        )
    return text


#: Steuerzeichen, die in einem Freitext NICHTS zu suchen haben. TAB und
#: Zeilenumbruch bleiben erlaubt — sie sind Teil normaler Absätze.
_STEUERZEICHEN = frozenset(chr(i) for i in range(0x20) if chr(i) not in "\t\n") | {"\x7f"}


@whitelist(allow_guest=False)
def get_loeschantraege(status=""):
    """Offene Löschanträge für die Verwaltung (D2), älteste zuerst.

    `status` filtert optional (``offen`` / ``zurueckgezogen`` / ``ausgefuehrt``);
    ohne Angabe werden die OFFENEN geliefert — das ist die Arbeitsliste.
    Anzeigename und Adresse kommen mit, damit der Administrator erkennt, wen er
    löscht; nach der Ausführung sind beide „Gelöschte Person“ bzw. leer.
    """
    _require_admin()
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import NotificationLog
    from diakronos_app.models.diakonos import Mitglied as _M

    gewuenscht = str(status or STATUS_OFFEN).strip().lower()
    if gewuenscht not in STATUS_WERTE + ("alle", ""):
        raise ValidationError("Unbekannter Status für die Antragsliste.")
    with SessionLocal() as s:
        abfrage = select(Loeschantrag, Mitglied).join(
            Mitglied, Mitglied.name == Loeschantrag.mitglied
        ).order_by(Loeschantrag.beantragt_am)
        if gewuenscht and gewuenscht != "alle":
            # Bestandszeilen aus N6 haben noch keinen Status; sie wurden von der
            # Migration auf 'offen'/'ausgefuehrt' gesetzt, der Rueckfall auf
            # `erledigt_am` deckt eine DB ohne die Migration (Tests) ab.
            if gewuenscht == STATUS_OFFEN:
                abfrage = abfrage.where(or_(
                    Loeschantrag.status == STATUS_OFFEN,
                    and_(Loeschantrag.status.is_(None), Loeschantrag.erledigt_am.is_(None)),
                ))
            else:
                abfrage = abfrage.where(Loeschantrag.status == gewuenscht)
        return [
            {
                **(_antrag_stand(a) or {}),
                # Nur für die Verwaltung: wer hat abgelehnt (Beschäftigtendatum,
                # nicht Teil der Antwort an die Person — `_antrag_stand`).
                "abgelehnt_von": a.abgelehnt_von,
                "vorname": m.vorname or "",
                "nachname": m.nachname or "",
                "email": m.email or "",
                "konto": m.user or "",
            }
            for a, m in s.execute(abfrage).all()
        ]


@whitelist(allow_guest=False)
def anonymisieren(mitglied_id, bestaetigt=False, bestaetigung='', nur_antrag=False, request=None):
    """Löschung NUR über Antrag → Bestätigung → Mail (N-5, D4).

    Der frühere Bestandsweg anonymisierte ohne Antrag und ohne Mail. Das
    widerspricht der Fachentscheidung („das Mitglied stellt den Antrag, ein
    Administrator bestätigt, dann geht die Mail raus, dann wird gelöscht“).
    Der Endpunkt bleibt für die Oberfläche N6 erreichbar, führt aber HART auf
    `loeschung_bestaetigen`: ohne bestätigten Antrag wird nichts gelöscht, und
    für die Meldung ist immer `loeschung_bestaetigen` zuständig.

    `nur_antrag=False` ändert daran nichts — die Unterscheidung ist entfallen.
    """
    _require_admin()
    _post(request)
    if bestaetigt is not True or bestaetigung != 'ANONYMISIEREN':
        raise ValidationError("Bitte beide Rückfragen bestätigen und ANONYMISIEREN eingeben.")
    if not isinstance(nur_antrag, bool):
        raise ValidationError("Ungültige Antragsauswahl.")
    from diakronos_app.db import SessionLocal

    with SessionLocal() as s:
        # Reihenfolge wie bisher: erst die Rechte (403), dann der Antrag (417).
        person = _person(s, mitglied_id)
        _pruefe_loeschberechtigung(_verwaltungs_konten(person))
        a = s.get(Loeschantrag, mitglied_id)
        offen = a is not None and (a.status or STATUS_OFFEN) == STATUS_OFFEN and not a.erledigt_am
    if not offen:
        raise ValidationError(
            "Für diese Person liegt kein offener Löschantrag vor. Löschungen "
            "laufen ausschließlich über einen Antrag: Das Mitglied stellt ihn, "
            "ein Administrator bestätigt ihn — dabei geht die Meldung an die "
            "Person raus, danach wird vollständig anonymisiert."
        )
    # Hart auf den Antragsweg: gleiche Anonymisierung, aber MIT Meldung (D4).
    return loeschung_bestaetigen(mitglied_id, bestaetigt=True, request=request)
