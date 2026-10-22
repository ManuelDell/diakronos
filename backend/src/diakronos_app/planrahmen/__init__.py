"""Plan-Rahmen — generischer Rahmen fuer beliebige Gemeinde-Plaene.

Die zentrale Idee (Konzept ``doku/KONZEPT.md``): *wenige Grundbausteine,
frei kombinierbar* — ein Chorplan, ein Freizeitplan oder ein Predigerplan sind
nur *Beispiele* fuer die gleiche Komposition aus Terminen, Feldern, Rollen,
Sammlungen, Merkmalen, Regeln und Ansichten, nicht eingebaute Sonderfaelle.

Bausteine dieses Pakets: Plantyp-Schema und Pruefung (``schema/``,
``pruefung.py``), Regel-Registry (``regeln/``), Struktur-Pruefung von
Instanzdaten (``eintraege.py``), erzeugte Referenz (``referenz.py``), Doku und
Kochbuch (``doku/``) sowie die Speicherschicht fuer die ``pr_*``-Tabellen
(``speicher.py``). Eigener, sauberer Code — keine Frappe-Doctype-Muster.
"""

from __future__ import annotations
