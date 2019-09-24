import datetime

from .waypoint import Waypoint

class ActionWaypoint(Waypoint):
    PAYLOAD_ACTION = "payload"

    def __init__(self, action: str, duration: datetime.timedelta, id: str = None, position: list = None, generated=False):
        self.action = action
        assert isinstance(duration, datetime.timedelta)
        assert duration.total_seconds() >= 0
        self.duration = duration

        # This can be optionally filled later
        self.position = position
        return super().__init__(type="action", id=id, generated=generated)

    @property
    def is_being_recharged(self):
        return Waypoint.BEING_RECHARGED in self.action.split(' ')

    @property
    def is_giving_recharge(self):
        return Waypoint.GIVING_RECHARGE in self.action.split(' ')

    @property
    def is_payload_action(self):
        return ActionWaypoint.PAYLOAD_ACTION in self.action.split(' ')

    def to_dict(self):
        # Convert the duration timedelta into the correct format HH:MM:SS
        duration = ":".join([
            value
            if len(value) == 2
            else f"0{value}"
            for value in str(self.duration).split('.')[0].split(":")
        ])

        dict_self = {
            'type': self.type,
            'action': self.action,
            'duration': duration,
            'id': self.id,
            'generated': self.generated if self.generated else False
        }

        if self.start_time and self.end_time:
            dict_self['start_time'] = self.start_time.strftime("%Y-%m-%dT%H:%M:%S")
            dict_self['end_time'] = self.end_time.strftime("%Y-%m-%dT%H:%M:%S")

        if self.position:
            dict_self['position'] = self.position

        return dict_self

    @classmethod
    def from_dict(cls, waypoint_dict: dict):
        duration = datetime.datetime.strptime(waypoint_dict['duration'], "%H:%M:%S")
        duration = datetime.timedelta(
            seconds=(
                duration.hour*60*60 + duration.minute*60 + duration.second
            )
        )
        return cls(
            action=waypoint_dict['action'],
            duration=duration,
            id=waypoint_dict.get('id'),
            position=waypoint_dict.get('position'),
            generated=waypoint_dict.get('generated')
        )

    def __repr__(self):
        return f"Waypoint(Type: {self.type}, Position: {self.position}, Action: {self.action}, Duration: {self.duration})"

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and other.is_action
            and other.action == self.action
            and other.duration == self.duration
        )
