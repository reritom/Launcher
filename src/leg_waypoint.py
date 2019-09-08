from .waypoint import Waypoint

class LegWaypoint(Waypoint):
    def __init__(self, positions: dict, id=None, generated=False):
        self.positions = positions
        return super().__init__(type="leg", id=id, generated=generated)

    @property
    def from_pos(self) -> tuple:
        return self.positions['from']

    @property
    def to_pos(self) -> tuple:
        return self.positions['to']

    def to_dict(self) -> dict:
        dict_self = {
            'positions': self.positions,
            'type': self.type,
            'id': self.id
        }

        if self.start_time and self.end_time:
            dict_self['start_time'] = self.start_time.strftime("%Y-%m-%d %H:%M:%S")
            dict_self['end_time'] = self.end_time.strftime("%Y-%m-%d %H:%M:%S")

        return dict_self

    @classmethod
    def from_dict(cls, waypoint_dict: dict):
        return cls(
            positions=waypoint_dict['positions'],
            id=waypoint_dict.get('id')
        )

    def __repr__(self):
        return f"Waypoint(Type: {self.type}, FromPosition: {self.from_pos}, ToPosition: {self.to_pos})"

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and other.is_leg
            and other.positions == self.positions
        )
