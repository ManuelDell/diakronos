#!/bin/bash
# A1b3 Container-Abnahme: Erstinstallation + CalDAV-Auth gegen echtes Postgres/Redis.
#
# Ablauf: frischer Stack -> Entrypoint legt Admin an -> echter HTTP-Login ->
# get_current_user_context liefert den ECHTEN Benutzer -> CalDAV PROPFIND mit
# denselben Zugangsdaten liefert 207; ohne Zugangsdaten 401.
set -u

APP=a1b3-app
BASE=http://localhost:8000
EMAIL=chef@example.org
PASS=erst-geheim-123
FEHLER=0

sag() { printf '\n=== %s ===\n' "$1"; }
ok()  { printf 'OK   %s\n' "$1"; }
bad() { printf 'FEHL %s\n' "$1"; FEHLER=$((FEHLER+1)); }

sag "1. Auf App warten (Healthcheck)"
for i in $(seq 1 60); do
    if docker exec "$APP" curl -fsS http://localhost:8000/healthz >/tmp/a1b3_health.json 2>/dev/null; then
        break
    fi
    sleep 2
done
cat /tmp/a1b3_health.json 2>/dev/null; echo
python3 - <<'PY' && ok "healthz meldet db+redis ok" || bad "healthz nicht ok"
import json,sys
d=json.load(open('/tmp/a1b3_health.json'))
sys.exit(0 if d.get('db') and d.get('redis') else 1)
PY

sag "2. Entrypoint-Log: Erstinstallation gelaufen?"
docker logs "$APP" 2>&1 | grep -i "erstinstallation" || bad "keine Erstinstallations-Zeile im Log"
docker logs "$APP" 2>&1 | grep -i "Administrator .* angelegt" && ok "Log: Administrator angelegt" || bad "Log: Anlage nicht bestaetigt"

sag "3. Datenbank: genau ein Benutzer, Argon2-Hash, Rollen"
docker exec a1b3-db psql -U diakronos -d diakronos -tAc \
  "select name, enabled, left(password_hash,7) from \"user\";" 2>&1
ANZ=$(docker exec a1b3-db psql -U diakronos -d diakronos -tAc "select count(*) from \"user\";" 2>/dev/null | tr -d ' ')
[ "$ANZ" = "1" ] && ok "genau 1 Benutzer" || bad "Benutzerzahl = $ANZ (erwartet 1)"
HASH=$(docker exec a1b3-db psql -U diakronos -d diakronos -tAc "select left(password_hash,7) from \"user\" where name='$EMAIL';" 2>/dev/null | tr -d ' ')
[ "$HASH" = "\$argon2" ] && ok "Passwort als Argon2-Hash gespeichert" || bad "Hash-Praefix = '$HASH' (erwartet \$argon2)"
docker exec a1b3-db psql -U diakronos -d diakronos -tAc \
  "select role from has_role where parent='$EMAIL' order by role;" 2>&1

sag "4. Echter HTTP-Login"
docker exec "$APP" sh -c "curl -sS -c /tmp/cj.txt -X POST '$BASE/api/method/login' \
  -H 'Content-Type: application/json' -d '{\"usr\":\"$EMAIL\",\"pwd\":\"$PASS\"}'" > /tmp/a1b3_login.json 2>&1
cat /tmp/a1b3_login.json; echo
python3 - <<'PY' && ok "Login 200 + csrf_token + sid-Cookie" || bad "Login fehlgeschlagen"
import json,sys
try: d=json.load(open('/tmp/a1b3_login.json'))
except Exception: sys.exit(1)
sys.exit(0 if d.get('message')=='Logged In' and d.get('csrf_token') else 1)
PY

TOKEN=$(python3 -c "import json;print(json.load(open('/tmp/a1b3_login.json')).get('csrf_token',''))" 2>/dev/null)

sag "5. Falsches Passwort -> abgelehnt"
docker exec "$APP" sh -c "curl -sS -o /dev/null -w '%{http_code}' -X POST '$BASE/api/method/login' \
  -H 'Content-Type: application/json' -d '{\"usr\":\"$EMAIL\",\"pwd\":\"falsch\"}'" 2>&1 | tail -c 200; echo

sag "6. get_current_user_context liefert den ECHTEN Benutzer"
docker exec "$APP" sh -c "curl -sS -b /tmp/cj.txt -X POST \
  '$BASE/api/method/diakronos.diakonos.api.session.get_current_user_context' \
  -H 'Content-Type: application/json' -H 'X-Frappe-CSRF-Token: $TOKEN' -d '{}'" > /tmp/a1b3_ctx.json 2>&1
python3 - <<'PY' && ok "Context: echter User + is_admin" || bad "Context falsch"
import json,sys
raw=open('/tmp/a1b3_ctx.json').read()
try: d=json.loads(raw)
except Exception:
    print(raw[:400]); sys.exit(1)
m=d.get('message',d)
if isinstance(m,str):
    try: m=json.loads(m)
    except Exception: pass
print('user=',m.get('user'),'email=',m.get('user_email'),'is_admin=',m.get('is_admin'),'roles=',m.get('roles'))
sys.exit(0 if m.get('user')=='chef@example.org' and m.get('is_admin') is True else 1)
PY

sag "7. CalDAV: PROPFIND ohne Auth -> 401"
docker exec "$APP" sh -c "curl -sS -o /dev/null -w '%{http_code}' -X PROPFIND '$BASE/dav/'" 2>&1; echo
CODE=$(docker exec "$APP" sh -c "curl -sS -o /dev/null -w '%{http_code}' -X PROPFIND '$BASE/dav/'" 2>/dev/null)
[ "$CODE" = "401" ] && ok "ohne Auth 401" || bad "ohne Auth = $CODE (erwartet 401)"

sag "8. CalDAV: PROPFIND mit den ERST-ADMIN-Zugangsdaten -> 207"
CODE=$(docker exec "$APP" sh -c "curl -sS -u '$EMAIL:$PASS' -o /tmp/dav.xml -w '%{http_code}' -X PROPFIND '$BASE/dav/'" 2>/dev/null)
echo "HTTP $CODE"
[ "$CODE" = "207" ] && ok "CalDAV-Auth gegen echte user-Tabelle" || bad "CalDAV = $CODE (erwartet 207)"
head -c 300 /tmp/dav.xml 2>/dev/null; echo

sag "9. CalDAV: falsches Passwort -> 401"
CODE=$(docker exec "$APP" sh -c "curl -sS -u '$EMAIL:falsch' -o /dev/null -w '%{http_code}' -X PROPFIND '$BASE/dav/'" 2>/dev/null)
[ "$CODE" = "401" ] && ok "falsches Passwort 401" || bad "falsches Passwort = $CODE (erwartet 401)"

sag "10. Neustart: Erstinstallation ist idempotent"
docker restart "$APP" >/dev/null 2>&1
for i in $(seq 1 60); do docker exec "$APP" curl -fsS http://localhost:8000/healthz >/dev/null 2>&1 && break; sleep 2; done
ANZ2=$(docker exec a1b3-db psql -U diakronos -d diakronos -tAc "select count(*) from \"user\";" 2>/dev/null | tr -d ' ')
[ "$ANZ2" = "1" ] && ok "nach Neustart weiterhin 1 Benutzer" || bad "nach Neustart $ANZ2 Benutzer (erwartet 1)"

printf '\n=== ERGEBNIS: %s Fehler ===\n' "$FEHLER"
exit $FEHLER