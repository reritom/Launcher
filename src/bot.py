import json
from typing import List

class Bot:
    @classmethod
    def from_dict(cls, bot_dict: dict) -> 'Bot':
        instance = cls(
            model=bot_dict['model'],
            bot_type=bot_dict['type'],
            flight_time=bot_dict['flight_time'],
            speed=bot_dict['speed']
        )

        return instance

    @classmethod
    def from_catalogue_file(cls, file_path: str) -> List['Bot']:
        """
        A catalogue file is a file containing a list of bot definitions
        """
        with open(file_path, 'r') as f:
            catalogue = json.load(f)

        return [
            cls.from_dict(bot_dict)
            for bot_dict in catalogue
        ]

    def __init__(self, flight_time: int, speed: int, bot_type: str, model: str):
        self.flight_time = flight_time
        self.speed = speed
        self.bot_type = bot_type
        self.model = model

    @property
    def is_refueler(self):
        return self.bot_type.lower() == "refueler"

    def to_dict(self) -> dict:
        return {
            'flight_time': self.flight_time,
            'speed': self.speed,
            'type': self.bot_type,
            'model': self.model
        }
