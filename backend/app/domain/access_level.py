from dataclasses import dataclass


@dataclass(frozen=True)
class AccessLevel:
    id: str
    title: str
