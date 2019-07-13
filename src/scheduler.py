import math as maths
from typing import List
import json

from .schedule import Schedule
from .flight_plan import FlightPlan
from .tower import Tower
from .waypoint import Waypoint

from .tools import distance_between
import datetime

class Scheduler:
    def __init__(self, towers: List[Tower], refuel_duration: int, remaining_flight_time_at_refuel: int):
        self.towers = towers
        self.refuel_duration = refuel_duration
        self.remaining_flight_time_at_refuel = remaining_flight_time_at_refuel

    def determine_schedule_from_waypoint_eta(self, flight_plan: FlightPlan, waypoint_eta: datetime.datetime, waypoint_id: str) -> Schedule:
        """
        Determine the schedule based on the time the client wants the bot to reach a certain waypoint.
        If the schedules requires the first launch to be in the past, the schedule is marked as unapplicable.
        """
        assert waypoint_id in [waypoint.id for waypoint in flight_time.waypoints]

    def determine_schedule_from_launch_time(self, flight_plan: FlightPlan, launch_time: datetime.datetime) -> Schedule:
        """
        For a given flight plan, determine when all the supporting bots need to be deployed and their
        respective flight plans
        """
        # Add an refueling waypoints to the flight plan
        self.recalculate_flight_plan(flight_plan)

        # Flight plans don't consider absolute timings, so here will will add some approximates
        self.approximate_timings(flight_plan, launch_time)

        with open('hello.json', 'w') as f:
            f.write(json.dumps(flight_plan.to_dict()))

        # For each refueling waypoint in the flight plan, create a resupply flight plan
        resupply_flight_plans = self.create_refuel_flight_plans(flight_plan)
        print(f"Updated flight plan has {len(flight_plan.waypoints)} waypoints")

        schedule = Schedule()
        return schedule

    def approximate_timings(self, flight_plan, launch_time):
        """
        For a given flight plan and launch time, approximate the start and end time of each waypoint
        """

        for index, waypoint in enumerate(flight_plan.waypoints):
            waypoint.start_time = launch_time if not index else flight_plan.waypoints[index - 1].end_time

            if waypoint.is_action:
                waypoint.end_time = waypoint.start_time + datetime.timedelta(seconds=waypoint.duration)
            elif waypoint.is_leg:
                waypoint.end_time = waypoint.start_time + datetime.timedelta(seconds=distance_between(waypoint.from_pos, waypoint.to_pos)/flight_plan.bot.speed)

    def recalculate_flight_plan(self, flight_plan):
        """
        For a given flight plan, add any necessary refueling waypoints
        """
        if flight_plan.is_definite:
            finished = False
            while not finished:
                time_since_last_recharge = 0

                for index, waypoint in enumerate(flight_plan.waypoints):
                    if waypoint.is_action:
                        if waypoint.is_being_recharged:
                            print("Waypoint is being recharged")
                            time_since_last_recharge = 0
                            continue

                        # Else we will look at the duration of the action, and split it if necessary
                        time_since_last_recharge += waypoint.duration

                        threshold = flight_plan.bot.flight_time - self.remaining_flight_time_at_refuel - self.refuel_duration
                        if time_since_last_recharge > threshold:
                            overshoot = time_since_last_recharge - threshold
                            waypoint.duration = waypoint.duration - overshoot

                            # Create the refueling waypoint
                            new_waypoint = Waypoint(
                                type='action',
                                action='being_recharged',
                                duration=self.refuel_duration
                            )

                            flight_plan.waypoints.insert(index + 1, new_waypoint)

                            # Create the action waypoint with the remaining overshoot
                            new_waypoint = Waypoint(
                                type='action',
                                action=waypoint.action,
                                duration=overshoot
                            )

                            flight_plan.waypoints.insert(index + 2, new_waypoint)
                            print("Breaking from action overshoot")
                            break

                        print("Continuing from action")
                        continue

                    elif waypoint.is_leg:
                        leg_time = int(distance_between(waypoint.from_pos, waypoint.to_pos))
                        time_since_last_recharge += leg_time

                        threshold = flight_plan.bot.flight_time - self.remaining_flight_time_at_refuel - self.refuel_duration
                        print(f"Leg, time since last {time_since_last_recharge}, threshold {threshold}")
                        if time_since_last_recharge > threshold:
                            overshoot = time_since_last_recharge - threshold

                            # We will split the leg into two legs with a refuel inbetween
                            overshoot_ratio = (leg_time - overshoot) / leg_time
                            split_position = [
                                waypoint.from_pos[i] + (waypoint.to_pos[i] - waypoint.from_pos[i]) * overshoot_ratio
                                for i in [0, 1, 2]
                            ]

                            # Create the refuel
                            new_waypoint = Waypoint(
                                type='action',
                                action='being_recharged',
                                duration=self.refuel_duration
                            )

                            flight_plan.waypoints.insert(index + 1, new_waypoint)

                            # Create the second leg
                            new_waypoint = Waypoint(
                                type='leg',
                                cartesian_positions={
                                    'from': split_position,
                                    'to': waypoint.cartesian_positions['to']
                                }
                            )

                            flight_plan.waypoints.insert(index + 2, new_waypoint)

                            # Turn the leg into just the first leg
                            waypoint.cartesian_positions['to'] = split_position
                            print("Breaking from leg overshoot")
                            break

                        print("Continuing from leg")
                        continue

                else:
                    finished = True

    def create_refuel_flight_plans(self, flight_plan):
        assert flight_plan.is_approximated

        for waypoint in flight_plan.refuel_waypoints:
            nearest_towers = ""
            flight_plan = FlightPlan()
