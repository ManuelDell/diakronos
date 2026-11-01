"""Öffentliche Passwort-Seite: kein Boot mit Personendaten, keine Fremdanfragen.

ON-0a: Farben, Schriften und Formen kommen AUSSCHLIESSLICH aus
`frontend/src/diakonos/tokens.css` und dem gemeinsamen Grund-Stylesheet
`frontend/src/ssot/seiten.css`. Der `<head>`-Block wird von
`anmeldung/seitenrahmen.py` gebaut (präfixbewusst) — hier steht KEIN
Farbwert und keine Schriftfamilie mehr.
"""
import html

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/diakonos/passwort-setzen", include_in_schema=False)
def passwort_seite():
    # WEB-5a: die Seite baut ihre Adressen (API, Login-Link) mit dem
    # Betriebs-Praefix. Reine HTML-Platzhalter — kein Nutzerinhalt, deshalb
    # direkt eingesetzt und escaped. Die Route selbst bleibt app-eigen; der
    # Praefix kommt vom Mount.
    from diakronos_app import base_path
    from diakronos_app.anmeldung import seitenrahmen

    api = html.escape(base_path.pfad("/api/method/zugang.passwort_uebernehmen"), quote=True)
    login = html.escape(base_path.pfad("/login"), quote=True)
    seite = (
        _SEITE.replace("__API__", api)
        .replace("__LOGIN__", login)
        .replace("__HEAD__", seitenrahmen.head_block())
    )
    return HTMLResponse(seite, headers={
        "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        # ON-0a: kein Inline-<style> mehr -> `style-src` braucht nur die
        # eigene Adresse (die zwei Build-Dateien). Das Inline-SKRIPT bleibt.
        # ON-0b (F3): `font-src 'self'` ergänzt — ohne diese Quelle verweigerte
        # `default-src 'none'` die Schriftdateien der Token-Datei, und die Seite
        # fiel auf die Systemschrift zurück (im Netzwerkprotokoll als
        # geblockte Anfrage sichtbar).
        "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'self'; font-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    })


_SEITE = '''<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Passwort setzen — Diakronos</title>
__HEAD__
</head><body class="dk-seite"><main class="dk-karte dk-karte--breit">
<h1>Passwort setzen</h1>
<p class="dk-unterzeile">Lege dein eigenes Passwort für Diakronos fest. Ein Startpasswort muss dabei durch ein anderes Passwort ersetzt werden.</p>
<p id="fehler" class="dk-meldung" role="alert" tabindex="-1" hidden></p>
<form id="formular" class="dk-formular">
<label class="dk-feld" for="passwort">Neues Passwort (mindestens 8 Zeichen)</label>
<input id="passwort" type="password" autocomplete="new-password" minlength="8" maxlength="1024" required>
<label class="dk-feld" for="wiederholung">Passwort wiederholen</label>
<input id="wiederholung" type="password" autocomplete="new-password" minlength="8" maxlength="1024" required>
<button id="speichern" class="dk-knopf dk-knopf-weit" type="submit">Passwort speichern</button>
</form>
<p id="erfolg" role="status" hidden>Dein Passwort wurde gespeichert. <a href="__LOGIN__">Jetzt anmelden</a></p>
<script>
const token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
history.replaceState(null, '', location.pathname);
// Ein anderer persönlicher Link im selben Tab ist sonst nur ein
// Fragmentwechsel; dann muss auch das neue Token eingelesen werden.
window.addEventListener('hashchange', () => { if (location.hash) location.reload(); });
const formular = document.getElementById('formular');
const fehler = document.getElementById('fehler');
const knopf = document.getElementById('speichern');
function melden(text) { fehler.textContent = text; fehler.hidden = false; fehler.focus(); }
if (!token) { formular.hidden = true; melden('Dieser Link ist nicht mehr gültig. Bitte frage bei der Gemeinde nach einem neuen Link.'); }
formular.addEventListener('submit', async (event) => {
  event.preventDefault();
  const passwort = document.getElementById('passwort');
  const wiederholung = document.getElementById('wiederholung');
  if (passwort.value !== wiederholung.value) { melden('Die Passwörter stimmen nicht überein.'); wiederholung.focus(); return; }
  knopf.disabled = true; knopf.textContent = 'Wird gespeichert…'; fehler.hidden = true;
  try {
    const antwort = await fetch('__API__', {
      method: 'POST', credentials: 'omit', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, passwort: passwort.value }),
    });
    const daten = await antwort.json();
    if (!antwort.ok) throw new Error(daten.message || 'Das Passwort konnte nicht gespeichert werden.');
    passwort.value = ''; wiederholung.value = ''; formular.hidden = true;
    document.getElementById('erfolg').hidden = false;
    document.querySelector('#erfolg a').focus();
  } catch (error) { melden(error.message || 'Bitte versuche es erneut.'); }
  finally { knopf.disabled = false; knopf.textContent = 'Passwort speichern'; }
});
</script></main></body></html>'''
