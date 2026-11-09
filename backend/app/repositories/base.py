"""Generic repository: thin persistence layer over a SQLAlchemy session."""

from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class Repository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, id_: uuid.UUID) -> ModelT | None:
        return self.session.get(self.model, id_)

    def get_or_404(self, id_: uuid.UUID) -> ModelT:
        obj = self.get(id_)
        if obj is None:
            raise NotFoundError(f"{self.model.__name__} not found")
        return obj

    def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        self.session.flush()
        return obj

    def delete(self, obj: ModelT) -> None:
        self.session.delete(obj)
        self.session.flush()

    def paginate(self, stmt: Select[Any], limit: int, offset: int) -> tuple[list[Any], int]:
        total = self.session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
        rows = list(self.session.scalars(stmt.limit(limit).offset(offset)))
        return rows, int(total or 0)
