from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class IngestionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SenderType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
