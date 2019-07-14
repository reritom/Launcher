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
        raise NotImplementedError()

    def __init__(self, type, id=None):
        self.type = type
        self.id = str(uuid.uuid4()) if not id else id

        self.start_time = None
        self.end_time = None

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

    def to_dict(self) -> dict:
        raise NotImplementedError()

    def copy(self):
        this_dict = self.to_dict()
        return type(self).from_dict(this_dict)
