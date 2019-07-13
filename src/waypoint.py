import uuid

class Waypoint:
    """
    A waypoint is a dataclass which either represents a leg of a journey, or an action being performed between two legs.
    """
    INDEFINITE = "indefinite"

    BEING_RECHARGED = "being_recharged"
    GIVING_RECHARGE = "giving_recharge"

    @classmethod
    def from_dict(cls, waypoint_dict: dict) -> 'Waypoint':
        instance = cls(
            cartesian_positions=waypoint_dict.get('cartesian_positions'),
            type=waypoint_dict['type'],
            action=waypoint_dict.get('action'),
            duration=waypoint_dict.get('duration'),
            id=waypoint_dict.get('id')
        )

        return instance

    def __init__(self, type, action=None, duration=None, cartesian_positions=None, id=None):
        self.type = type
        self.id = str(uuid.uuid4()) if not id else id

        self.action = None
        self.duration = None
        self.cartesian_positions = None

        self.start_time = None
        self.end_time = None

        if self.type == 'leg':
            assert cartesian_positions is not None
            self.cartesian_positions = cartesian_positions

        elif self.type == 'action':
            assert action is not None
            self.action = action

            assert duration is not None
            self.duration = duration

    @property
    def is_approximated(self):
        return self.start_time and self.end_time

    @property
    def is_definite(self):
        if self.is_leg:
            return True

        elif self.is_action:
            return self.duration != self.INDEFINITE

    @property
    def is_leg(self):
        return self.type == 'leg'

    @property
    def is_action(self):
        return self.type == 'action'

    @property
    def from_pos(self):
        assert self.is_leg
        return self.cartesian_positions['from']

    @property
    def to_pos(self):
        assert self.is_leg
        return self.cartesian_positions['to']

    @property
    def is_being_recharged(self):
        return self.action == Waypoint.BEING_RECHARGED

    @property
    def is_giving_recharge(self):
        return self.action == Waypoint.GIVING_RECHARGE

    def to_dict(self) -> dict:
        if self.is_action:
            return {
                'type': self.type,
                'action': self.action,
                'duration': self.duration,
                'start_time': self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                'end_time': self.end_time.strftime("%Y-%m-%d %H:%M:%S")
            }
        elif self.is_leg:
            return {
                'cartesian_positions': self.cartesian_positions,
                'type': self.type,
                'start_time': self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                'end_time': self.end_time.strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            return {}
