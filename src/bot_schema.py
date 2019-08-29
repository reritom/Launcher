import json
from typing import List
from dataclasses import dataclass

@dataclass
class BotSchema:
    """
    A BotSchema defines a bot model and the parameters of the bot, but doesn't represent an instance of a bot
    """
    model: str # The name of this type of bot
    bot_type: str # Enum, operator or refueler, basically a description if this bot model is tailored to certain activities
    flight_time: int # Average flight time in seconds
    speed: int # Average speed in meters per second
    cruising_altitude: int

    @classmethod
    def from_dict(cls, bot_dict: dict) -> 'Bot':
        instance = cls(
            model=bot_dict['model'],
            bot_type=bot_dict['type'],
            flight_time=bot_dict['flight_time'],
            speed=bot_dict['speed'],
            cruising_altitude=bot_dict['cruising_altitude']
        )

        return instance

    @property
    def is_refueler(self):
        return self.bot_type.lower() == "refueler"

    def to_dict(self) -> dict:
        return {
            'flight_time': self.flight_time,
            'speed': self.speed,
            'type': self.bot_type,
            'model': self.model,
            'cruising_altitude': self.cruising_altitude
        }
