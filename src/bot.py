from dataclasses import dataclass

from .bot_schema import BotSchema

@dataclass
class Bot:
    """
    A bot is a effectively an instance of a BotSchema and is directly related to physical bot resource
    """
    id: str
    schema: BotSchema
