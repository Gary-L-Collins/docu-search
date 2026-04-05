from enum import Enum
from dataclasses import dataclass

class JobType(str, Enum):
    UPLOAD = "upload"
    DELETE = "delete"

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"

class QueryStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"

class SessionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
