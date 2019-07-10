class Waypoint:
    """
    A waypoint is a dataclass which represents a cartesian coordinate and the duration that
    said coordinate is occupied.
    """
    INDEFINITE = "INDEFINITE"
    BEING_RECHARGED = "BEING_RECHARGED"
    GIVING_RECHARGE = "GIVING_RECHARGE"

    @classmethod
    def from_dict(cls, waypoint_dict: dict) -> 'Waypoint':
        instance = cls(
            cartesian_position=waypoint_dict['cartesian_position'],
            wait=waypoint_dict.get('wait', 0),
            action=waypoint_dict.get('action')
        )

        return instance

    def __init__(self, cartesian_position, wait, action=None):
        self.cartesian_position = cartesian_position
        self.action = action
        self.wait = self.INDEFINITE if wait == -1 else wait

    @property
    def is_being_recharged(self):
        return self.action == Waypoint.BEING_RECHARGED

    @property
    def is_giving_recharge(self):
        return self.action == Waypoint.GIVING_RECHARGE

    @property
    def has_wait(self):
        return self.wait != Waypoint.INDEFINITE

    def to_dict(self) -> dict:
        return {
            'cartesian_position': self.cartesian_position,
            'wait': self.wait if not self.wait == self.INDEFINITE else -1,
            'action': self.action
        }
