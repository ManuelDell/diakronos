"""Öffentliche Passwort-Seite: kein Boot mit Personendaten, keine Fremdanfragen."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/diakonos/passwort-setzen", include_in_schema=False)
def passwort_seite():
    return HTMLResponse(_SEITE, headers={
        "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    })


_SEITE = '''<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Passwort setzen — Diakronos</title>
<style>
:root { color-scheme: light dark; --bg: #f5f6f8; --surface: #fff; --text: #1f2430; --muted: #5b6474; --primary: #2f5d8a; --line: #d3d8e0; --err: #b42318; }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 1rem; font: 1rem/1.5 system-ui,sans-serif; background: var(--bg); color: var(--text); }
main { width: 100%; max-width: 28rem; padding: 1.5rem; background: var(--surface); border: 1px solid var(--line); border-radius: .75rem; }
h1 { font-size: 1.4rem; margin: 0 0 .5rem; } p { color: var(--muted); }
label { display: block; margin-top: 1rem; }
input,button { width: 100%; font: inherit; border-radius: .5rem; padding: .75rem; }
input { border: 1px solid var(--line); color: var(--text); background: var(--surface); }
button { margin-top: 1.25rem; border: 0; background: var(--primary); color: var(--surface); cursor: pointer; }
:focus-visible { outline: 2px solid var(--primary); outline-offset: 3px; }
[hidden] { display: none !important; } #fehler { color: var(--err); } a { color: var(--primary); }
@media(prefers-color-scheme:dark) { :root { --bg: #14171d; --surface: #1d212a; --text: #e8eaee; --muted: #abb4c4; --line: #333a47; --primary: #8ab7e4; --err: #ffb4ab; } button { color: var(--bg); } }
</style></head><body><main>
<h1>Passwort setzen</h1>
<p>Lege dein eigenes Passwort für Diakronos fest. Ein Startpasswort muss dabei durch ein anderes Passwort ersetzt werden.</p>
<p id="fehler" role="alert" tabindex="-1" hidden></p>
<form id="formular">
<label for="passwort">Neues Passwort (mindestens 8 Zeichen)</label>
<input id="passwort" type="password" autocomplete="new-password" minlength="8" maxlength="1024" required>
<label for="wiederholung">Passwort wiederholen</label>
<input id="wiederholung" type="password" autocomplete="new-password" minlength="8" maxlength="1024" required>
<button id="speichern" type="submit">Passwort speichern</button>
</form>
<p id="erfolg" role="status" hidden>Dein Passwort wurde gespeichert. <a href="/login">Jetzt anmelden</a></p>
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
    const antwort = await fetch('/api/method/zugang.passwort_uebernehmen', {
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
