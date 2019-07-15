import math as maths
from typing import List, Optional
import json

from .schedule import Schedule
from .flight_plan import FlightPlan
from .tower import Tower
from .waypoint import Waypoint
from .leg_waypoint import LegWaypoint
from .action_waypoint import ActionWaypoint
from .bot import Bot

from .tools import distance_between
import datetime

class Scheduler:
    def __init__(self, towers: List[Tower], bots: List[Bot], refuel_duration: int, remaining_flight_time_at_refuel: int, refuel_anticipation_buffer: str):
        # Tower objects with their inventories and availabilities
        self.towers = towers

        # List of defined bots
        self.bots = bots

        # All the bots in each tower inventory needs to be defined in this bots list
        bot_models = [bot.model for bot in self.bots]

        for self.tower in towers:
            for inventory in self.tower.inventory:
                assert inventory['model'] in bot_models, f"{inventory['model']} not defined in bot models, {bot_models}"

        # The seconds that a refueler should arrive at the refuel location before the refueling
        self.refuel_anticipation_buffer = refuel_anticipation_buffer

        # The duration of the refuel, the refuel is considered complete at the end of this time
        self.refuel_duration = refuel_duration

        # The flight time a bot should have remaining when it initiates the refueling, it needs to be greater than the refuel_duration
        self.remaining_flight_time_at_refuel = remaining_flight_time_at_refuel

        assert remaining_flight_time_at_refuel > refuel_duration

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

        # Add the position to the action waypoints
        self.add_positions_to_action_waypoints(flight_plan)

        with open('hello.json', 'w') as f:
            f.write(json.dumps(flight_plan.to_dict()))

        # For each refueling waypoint in the flight plan, create a resupply flight plan
        resupply_flight_plans = self.create_refuel_flight_plans(flight_plan)
        print(f"Updated flight plan has {len(flight_plan.waypoints)} waypoints")

        schedule = Schedule()
        return schedule

    def approximate_timings(self, flight_plan: FlightPlan, launch_time: datetime.datetime) -> None:
        """
        For a given flight plan and launch time, approximate the start and end time of each waypoint
        """

        for index, waypoint in enumerate(flight_plan.waypoints):
            waypoint.start_time = launch_time if not index else flight_plan.waypoints[index - 1].end_time

            if waypoint.is_action:
                waypoint.end_time = waypoint.start_time + datetime.timedelta(seconds=waypoint.duration)
            elif waypoint.is_leg:
                bot = self.get_bot_by_model(flight_plan.bot_model)
                waypoint.end_time = waypoint.start_time + datetime.timedelta(seconds=distance_between(waypoint.from_pos, waypoint.to_pos)/bot.speed)

    def recalculate_flight_plan(self, flight_plan: FlightPlan) -> None:
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

                        bot = self.get_bot_by_model(flight_plan.bot_model)
                        threshold = bot.flight_time - self.remaining_flight_time_at_refuel - self.refuel_duration
                        if time_since_last_recharge > threshold:
                            overshoot = time_since_last_recharge - threshold
                            waypoint.duration = waypoint.duration - overshoot

                            # Create the refueling waypoint
                            new_waypoint = ActionWaypoint(
                                action='being_recharged',
                                duration=self.refuel_duration
                            )

                            flight_plan.waypoints.insert(index + 1, new_waypoint)

                            # Create the action waypoint with the remaining overshoot
                            new_waypoint = ActionWaypoint(
                                action=waypoint.action,
                                duration=overshoot
                            )

                            flight_plan.waypoints.insert(index + 2, new_waypoint)
                            print("Breaking from action overshoot")
                            break

                        print("Continuing from action")
                        continue

                    elif waypoint.is_leg:
                        bot = self.get_bot_by_model(flight_plan.bot_model)
                        leg_time = int(distance_between(waypoint.from_pos, waypoint.to_pos)/bot.speed)
                        time_since_last_recharge += leg_time

                        threshold = bot.flight_time - self.remaining_flight_time_at_refuel - self.refuel_duration
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
                            new_waypoint = ActionWaypoint(
                                action='being_recharged',
                                duration=self.refuel_duration
                            )

                            flight_plan.waypoints.insert(index + 1, new_waypoint)

                            # Create the second leg
                            new_waypoint = LegWaypoint(
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

    def add_positions_to_action_waypoints(self, flight_plan: FlightPlan) -> None:
        """
        By default, action waypoints don't have the position because it is implicitly the position of the
        previous waypoint so it can be calculated, but this function adds them for functions which don't
        access the full waypoint context.
        """
        for index, waypoint in enumerate(flight_plan.waypoints):
            if waypoint.is_action:
                i = 1
                while True:
                    try:
                        previous_waypoint = flight_plan.waypoints[index - i]
                    except IndexError as e:
                        waypoint.position = flight_plan.starting_position
                        break

                    if previous_waypoint.is_leg:
                        waypoint.position = flight_plan.waypoints[index - i].to_pos
                        break

                    i = i + 1

    def create_refuel_flight_plans(self, flight_plan: FlightPlan) -> List[FlightPlan]:
        """
        For a given flight plan, determine the flight plans for any refueling bots
        """
        assert flight_plan.is_approximated

        potential_flight_plans_per_waypoint_id = {}
        print(f"There are {len(flight_plan.refuel_waypoints)}")

        for waypoint in flight_plan.refuel_waypoints:
            nearest_towers = self.get_nearest_towers_to_waypoint(waypoint)
            print(f"Nearest towers to {waypoint} are {nearest_towers}")

            # For each tower we will create a dummy flight plan, and then take whichever is available
            for tower in nearest_towers:
                # These are the base waypoints, we will copy these for each type of inventory
                waypoints = [
                    LegWaypoint(
                        cartesian_positions={
                            'from': tower.position,
                            'to': waypoint.position
                        }
                    ),
                    ActionWaypoint(
                        id="critical",
                        action="refuel_anticipation_buffer",
                        duration=self.refuel_anticipation_buffer
                    ),
                    ActionWaypoint(
                        action=Waypoint.GIVING_RECHARGE,
                        duration=self.refuel_duration
                    ),
                    LegWaypoint(
                        cartesian_positions={
                            'from': waypoint.position,
                            'to': tower.position
                        }
                    )
                ]

                # Each tower can multiple types of refueler models, so we will check each
                for bot_model in tower.inventory_models:
                    bot = self.get_bot_by_model(bot_model)

                    flight_plan = FlightPlan(
                        waypoints=[
                            waypoint.copy()
                            for waypoint in waypoints
                            ],
                        bot_model=bot_model,
                        starting_position=tower.position
                    )
                    potential_flight_plans_per_waypoint_id.setdefault(waypoint.id, [])
                    potential_flight_plans_per_waypoint_id[waypoint.id].append(flight_plan)

        for id in potential_flight_plans_per_waypoint_id:
            print(potential_flight_plans_per_waypoint_id[id])

    def get_nearest_towers_to_waypoint(self, waypoint: Waypoint) -> List[Tower]:
        """
        For a given waypoint, return a list of towers with the first element being the closest
        """
        assert waypoint.is_action
        distances = []

        for tower in self.towers:
            distance = distance_between(waypoint.position, tower.position)
            distances.append((distance, tower))

        # We then sort by distance and return a list of towers with the first being the closest
        distances.sort(key=lambda value: value[0])

        return [
            distance[1]
            for distance in distances
        ]

    def get_bot_by_model(self, model: str) -> Optional[Bot]:
        for bot in self.bots:
            if bot.model == model:
                return bot
