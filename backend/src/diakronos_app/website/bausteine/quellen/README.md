# Bausteine für Primo (Diakronos × Primo)

Diese Bibliothek wird von Diakronos **in die angebundene Primo-Instanz
ausgeliefert** — als ein ZIP über `POST /api/primo/import-library` mit
`expected_revision` (Einzel-API nur als Rückfallebene, siehe BS-0
„Empfohlene Auslieferungsstrategie"). Der Installer heißt
`backend/src/diakronos_app/website/bausteine.py`.

## Aufbau

```
deploy/primo/bausteine/
  VERSION                 Versionsnummer der AUSLIEFERUNG (eine Zahl, ganze Datei)
  <kennung>/              ein Baustein; <kennung> = Verzeichnisname
    block.json            Maschinenlesbar: Anzeigename, Beschreibung, Reihenfolge
    component.svelte      Quelltext (html + <script> + <style>, Primo-Format)
    fields.json           Felddefinitionen mit Vorgabewerten
    README.md             Zweck, Felder, Datenquelle (für Redakteure und Betrieb)
```

`<kennung>` ist ein ASCII-Bezeichner (`[a-z0-9-]+`). Der Baustein heißt in
Primo `diakronos/<kennung>` und liegt in der Gruppe `Diakronos`.

## Regeln, die jeder Baustein einhält

1. **Eigenständig.** Primo kopiert einen Bibliotheksblock beim Einsetzen in
   eine Site; die Kopie lebt danach für sich. Ein Baustein darf deshalb
   NICHTS aus einem anderen Baustein importieren — gemeinsame Hilfslogik steht
   in jedem Baustein noch einmal (bewusst: Lieber kleine Dopplung als ein
   Baustein, der beim Kopieren kaputtgeht).
2. **Keine Gebäude-Farben, keine Namen, keine Bilder im Code.** Beschriftungen
   sind deutsch, aber über Primo-Felder änderbar. Gestaltung ausschließlich
   über `--dk-*`-Custom-Properties, die von den Site-Stilen überschrieben
   werden (BS-0 F5).
3. **`--dk-*` nur LESEN, niemals im Block deklarieren.**
   `--dk-abstand: var(--dk-abstand, 0.75rem)` ist nach CSS-Spezifikation
   ungültig und fällt auf „unset" zurück (BS-0 F5: gemessenes `padding: 0px`).
4. **Daten holen per `fetch` auf eine ABSOLUTE URL**, aus einem Primo-Feld
   („Diakronos-Adresse"). Ein relativer Pfad scheitert im `srcdoc`-iframe des
   Editors (Basis `about:srcdoc`) und damit auch im veröffentlichten Build
   (BS-0 F4).
5. **Client-seitig, nie serverseitig.** Primo rendert beim Publish kein fetch;
   der Block läuft beim Besucher. Alle Besucher teilen sich deshalb keine
   Diakronos-Ratenbremse — jeder Abruf ist eine normale Besucher-Anfrage
   (Karten-Zusatz 2026-11-03).
6. **Erstes Rendering ist ein Lade-/Leerzustand** — die Block-SSR kennt keine
   Daten. Der Inhalt kommt erst im Browser; Fehler werden IM Block sichtbar
   gemacht (nicht in der Editor-Konsole, BS-0 F4 Punkt 3).
7. **Barrierearm:** semantisches HTML, `aria-live` für Zustandswechsel,
   sichtbarer Fokus, Tastaturbedienung, kein Autofokus, kein Autoplay.
8. **Kein externes CDN, keine Google-Fonts.** Einzige Außenverbindung ist die
   Diakronos-Adresse aus dem Feld.

## Datenquelle

Die Bausteine sprechen ausschließlich mit der öffentlichen Lese-API aus BS-1
(`{Diakronos-Adresse}/website/oeffentlich/<funktion>`, Antwort
`{"message": …}`) und — beim Kontaktformular — mit
`{Diakronos-Adresse}/api/method/website.kontakt_senden`. Beide antworten nur,
wenn in Diakronos ausdrücklich freigegeben ist (Freigabe-Prinzip G1).

## Auslieferung

* Beim Übergang in Primo (`website.login_uebergabe`) prüft Diakronos, ob die
  installierte Bibliotheksversion kleiner ist als die mitgelieferte, und
  installiert sie nach. Fehler dort werden **nur protokolliert** und
  verhindern die Anmeldung nicht.
* **In-Prozess-Merker (BS-2a2/F2):** Je Prozess wird eine bestätigt
  installierte Version höchstens EINMAL geprüft. Der erste Übergang liest den
  Stand (Superuser-Anmeldung + Bibliotheks-Export) und schreibt bei Bedarf;
  jeder weitere Übergang im selben Prozess überspringt Prüfung und Export.
  Der Merker gilt nur im Speicher — nach einem Neustart wird neu geprüft.
* Der Stand ist über `website.bausteine_status` abrufbar, das Nachziehen per
  `website.bausteine_installieren`.
* **Bewusst NICHT automatisch:** bereits in Primo-Sites eingesetzte Kopien
  behalten ihren Code. Ein Block, den ein Redakteur angepasst hat, wird nie
  überschrieben (BS-0 F2c).
