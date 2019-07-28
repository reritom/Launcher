import json, uuid
from typing import Optional

from .leg_waypoint import LegWaypoint
from .action_waypoint import ActionWaypoint
from .waypoint import Waypoint
from .bot import Bot
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
            bot_model=flight_plan_dict['bot_model'],
            starting_position=flight_plan_dict['starting_position'],
            id=flight_plan_dict.get('id')
        )

    def __init__(self, waypoints: list = None, bot_model: str = None, starting_position: list = None, id: str = None):
        self.waypoints = waypoints if waypoints else []
        self.bot_model = bot_model if bot_model else None
        self.starting_position = starting_position if starting_position else [0, 0, 0]
        self.id = id if id else str(uuid.uuid4())

    def add_waypoint(self, waypoint: Waypoint):
        # TODO add some validations to do with positions
        # TODO, undo estimations
        self.waypoints.append(waypoint)

    def set_bot(self, bot_model: str):
        """
        Flight plans don't have a bot as such, but they do require a bot type which is determined by payload type
        and specification. The bot here is used when calculating schedules and timings
        """
        self.bot_model = bot_model

    def set_starting_position(self, starting_position: list):
        """
        The location of the tower the flight plan starts from
        """
        self.starting_position = starting_position

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
            'bot_model': self.bot_model,
            'starting_position': self.starting_position,
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

        print("Enumerations match")

        return (
            self.bot_model == other.bot_model
            and self.starting_position == other.starting_position
        )

    def copy(self) -> 'FlightPlan':
        cls = type(self)
        return cls(
            waypoints=[
                waypoint.copy()
                for waypoint in self.waypoints
            ],
            bot_model=self.bot_model,
            starting_position=[i for i in self.starting_position]
        )

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
