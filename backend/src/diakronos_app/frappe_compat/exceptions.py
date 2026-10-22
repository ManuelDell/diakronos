"""Exception-Typen der Compat-Schicht + `throw`.

Der Router uebersetzt jede `FrappeCompatError` in die vertragsgemaesse
Fehlerantwort (HTTP 417, Body `{"message": ..., "exception": ...}`).
"""

from __future__ import annotations


class FrappeCompatError(Exception):
	"""Basisklasse aller Compat-Fehler. Traegt die Frappe-Exc-Klassennamen."""

	# Name, der im Fehlerformat als `exception` erscheint (Frappe-Konvention).
	exc_name = "FrappeError"
	# Frappe nutzt fuer fachliche Fehler 417 (Expectation Failed).
	http_status = 417


class ValidationError(FrappeCompatError):
	exc_name = "ValidationError"


class PermissionError(FrappeCompatError):  # noqa: A001 — bewusst wie in Frappe
	exc_name = "PermissionError"
	http_status = 403


class DoesNotExistError(FrappeCompatError):
	exc_name = "DoesNotExistError"
	http_status = 404


class AuthenticationError(FrappeCompatError):
	"""`frappe.AuthenticationError` — falsche Zugangsdaten -> HTTP 401 (A1b1)."""

	exc_name = "AuthenticationError"
	http_status = 401


class DuplicateEntryError(FrappeCompatError):
	exc_name = "DuplicateEntryError"


def throw(msg: str, exc: type[FrappeCompatError] | FrappeCompatError | None = None) -> None:
	"""Entspricht `frappe.throw(msg, exc)`.

	Wirft immer. Ohne `exc` wird `ValidationError` benutzt (Frappe-Default).
	"""
	exc_cls: type[FrappeCompatError] = ValidationError
	if isinstance(exc, type) and issubclass(exc, FrappeCompatError):
		exc_cls = exc
	elif isinstance(exc, FrappeCompatError):
		exc_cls = type(exc)
	raise exc_cls(str(msg))
