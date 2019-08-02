from .waypoint import Waypoint
from .leg_waypoint import LegWaypoint
from .action_waypoint import ActionWaypoint

from typing import List
import uuid


class PartialFlightPlan:
    """
    This is dummy class for flight plans which only define partial bounds without
    specifying starting and ending towers.

    This class should be converted to a full FlightPlan instead of duplicating functionalities
    """
    def __init__(self, id: str = None, bot_model: str = None, waypoints: List[Waypoint] = None):
        self.id = id if id else str(uuid.uuid4())
        self.bot_model = bot_model
        self.waypoints = (
            [waypoint.copy() for waypoint in waypoints]
            if waypoints
            else []
        )

    @classmethod
    def from_dict(cls, partial_flight_plan_dict) -> 'PartialFlightPlan':
        return cls(
            waypoints=[
                ActionWaypoint.from_dict(waypoint_dict)
                if waypoint_dict['type'] == 'action'
                else LegWaypoint.from_dict(waypoint_dict)
                for waypoint_dict in partial_flight_plan_dict.get('waypoints', [])
                ],
            bot_model=partial_flight_plan_dict['bot_model'],
            id=partial_flight_plan_dict.get('id')
        )
