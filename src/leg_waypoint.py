from .waypoint import Waypoint

class LegWaypoint(Waypoint):
    def __init__(self, cartesian_positions: dict, id=None):
        self.cartesian_positions = cartesian_positions
        return super().__init__(type="leg", id=id)

    @property
    def from_pos(self) -> tuple:
        return self.cartesian_positions['from']

    @property
    def to_pos(self) -> tuple:
        return self.cartesian_positions['to']

    def to_dict(self) -> dict:
        dict_self = {
            'cartesian_positions': self.cartesian_positions,
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
            cartesian_positions=waypoint_dict['cartesian_positions'],
            id=waypoint_dict.get('id')
        )

    def __repr__(self):
        return f"Waypoint {self.type} from {self.from_pos} to {self.to_pos}"

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and other.is_leg
            and other.cartesian_positions == self.cartesian_positions
        )
