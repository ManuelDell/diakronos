"""Lokaler Passwortzugang, bewusst kein generisch zugänglicher DocType."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base


class Passwortzugang(Base):
    __tablename__ = "passwortzugang"

    user: Mapped[str] = mapped_column(String(140), ForeignKey("user.name", ondelete="CASCADE"), primary_key=True)
    wechsel_noetig: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    gueltig_bis: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
