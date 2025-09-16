"""Definições de tipos compartilhados no projeto."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class MensagemDetalhada:
    """Representa o texto da mensagem e os motivos relacionados."""

    texto: str
    motivos: List[str]
