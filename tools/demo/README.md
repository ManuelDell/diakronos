# Demo-Gemeinde „Musterhausen“ — Seed und Screenshots

`musterhausen.py` ist das Seed-Skript: ein Aufruf im app-Container fuellt eine
LEERE Datenbank mit einer glaubwuerdigen, vollstaendig erfundenen Gemeinde —
Mitglieder, Familien, Gruppen, Räume, Kalender mit Terminen ueber zwei Monate,
Lieder, Dienst- und Ablaufplaene sowie Plan-Rahmen-Plaene aus den
Kochbuch-Vorlagen. Zwei Konten werden angelegt (Administrator und Mitglied).

```
python tools/demo/musterhausen.py              # anlegen (idempotent)
python tools/demo/musterhausen.py --pruefen    # nur pruefen
python tools/demo/musterhausen.py --entfernen  # wieder entfernen
```

Das Skript arbeitet ausschliesslich ueber die echten Modelle und Dienste der
App und verweigert eine Datenbank, die bereits Mitglieder enthaelt — es kann
also nicht versehentlich in eine Betriebsdatenbank schreiben.

Die Beispieltermine liegen um den Stichtag herum (Vorgabe: `2026-11-02`,
ueber `DIAKRONOS_DEMO_STICHTAG` oder `--stichtag` einstellbar). Alle Namen,
Adressen, Telefonnummern und Mailadressen (`…@example.org`) sind erfunden.

## Screenshots

`docs/bilder/v2/` enthaelt die Bilder der README. Sie werden mit
`screenshots.py` gegen genau diesen Demo-Bestand aufgenommen (Aufruf steht im
Kopf der Datei): Desktop 1366x800, Mobil 390x844, Dunkelmodus nur fuer die
Uebersicht.

Der Zugriff laeuft ueber `BASE` (Default `http://app:8000`, also der
App-Dienst im eigenen Compose-Netz); den Compose-Projektnamen fuer Netznamen
und Meldungen setzt `DEMO_PROJEKT` (Default `demo`). Konten kommen aus
`ADMIN_EMAIL`/`ADMIN_PASS` und `MITGLIED_EMAIL`/`MITGLIED_PASS`, das Ziel
aus `ZIEL`.

Die Bilder gehen in ein OEFFENTLICHES Repository: nach dem Lauf pruefen, dass
keine echten Namen und keine internen Adressen im Bild stehen.
