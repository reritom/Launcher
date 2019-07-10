class Bot:
    @classmethod
    def from_dict(cls, bot_dict: dict) -> 'Bot':
        instance = cls(
            flight_time=bot_dict['flight_time'],
            speed=bot_dict['speed']
        )

        return instance

    def __init__(self, flight_time: int, speed: int):
        self.flight_time = flight_time
        self.speed = speed

    def to_dict(self) -> dict:
        return {
            'flight_time': self.flight_time,
            'speed': self.speed
        }
