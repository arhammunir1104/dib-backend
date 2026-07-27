from abc import ABC, abstractmethod
from typing import Any

class BaseAgent(ABC):
    @abstractmethod
    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Process the current state and return updated state."""
        pass