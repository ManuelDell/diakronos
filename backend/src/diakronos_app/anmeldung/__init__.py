"""Anmelde-Anbieter (SEC1) — OIDC + optional Forward-Auth-Kopfzeilen.

Paketaufteilung:

  ``konfiguration``  — wirksame Einstellungen + Startpruefung (fail fast).
  ``oidc``           — Discovery, JWKS, Token-Pruefung, Authorization-Code-Flow.
  ``transaktionen``  — serverseitiger state/nonce/PKCE-Speicher (Redis).
  ``zuordnung``      — (issuer, sub)/E-Mail -> Diakronos-Benutzer, unbekannte-
                       Nutzer-Modi, Gruppen->Rollen.
  ``proxy_header``   — Forward-Auth-Kopfzeilen (TEIL B).
  ``middleware``     — Forward-Auth-Middleware (setzt den Benutzer aus Kopfzeilen).
  ``einstellungen_api`` — Admin-Endpunkte fuer das unbekannte-Nutzer-Verhalten.
  ``routen``         — /login, /auth/oidc/*, /logout.

Sprache: Deutsch. Keine Geheimnisse in Logs.
"""

from __future__ import annotations

__all__ = ["konfiguration", "oidc", "transaktionen", "zuordnung", "proxy_header"]
