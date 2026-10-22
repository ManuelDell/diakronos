"""Gemeinsame DeclarativeBase fuer alle ORM-Modelle.

GENERIERT von tools/gen_models.py — nicht von Hand bearbeiten.
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Basisklasse aller Diakronos-Modelle (Frappe-String-PK bleibt erhalten)."""
