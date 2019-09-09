import json, uuid
from typing import Optional

from .leg_waypoint import LegWaypoint
from .action_waypoint import ActionWaypoint
from .waypoint import Waypoint
from .bot_schema import BotSchema
from .flight_plan_meta import FlightPlanMeta
from .tools import distance_between

class FlightPlan:
    @classmethod
    def from_file(cls, filepath: str) -> 'FlightPlan':
        with open(filepath, 'r') as f:
            flight_plan_dict = json.load(f)

        return cls.from_dict(flight_plan_dict)

    @classmethod
    def from_dict(cls, flight_plan_dict: dict) -> 'FlightPlan':
        return cls(
            waypoints=[
                ActionWaypoint.from_dict(waypoint_dict)
                if waypoint_dict['type'] == 'action'
                else LegWaypoint.from_dict(waypoint_dict)
                for waypoint_dict in flight_plan_dict.get('waypoints', [])
                ],
            starting_tower=flight_plan_dict['starting_tower'],
            finishing_tower=flight_plan_dict['finishing_tower'],
            id=flight_plan_dict.get('id')
        )

    def __init__(self,
        waypoints: list = None,
        id: str = None,
        starting_tower: str = None,
        finishing_tower: str = None,
        meta: FlightPlanMeta = None
    ):
        self.waypoints = waypoints if waypoints else []
        self.starting_tower = starting_tower
        self.finishing_tower = finishing_tower
        self.id = id if id else str(uuid.uuid4())

        # Meta is the dynamic component
        self.meta = meta if meta else None

        # Used for restoring the original state
        self._original_parameters = {
            'waypoints': [waypoint for waypoint in self.waypoints],
            'starting_tower': self.starting_tower,
            'finishing_tower': self.finishing_tower,
            'id': self.id,
            'meta': self.meta
        }

    def set_meta(self, meta: FlightPlanMeta):
        self.meta = meta

    @property
    def has_meta(self):
        return True if self.meta else False

    def reset(self):
        self.waypoints = [waypoint for waypoint in self._original_parameters['waypoints']]
        self.id = self._original_parameters['id']
        self.starting_tower = self._original_parameters['starting_tower']
        self.finishing_tower =  self._original_parameters['finishing_tower']
        self.meta = self._original_parameters['meta']

    def add_waypoint(self, waypoint: Waypoint):
        # TODO add some validations to do with positions
        # TODO, undo estimations
        self.waypoints.append(waypoint)

    def is_definite(self) -> bool:
        """
        If all the waypoints are definite, then the flight plan is definite, meaning timings can be calculated
        with relative ease.
        """
        for waypoint in self.waypoints:
            if waypoint.duration == waypoint.INDEFINITE:
                return False
        else:
            return True

    @property
    def giving_recharge_index(self) -> int:
        for index, waypoint in enumerate(self.waypoints):
            if waypoint.is_action and waypoint.is_giving_recharge:
                return index

    @property
    def has_giving_recharge_waypoint(self) -> bool:
        return self.giving_recharge_index is not None

    @property
    def is_approximated(self) -> bool:
        """
        A flight plan is approximated if all the waypoints are approximated, meaning they have a start time
        and an end time relative to a given launch time.
        """
        for waypoint in self.waypoints:
            if not waypoint.is_approximated:
                return False

        return True

    @property
    def refuel_waypoints(self):
        """
        Return a list of waypoints where the action is being recharged
        """
        return [
            waypoint
            for waypoint in self.waypoints
            if waypoint.is_action
            and waypoint.action == waypoint.BEING_RECHARGED
        ]

    @property
    def giving_refuel_waypoint(self) -> Optional[ActionWaypoint]:
        for waypoint in self.waypoints:
            if waypoint.is_action and waypoint.action == waypoint.GIVING_RECHARGE:
                return waypoint

    @property
    def refuel_waypoint_count(self):
        return len(self.refuel_waypoints)

    @property
    def total_distance(self) -> Optional[int]:
        """
        If the flight plan is definitive, return the total distance
        """
        if not self.is_definite:
            return None

        total_distance = 0

        for waypoint in self.waypoints:
            if waypoint.is_leg:
                total_distance = distance_between(waypoint.from_pos, waypoint.to_pos)

        return total_distance

    def to_dict(self) -> dict:
        return {
            'waypoints': [
                waypoint.to_dict()
                for waypoint
                in self.waypoints
            ],
            'starting_tower': self.starting_tower,
            'finishing_tower': self.finishing_tower,
            'id': self.id
        }

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False

        if len(self.waypoints) != len(other.waypoints):
            print(f"Lengths dont match {len(self.waypoints)} {len(other.waypoints)}")
            return False

        print(f"Lengths match {len(self.waypoints)} {len(other.waypoints)}")

        for index, waypoint in enumerate(self.waypoints):
            if not waypoint == other.waypoints[index]:
                return False

        print("Waypoints match")
        print(self.starting_tower, other.starting_tower)
        print(self.finishing_tower, other.finishing_tower)

        return (
            self.starting_tower == other.starting_tower
            and self.finishing_tower == other.finishing_tower
        )

    def copy(self) -> 'FlightPlan':
        cls = type(self)
        return cls(
            waypoints=[
                waypoint.copy()
                for waypoint in self.waypoints
            ],
            starting_tower=self.starting_tower,
            finishing_tower=self.finishing_tower,
            meta=self.meta
        )

    def copy_from(self, other_flight_plan: 'FlightPlan'):
        """
        Overwrite this flight plan with the contents of another
        """
        self.waypoints = [
            waypoint.copy()
            for waypoint in other_flight_plan.waypoints
        ]

        self.starting_tower = other_flight_plan.starting_tower
        self.finishing_tower = other_flight_plan.finishing_tower
        self.id = other_flight_plan.id
        self.meta = other_flight_plan.meta

    @property
    def start_time(self):
        """
        Return the start time of the first waypoint
        """
        return self.waypoints[0].start_time

    @property
    def end_time(self):
        """
        Return the end time of the final waypoint
        """
        return self.waypoints[-1].end_time
