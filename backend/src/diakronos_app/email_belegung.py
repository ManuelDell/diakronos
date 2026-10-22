"""E-Mail-Belegung: Eingabe UND Altbestand normalisiert vergleichen.

FACHENTSCHEIDUNG (Manuel, 2026-10-19): Jede Person braucht eine EIGENE
E-Mail-Adresse — eine Adresse gehoert hoechstens zu EINEM Mitglied
(Familienpostfaecher gibt es nicht mehr). Damit diese Zusage traegt, gilt
ueberall DIESELBE Normalisierung: beim Anlegen, beim Aendern, im Import, in
der oeffentlichen Registrierung und beim Vergleich mit dem Altbestand.

K2 (R-SEC-AUSSCHLUSS-code): Die frueheren Vergleiche normalisierten nur mit
`strip().lower()`. Ein unsichtbares Zeichen (Nullbreiten-Leerzeichen, U+200B)
oder Vollbreite-Zeichen (ｆｕｌｌｗｉｄｔｈ) kam damit als „andere Adresse“
durch: die Adresse stand zweimal da, war fuer die Rechtepruefung nicht mehr
eindeutig, und ein Ausschluss ueber die E-Mail wirkte nicht mehr.
`normalisiere` zieht deshalb vorher NFKC an; `enthaelt_unsichtbare` weist
unsichtbare Zeichen ab, statt sie still zu entfernen.
"""
from __future__ import annotations

import unicodedata

from sqlalchemy import func, or_, select

#: Zeichen, die in einer Adresse nichts zu suchen haben. Sie sind unsichtbar
#: oder zerlegen die Anzeige — damit lassen sich sonst Adressen
#: „verdoppeln“, die fuer das Auge gleich aussehen.
_UNSICHTBAR = (
    "\ufeff",  # Nullbreiten-Leerzeichen ohne Umbruch (BOM)
    "\u200b",  # Nullbreiten-Leerzeichen
    "\u200c",  # Nullbreiten-Nichtverbinder
    "\u200d",  # Nullbreiten-Verbinder
    "\u2060",  # Wortverbinder ohne Umbruch
    "\u00ad",  # weicher Trennstrich
)


def enthaelt_unsichtbare(email) -> bool:
    """Traegt die Adresse ein unsichtbares Zeichen? (K2)"""
    text = str(email or "")
    return any(zeichen in text for zeichen in _UNSICHTBAR)


def normalisiere(email) -> str:
    """E-Mail fuer JEDEN Vergleich normalisieren (NFKC, Leerraum weg, klein).

    Reihenfolge: NFKC (Vollbreite/kompatible Zeichen zusammenziehen), ALLEN
    Unicode-Leerraum entfernen (Leerzeichen, Tab, CR/LF, NBSP, Vollbreite-
    Leerzeichen …), dann kleinschreiben. Kein `casefold()` — die Gemeinde
    behandelt Adressen klein; das ist die eine Regel fuer alle Wege.

    SEC-c: `str.strip()` entfernt nur Leerraum — genau deshalb kam „\\tanna@…“
    am Index (`lower(trim(email))`, trim = nur Leerzeichen) und an
    `strip().lower()` vorbei. In einer Adresse hat Leerraum INNEN nichts zu
    suchen; er wird deshalb ueberall entfernt, nicht nur am Rand.
    """
    text = unicodedata.normalize("NFKC", str(email or ""))
    text = "".join(z for z in text if not _ist_leerraum(z))
    return text.lower()


def _ist_leerraum(zeichen: str) -> bool:
    """Unicode-Leerraum? (`isspace` deckt Tab, CR/LF, NBSP, U+3000 … ab)"""
    return zeichen.isspace() or unicodedata.category(zeichen) == "Zs"


#: Schreibweisen, mit denen im Alltag „keine Adresse“ gemeint ist. Der Betrieb
#: hat ein Mitglied mit E-Mail „-“; ohne diese Liste galt es als Adresse und
#: eine zweite Person mit „-“ wurde als Dublette abgewiesen (K-b).
_PLATZHALTER = frozenset(
    {"-", "--", "---", "–", "—", "n/a", "nv", "keine", "kein", "keine adresse", "none", "null"}
)


def ist_platzhalter(email) -> bool:
    """Steht hier statt einer Adresse nur ein Platzhalter? (K-b)"""
    text = normalisiere(email)
    if not text:
        return False  # leer ist leer — nichts zu ersetzen
    return text in _PLATZHALTER


def _belegung_aus_sitzung(sess, email: str, *, ohne_mitglied: str | None = None,
                          ohne_mitglied_konto: str | None = None):
    """Wie `belegung()`, aber auf einer BESTEHENDEN Sitzung.

    SEC-c: In einem Import-Lauf haengt die Zeile an einem SAVEPOINT. Ein
    Lesehelfer, der eine EIGENE Sitzung oeffnet (`belegung`), kann einen Fehler
    woanders ausloesen — bei SQLite platzt dann der Savepoint („no such
    savepoint“, Regression G1). Der Aufrufer mit Sitzung nutzt deshalb diese
    Funktion; die Regel ist dieselbe.
    """
    from sqlalchemy import select

    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    email = normalisiere(email)
    if not email or ist_platzhalter(email):
        return None
    for name, bestand in sess.execute(
        select(Mitglied.name, Mitglied.email).where(Mitglied.email.is_not(None))
    ).all():
        if ohne_mitglied and name == ohne_mitglied:
            continue
        if normalisiere(bestand) == email:
            return {"doctype": "Mitglied", "name": name}
    eigenes = normalisiere(ohne_mitglied_konto)
    # SEC-d (W4): OHNE `User.email IS NOT NULL`. `anonymisieren` setzt
    # `User.email = None`, der Kontoname bleibt aber die alte Adresse. Eine
    # Adresse, die nur noch im Namen steht, belegt sie weiter — sonst gaelte
    # sie danach als frei und ein neues Konto liefe in eine Schluessel-
    # Kollision (`konto_anlegen`), waehrend `pruefe_mitglied_dublette` sie
    # nicht mehr meldete.
    for konto, konto_email, konto_name in sess.execute(
        select(User.name, User.email, User.full_name)
    ).all():
        anzeige = str(konto)
        if eigenes and anzeige == eigenes:
            continue
        if normalisiere(konto_email) == email or normalisiere(anzeige) == email:
            return {"doctype": "User", "name": anzeige,
                    "full_name": konto_name or "Vorhandenes Konto"}
    return None


def belegung(email: str, *, ohne_mitglied: str | None = None,
             ohne_mitglied_konto: str | None = None):
    """Nur nach einer Berechtigungsprüfung aufrufen; liefert keine Klartextliste.

    `email` wird mit `normalisiere` verglichen, der Bestand ebenfalls — NFKC,
    ohne jeden Leerraum, kleingeschrieben (dieselbe Regel wie beim Schreiben in
    `_normalisiere_mitglied_email`).

    SEC-c: der Bestand wird NICHT mehr in SQL auf `lower(trim(b))` reduziert.
    `trim` kennt Tab/NBSP nicht und NFKC gar nicht — eine Zeile
    „\\tanna@x.org“ galt damit als frei und der Vergleich traf die
    Schreibregel nicht. Stattdessen wird die Adresse jedes Bestandsmitglieds
    mit DERSELBEN Python-Funktion normalisiert.

    `ohne_mitglied` laesst einen Datensatz aus (er findet sich nicht selbst).
    `ohne_mitglied_konto` laesst zusaetzlich dessen EIGENES Benutzerkonto aus —
    ein Mitglied, das auf sein eigenes Konto zeigt, belegt die Adresse nicht
    doppelt.
    """
    from diakronos_app.db import lesesitzung

    with lesesitzung() as sess:
        return _belegung_aus_sitzung(sess, email, ohne_mitglied=ohne_mitglied,
                                     ohne_mitglied_konto=ohne_mitglied_konto)
