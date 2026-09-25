from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel

DataT = TypeVar("DataT")


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


class DataResponse(BaseModel, Generic[DataT]):
    data: DataT
    message: Optional[str] = None


class PaginatedResponse(BaseModel, Generic[DataT]):
    items: List[DataT]
    total: int
    page: int
    page_size: int
    total_pages: int
