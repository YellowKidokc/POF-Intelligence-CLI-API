"""Provider contracts and shared response types."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator


@dataclass
class ProviderResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class Provider(ABC):
    @abstractmethod
    def call(self, messages: list[dict], model: str, temperature: float, max_tokens: int) -> ProviderResponse: ...

    @abstractmethod
    def stream(self, messages: list[dict], model: str, temperature: float, max_tokens: int) -> Iterator[str]: ...

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> dict: ...

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Return embeddings, when supported by the provider."""
        raise NotImplementedError(f"{type(self).__name__} does not support embeddings")
