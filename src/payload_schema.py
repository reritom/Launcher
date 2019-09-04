from dataclasses import dataclass
from typing import List

from .bot_schema import BotSchema

@dataclass
class PayloadSchema:
    """
    A payload schema defined the payload and the compatable bots for transportation of the payload.
    It isn't a payload in itself
    """
    model: str
    compatable_bots: List[BotSchema]
