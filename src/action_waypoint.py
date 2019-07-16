from .waypoint import Waypoint

class ActionWaypoint(Waypoint):
    def __init__(self, action: str, duration: int, id: str = None):
        self.action = action
        self.duration = duration

        # This gets filled later
        self.position = None
        return super().__init__(type="action", id=id)

    @property
    def is_being_recharged(self):
        return self.action == Waypoint.BEING_RECHARGED

    @property
    def is_giving_recharge(self):
        return self.action == Waypoint.GIVING_RECHARGE

    def to_dict(self):
        dict_self = {
            'type': self.type,
            'action': self.action,
            'duration': self.duration,
            'id': self.id
        }

        if self.start_time and self.end_time:
            dict_self['start_time'] = self.start_time.strftime("%Y-%m-%d %H:%M:%S")
            dict_self['end_time'] = self.end_time.strftime("%Y-%m-%d %H:%M:%S")

        return dict_self

    @classmethod
    def from_dict(cls, waypoint_dict: dict):
        return cls(
            action=waypoint_dict['action'],
            duration=waypoint_dict['duration'],
            id=waypoint_dict.get('id')
        )

    def __repr__(self):
        return f"Waypoint {self.type} at {self.position}"

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and other.is_action
            and other.action == self.action
            and other.duration == self.duration
        )
