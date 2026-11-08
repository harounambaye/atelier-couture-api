from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Réponse paginée : {"items": [...], "total": n, "limit": n, "offset": n}."""

    items: list[T]
    total: int
    limit: int
    offset: int
