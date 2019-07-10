import math as maths
from typing import List
import json

from .schedule import Schedule
from .flight_plan import FlightPlan
from .tower import Tower
from .waypoint import Waypoint

from .tools import distance_between

class Scheduler:
    def __init__(self, towers: List[Tower], refuel_duration: int, remaining_flight_time_at_refuel: int):
        self.towers = towers
        self.refuel_duration = refuel_duration
        self.remaining_flight_time_at_refuel = remaining_flight_time_at_refuel

    @classmethod
    def from_config_file(cls, filepath: str) -> 'Scheduler':
        with open(filepath, 'r') as f:
            configuration_dict = json.load(f)

        return cls.from_dict(configuration_dict)

    @classmethod
    def from_dict(cls, configuration_dict: dict) -> 'Scheduler':
        return cls(
            towers=[Tower.from_dict(tower_dict) for tower_dict in configuration_dict.get('towers', [])],
            refuel_duration=configuration_dict['refuel_duration'],
            remaining_flight_time_at_refuel=configuration_dict['remaining_flight_time_at_refuel']
        )

    def determine_schedule(self, flight_plan: FlightPlan) -> Schedule:
        """
        For a given flight plan, determine when all the supporting bots need to be deployed and their
        respective flight plans
        """
        self.recalculate_flight_plan(flight_plan)

        with open('hello.json', 'w') as f:
            f.write(json.dumps(flight_plan.to_dict()))

        schedule = Schedule()
        return schedule

    def recalculate_flight_plan(self, flight_plan):
        """
        For a given flight plan, add any necessary refueling waypoints
        """
        if flight_plan.is_definite:
            # Based on the range, determine how many assistant bots are needed
            #main_bot_refills_required = maths.ceil(flight_plan.flight_time / (self.bot.flight_time - self.remaining_flight_time_at_refuel))

            # For each assistant bot, determine how many assistants are needed and when they need to be deployed
            finished = False
            count = 0
            while not finished and count < 100:
                print(f"Count {count}")
                count = count + 1
                time_since_last_recharge = 0

                for index, waypoint in enumerate(flight_plan.waypoints):
                    print(f"Count {count}, index {index}")
                    if not index:
                        reference_position = flight_plan.starting_position
                    else:
                        reference_position = flight_plan.waypoints[index - 1].cartesian_position

                    print(f"Reference position is {reference_position}")
                    if waypoint.is_giving_recharge:
                        print("Waypoint is being recharged")
                        time_since_last_recharge = 0
                        continue

                    distance = distance_between(reference_position, waypoint.cartesian_position)
                    time_between_waypoints = distance / flight_plan.bot.speed
                    time_since_last_waypoint = time_between_waypoints + waypoint.wait
                    time_since_last_recharge = time_since_last_recharge + time_since_last_waypoint

                    if time_since_last_recharge >= (flight_plan.bot.flight_time - self.remaining_flight_time_at_refuel):
                        print(f"Time since last recharge is {time_since_last_recharge}")
                        # We need to add a recharge waypoint

                        # We need to determine where to put the waypoint
                        time_overshoot = time_since_last_recharge - (flight_plan.bot.flight_time - self.remaining_flight_time_at_refuel)
                        print(f"Overshoot is {time_overshoot}")

                        # If the overshoot is in the waiting period, we can add a waypoint after in the same position
                        if waypoint.has_wait and time_overshoot <= waypoint.wait:
                            print("Overshoot is in wait")
                            new_waypoint = Waypoint(
                                cartesian_position=waypoint.cartesian_position,
                                wait=self.refuel_duration,
                                action=Waypoint.GIVING_RECHARGE
                            )
                            flight_plan.waypoints.insert(index + 1, new_waypoint)
                        elif waypoint.has_wait:
                            print("Overshoot isnt in wait, but there is a wait")
                            time_overshoot = time_overshoot - waypoint.wait
                        else:
                            pass


                        # We will create a waypoint before the current one
                        # The time from the start of the n - 1 waypoint to the waypoint
                        # The ratio between this and the last waypoint
                        waypoint_ratio = (time_since_last_waypoint - time_overshoot) / time_since_last_waypoint
                        print(f"Waypoint ratio is {waypoint_ratio}")
                        print(f"Reference {reference_position}, ratio {waypoint_ratio}, waypoint {waypoint.cartesian_position}")
                        waypoint_position = [
                            reference_position[i] + waypoint_ratio * (waypoint.cartesian_position[i] - reference_position[i])
                            for i in [0, 1, 2]
                        ]
                        print(f"New waypoint position is {waypoint_position}")
                        new_waypoint = Waypoint(
                            cartesian_position=waypoint_position,
                            wait=self.refuel_duration,
                            action=Waypoint.GIVING_RECHARGE
                        )
                        flight_plan.waypoints.insert(index, new_waypoint)
                        print("Breaking")
                        break
                else:
                    finished = True
        """
        else:
            # We can't statically create a schedule, and instead need to create a dynamic schedule
            # Somehow..
            pass
        """
