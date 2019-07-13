import json
from typing import Optional

from .waypoint import Waypoint
from .bot import Bot
from .tools import distance_between

class FlightPlan:
    UNDEFINED = "UNDEFINED"

    @classmethod
    def from_file(cls, filepath: str) -> 'FlightPlan':
        with open(filepath, 'r') as f:
            flight_plan_dict = json.load(f)

        return cls.from_dict(flight_plan_dict)

    @classmethod
    def from_dict(cls, flight_plan_dict: dict) -> 'FlightPlan':
        return cls(
            waypoints=[Waypoint.from_dict(waypoint_dict) for waypoint_dict in flight_plan_dict.get('waypoints', [])],
            bot=Bot.from_dict(flight_plan_dict['bot']),
            starting_position=flight_plan_dict['starting_position']
        )

    def __init__(self, waypoints: list = None, bot: Bot = None, starting_position: list = None):
        self.waypoints = waypoints if waypoints else []
        self.bot = bot if bot else None
        self.starting_position = starting_position if starting_position else [0, 0, 0]

    def add_waypoint(self, waypoint: Waypoint):
        self.waypoints.append(waypoint)

    def set_bot(self, bot: Bot):
        self.bot = bot

    def set_starting_position(self, starting_position: list):
        self.starting_position = starting_position

    def is_definite(self) -> bool:
        for waypoint in self.waypoints:
            if waypoint.duration == waypoint.INDEFINITE:
                return False
        else:
            return True

    @property
    def is_approximated(self) -> bool:
        for waypoint in self.waypoints:
            if not waypoint.is_approximated:
                return False

        return True

    @property
    def refuel_waypoints(self):
        return [
            waypoint
            for waypoint in self.waypoints
            if waypoint.is_action
            and waypoint.action == waypoint.BEING_RECHARGED
        ]

    @property
    def total_distance(self) -> Optional[int]:
        if not self.is_definite:
            return None

        total_distance = 0

        for waypoint in self.waypoints:
            if waypoint.is_leg:
                total_distance = distance_between(waypoint.from_pos, waypoint.to_pos)

        return total_distance

    @property
    def flight_time(self) -> Optional[int]:
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
