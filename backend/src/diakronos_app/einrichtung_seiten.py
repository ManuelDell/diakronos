"""ON-1 — die server-gerenderten Seiten der Ersteinrichtung (Entwurf 02, 03, 13).

ZWEI Seiten, EIN Rahmen
-----------------------
  * ``seite_anlegen(...)``  — „Administrator anlegen" (Entwurf 02, mobil 13)
  * ``seite_ungueltig(...)`` — „Dieser Einrichtungslink ist nicht mehr gültig"
    (Entwurf 03)

Gestaltung kommt AUSSCHLIESSLICH aus ``tokens.css`` und dem gemeinsamen
Grund-Stylesheet ``frontend/src/ssot/seiten.css``; der ``<head>``-Block wird von
``anmeldung/seitenrahmen.head_block()`` gebaut (praefixbewusst, ON-0a). In
dieser Datei steht deshalb KEIN Farbwert, keine Schriftfamilie und kein
Radius — der Wächter ``backend/tests/test_on0a_css_ssot.py`` prueft das.

Was hier NICHT steht: Fachlogik. Pruefen, Anlegen und Verbrauchen macht
``einrichtung.routen``; dieses Modul liefert nur Markup.
"""

from __future__ import annotations

import html

from diakronos_app.anmeldung import seitenrahmen

__all__ = ["seite_anlegen", "seite_ungueltig", "EINRICHTUNGSLINK_BEFEHL"]

#: Der Befehl zum Neuerzeugen — EIN Text fuer Konsole (``erstinstallation``)
#: und Seite. Die Seite darf ihn nicht aus dem Konsolenmodul importieren
#: (Ringbezug: ``erstinstallation`` importiert ``einrichtung``, das hier nicht
#: gebraucht wird) — deshalb steht er hier und ``erstinstallation`` liest ihn
#: nicht neu. Die Pruefung auf Gleichheit macht der Test.
EINRICHTUNGSLINK_BEFEHL = "docker compose exec app diakronos einrichtungslink"

# ON-1b (F5): die frueheren Konstanten ``CSP``/``ANTWORT_KOPFZEILEN`` sind
# entfernt. Sie waren toter Code: die Seiten bekommen ihre Kopfzeilen in
# ``anmeldung/einrichtung_routen._EIGENE_KOPFZEILEN``, und die Policy haengt
# zentral ``sec_header`` an (eine zweite Policy im selben Feld waere die
# SCHNITTMENGE und damit unbedienbar — im Abnahme-Lauf gemessen).

#: Der Cursor der Passwortstaerke als Inline-Skript-Daten. Farben kommen aus
#: den Tokens (--ok/--warn/--err/--line), nicht aus JS.
_JS = """
(function () {
  var feld = document.getElementById('passwort');
  var wiederholung = document.getElementById('wiederholung');
  var balken = document.getElementById('staerke');
  var text = document.getElementById('staerke-text');
  var augen = document.querySelectorAll('[data-auge]');

  // ── Fortschritt der Passwortstaerke (Entwurf 02/13: 4/4 = „stark") ────────
  //
  // Stufe 1..4. Gezaehlt werden fünf Merkmale (Groß-/Klein, Zahl,
  // Sonderzeichen, 12 Zeichen, 16 Zeichen). Unter 8 Zeichen ist es Stufe 1.
  // „EinSicheres12" (13 Zeichen, Groß-/Kleinbuchstaben, Zahl) erreicht drei
  // Merkmale — „stark" (4/4) ist einem Passwort mit vier Merkmalen
  // vorbehalten.
  function stufe(wert) {
    if (!wert) return 0;
    var merkmale = 0;
    if (/[a-z]/.test(wert) && /[A-Z]/.test(wert)) merkmale += 1;
    if (/[0-9]/.test(wert)) merkmale += 1;
    if (/[^A-Za-z0-9]/.test(wert)) merkmale += 1;
    if (wert.length >= 12) merkmale += 1;
    if (wert.length >= 16) merkmale += 1;
    if (wert.length < 8) return 1;
    if (merkmale >= 4) return 4;
    if (merkmale === 3) return 3;
    return 2;
  }

  function zeichne() {
    var s = stufe(feld.value || '');
    var namen = ['', 'schwach', 'mittel', 'gut', 'stark'];
    if (balken) {
      balken.setAttribute('data-stufe', String(s));
      balken.hidden = s === 0;
    }
    if (text) {
      text.textContent = s === 0 ? '' : namen[s];
      text.setAttribute('data-stufe', String(s));
      text.hidden = s === 0;
    }
  }

  if (feld) { feld.addEventListener('input', zeichne); zeichne(); }

  for (var i = 0; i < augen.length; i++) {
    augen[i].addEventListener('click', function () {
      var ziel = document.getElementById(this.getAttribute('data-auge'));
      if (!ziel) return;
      var zeigen = ziel.type === 'password';
      ziel.type = zeigen ? 'text' : 'password';
      this.setAttribute('aria-pressed', zeigen ? 'true' : 'false');
      var beschriftung = zeigen ? 'Passwort verbergen' : 'Passwort anzeigen';
      this.setAttribute('aria-label', beschriftung);
      this.setAttribute('title', beschriftung);
      ziel.focus();
    });
  }
})();
"""


def _kopf() -> str:
    return seitenrahmen.head_block()


def seite_anlegen(*, api: str, login: str, csrf_token: str = "") -> str:
    """Seite „Administrator anlegen" (GET).

    ``api`` ist die Praefix-bewusste POST-Adresse, ``login`` der Weg zur
    Anmeldung. ``csrf_token`` ist der signierte Masken-Token (SEC-4) — ohne ihn
    bliebe das Feld weg; das Formular bleibt dann trotzdem bedienbar (die
    Herkunftspruefung des Servers entscheidet, nicht das Feld).
    """
    api_p = html.escape(api, quote=True)
    login_p = html.escape(login, quote=True)
    csrf = html.escape(csrf_token or "", quote=True)
    csrf_feld = (
        f'\n<input type="hidden" name="_csrf" value="{csrf}">' if csrf else ""
    )
    befehl = html.escape(EINRICHTUNGSLINK_BEFEHL)
    # Absolute Adressen fuer die Weiterleitung nach dem Anlegen setzt der
    # Client (`location.href = ziel`), damit keine Antwort die Praefix-Regel
    # umgeht. Das Ziel selbst kommt vom Server (unten eingefuegt).
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Administrator anlegen — Diakronos</title>
{_kopf()}
</head><body class="dk-seite"><main class="dk-karte dk-karte--breit dk-einrichtung">
<div class="dk-monogramm" aria-hidden="true">D</div>
<p class="dk-marke">Diakronos</p>
<h1>Willkommen bei Diakronos</h1>
<p class="dk-unterzeile">Legen Sie den Systemadministrator an.</p>
<p id="fehler" class="dk-meldung" role="alert" tabindex="-1" hidden></p>
<form id="formular" class="dk-formular" method="post" action="{api_p}" accept-charset="utf-8">{csrf_feld}
<div class="dk-feldpaar">
<div>
<label class="dk-feld" for="vorname">Vorname <span class="dk-pflicht" aria-hidden="true">*</span></label>
<input id="vorname" name="vorname" type="text" autocomplete="given-name" maxlength="140" required>
</div>
<div>
<label class="dk-feld" for="nachname">Nachname <span class="dk-pflicht" aria-hidden="true">*</span></label>
<input id="nachname" name="nachname" type="text" autocomplete="family-name" maxlength="140" required>
</div>
</div>
<label class="dk-feld" for="email">E-Mail-Adresse <span class="dk-pflicht" aria-hidden="true">*</span></label>
<input id="email" name="email" type="email" autocomplete="email" maxlength="320" required
       autocapitalize="none" autocorrect="off" spellcheck="false">
<label class="dk-feld" for="passwort">Passwort <span class="dk-pflicht" aria-hidden="true">*</span></label>
<div class="dk-eingabe">
<input id="passwort" name="passwort" type="password" autocomplete="new-password"
       minlength="8" maxlength="1024" required class="dk-passwort">
<button type="button" class="dk-auge" data-auge="passwort"
        aria-controls="passwort" aria-pressed="false"
        aria-label="Passwort anzeigen" title="Passwort anzeigen">&#x25C9;</button>
</div>
<div id="staerke" class="dk-staerke" data-stufe="0" aria-hidden="true" hidden>
<span></span><span></span><span></span><span></span>
</div>
<p id="staerke-text" class="dk-staerke-text" data-stufe="0" role="status" hidden></p>
<p class="dk-hinweis dk-hinweis--eng">Mindestens 12 Zeichen, ein Großbuchstabe und eine Zahl.</p>
<label class="dk-feld" for="wiederholung">Passwort wiederholen <span class="dk-pflicht" aria-hidden="true">*</span></label>
<div class="dk-eingabe">
<input id="wiederholung" name="wiederholung" type="password" autocomplete="new-password"
       minlength="8" maxlength="1024" required>
<button type="button" class="dk-auge" data-auge="wiederholung"
        aria-controls="wiederholung" aria-pressed="false"
        aria-label="Passwort anzeigen" title="Passwort anzeigen">&#x25C9;</button>
</div>
<button id="anlegen" class="dk-knopf dk-knopf-weit" type="submit">Administrator anlegen</button>
</form>
<p class="dk-hinweis dk-hinweis--mitte">Dieser Link ist danach ungültig.</p>
<p class="dk-hinweis dk-hinweis--mitte dk-hinweis--klein">Neuen Link erzeugen:
<code class="dk-befehl">{befehl}</code></p>
</main>
<footer class="dk-seitenfuss">Diakronos · Ersteinrichtung</footer>
<script>{_JS}</script>
</body></html>"""


def seite_ungueltig(*, login: str, status_fehler: str = "") -> str:
    """Seite „Link ungültig" (Entwurf 03).

    Bewusst EIN Text fuer „nie gueltig", „abgelaufen" und „Einrichtung schon
    abgeschlossen" — kein Orakel, das verraten wuerde, ob es den Token je gab
    (Karte E3). ``status_fehler`` ist der Klartext fuer eine abgelehnte
    Absendung (Validierung/CSRF/Bremse) und bleibt leer, wenn die Seite auf
    einen ungueltigen Link antwortet.
    """
    login_p = html.escape(login, quote=True)
    befehl = html.escape(EINRICHTUNGSLINK_BEFEHL)
    fehler = (
        f'\n<p class="dk-meldung" role="alert" tabindex="-1">{html.escape(status_fehler)}</p>'
        if status_fehler
        else ""
    )
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Link ungültig — Diakronos</title>
{_kopf()}
</head><body class="dk-seite"><main class="dk-karte dk-karte--breit dk-einrichtung">
<div class="dk-warnzeichen" aria-hidden="true">!</div>
<h1 class="dk-mitte">Dieser Einrichtungslink ist nicht mehr gültig</h1>{fehler}
<p class="dk-unterzeile dk-mitte">Ein Einrichtungslink lässt sich genau einmal verwenden und
verfällt nach 7 Tagen. Wurde bereits ein Systemadministrator
angelegt, ist die Ersteinrichtung abgeschlossen.</p>
<hr class="dk-trenner">
<h2 class="dk-abschnitt">Neuen Link erzeugen</h2>
<p class="dk-hinweis dk-hinweis--eng">Auf dem Server ausführen:</p>
<p><code class="dk-befehl dk-befehl--breit">{befehl}</code></p>
<h2 class="dk-abschnitt">Bereits eingerichtet?</h2>
<p><a class="dk-knopf" href="{login_p}">Zur Anmeldung</a></p>
<p class="dk-hinweis dk-hinweis--eng">oder wenden Sie sich an Ihren Administrator.</p>
</main>
<footer class="dk-seitenfuss">Diakronos · Ersteinrichtung</footer>
</body></html>"""
