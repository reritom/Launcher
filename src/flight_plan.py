import json
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
            bot=Bot.from_dict(flight_plan_dict['bot']),
            starting_position=flight_plan_dict['starting_position']
        )

    def __init__(self, waypoints: list = None, bot: Bot = None, starting_position: list = None):
        self.waypoints = waypoints if waypoints else []
        self.bot = bot if bot else None
        self.starting_position = starting_position if starting_position else [0, 0, 0]

    def add_waypoint(self, waypoint: Waypoint):
        # TODO add some validations to do with positions
        self.waypoints.append(waypoint)

    def set_bot(self, bot: Bot):
        """
        Flight plans don't have a bot as such, but they do require a bot type which is determined by payload type
        and specification. The bot here is used when calculating schedules and timings
        """
        self.bot = bot

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

    @property
    def flight_time(self) -> Optional[int]:
        """
        Return the approximate flight time by considering the distance and the bot type.
        """
        flight_time = 0

        for waypoint in self.waypoints:
            if waypoint.is_leg:
                distance = distance_between(waypoint.from_pos, waypoint.to_pos)
                time = distance / self.bot.speed

            elif waypoint.is_action:
                time = time + waypoint.duration

            flight_time = flight_time + time

        return flight_time


    def to_dict(self) -> dict:
        return {
            'waypoints': [
                waypoint.to_dict()
                for waypoint
                in self.waypoints
            ],
            'bot': self.bot.to_dict(),
            'starting_position': self.starting_position
        }
