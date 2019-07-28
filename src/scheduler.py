import math as maths
from typing import List, Optional, Dict
import json

from .schedule import Schedule
from .flight_plan import FlightPlan
from .tower import Tower
from .waypoint import Waypoint
from .leg_waypoint import LegWaypoint
from .action_waypoint import ActionWaypoint
from .bot import Bot

from .tools import distance_between, find_middle_position_by_ratio, Encoder
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
        self.validate_flight_plan(flight_plan)

        # Add an refueling waypoints to the flight plan
        self.recalculate_flight_plan(flight_plan)

        # Flight plans don't consider absolute timings, so here will will add some approximates
        self.approximate_timings_based_on_waypoint_eta(
            flight_plan=flight_plan,
            waypoint_id=waypoint_id,
            waypoint_eta=waypoint_eta
        )

        # Add the position to the action waypoints
        self.add_positions_to_action_waypoints(flight_plan)

        # For each refueling waypoint in the flight plan, create a resupply flight plan
        refuel_flight_plans_per_waypoint_id = self.create_refuel_flight_plans(flight_plan)

        with open("hello.json", 'w') as f:
            f.write(json.dumps(refuel_flight_plans_per_waypoint_id, cls=Encoder))

        schedule = Schedule()
        return schedule

    def determine_schedule_from_launch_time(self, flight_plan: FlightPlan, launch_time: datetime.datetime) -> Schedule:
        """
        For a given flight plan, determine when all the supporting bots need to be deployed and their
        respective flight plans
        """
        self.validate_flight_plan(flight_plan)

        # Add an refueling waypoints to the flight plan
        self.recalculate_flight_plan(flight_plan)

        # Flight plans don't consider absolute timings, so here will will add some approximates
        self.approximate_timings(flight_plan, launch_time)

        # Add the position to the action waypoints
        self.add_positions_to_action_waypoints(flight_plan)

        # For each refueling waypoint in the flight plan, create a resupply flight plan
        refuel_flight_plans_per_waypoint_id = self.create_refuel_flight_plans(flight_plan)

        schedule_dict = {
            'flight_plan': flight_plan,
            'related_sub_flight_plans': refuel_flight_plans_per_waypoint_id
        }

        with open("hello.json", 'w') as f:
            f.write(json.dumps(refuel_flight_plans_per_waypoint_id, cls=Encoder))

        schedule = Schedule(raw_schedule=schedule_dict)
        print(f"Schedule contains {len(schedule.flight_plans)} flight plans")
        return schedule

    def validate_schedule_availabilities(self, schedule: Schedule):
        pass

    def calculate_sourcing_schedule(self, schedule: Schedule) -> Schedule:
        pass

    def validate_flight_plan(self, flight_plan: FlightPlan):
        """
        Perform some basic assertions on the flight plan to ensure it will work
        """
        # The associated bot model needs to exist in our context
        assert flight_plan.bot_model in [bot.model for bot in self.bots], "Unknown bot model"

        # Make sure the flight plan starts at a tower
        assert flight_plan.starting_position == flight_plan.waypoints[0].from_pos, "Starting point doesnt match first waypoint"
        assert flight_plan.waypoints[0].from_pos in [tower.position for tower in self.towers], "Starting waypoint isn't located on tower"

        # The end of the final leg needs to be a tower location
        assert flight_plan.waypoints[-1].is_leg, "Last waypoint isnt a leg"

        tower_positions = [tower.position for tower in self.towers]
        assert flight_plan.waypoints[-1].to_pos in tower_positions, f"Last waypoint isn't targetting a tower {flight_plan.waypoints[-1].to_pos} not in {tower_positions}"

        # Assert each of the legs line up
        for index, waypoint in enumerate(flight_plan.waypoints):
            if not index:
                # The first waypoint is a leg
                end_position = waypoint.to_pos
            else:
                if waypoint.is_leg:
                    assert waypoint.from_pos == end_position, f"End of waypoint {index - 1} doesn't match start of waypoint {index}" # of previous leg
                    end_position = waypoint.to_pos

        return True

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

    def approximate_timings_based_on_waypoint_eta(self, flight_plan: FlightPlan, waypoint_eta: datetime.datetime, waypoint_id: str):
        """
        For a given flight plan and launch time, approximate the start and end time of each waypoint
        """
        # Find the index of the waypoint we are interested in
        index = [index for index, waypoint in enumerate(flight_plan.waypoints) if waypoint.id == waypoint_id].pop(0)
        initial_index = index

        bot = self.get_bot_by_model(flight_plan.bot_model)

        # We will work backwards from the index
        while index >= 0:
            reference_waypoint = flight_plan.waypoints[index]

            if index == initial_index:
                # Make the initial approximations
                reference_waypoint.start_time = waypoint_eta
                reference_waypoint.end_time = (
                    waypoint_eta + datetime.timedelta(seconds=reference_waypoint.duration)
                    if reference_waypoint.is_action
                    else waypoint_eta + datetime.timedelta(seconds=distance_between(reference_waypoint.from_pos, reference_waypoint.to_pos)/bot.speed)
                )
            else:
                # Work backwards from the timing we know
                reference_waypoint.start_time = (
                    flight_plan.waypoints[index + 1].start_time - datetime.timedelta(seconds=reference_waypoint.duration)
                    if reference_waypoint.is_action
                    else flight_plan.waypoints[index + 1].start_time - datetime.timedelta(seconds=distance_between(reference_waypoint.from_pos, reference_waypoint.to_pos)/bot.speed)
                )
                reference_waypoint.end_time = flight_plan.waypoints[index + 1].start_time

            index = index - 1

        # And then work forward from the beginning like usual
        return self.approximate_timings(
            flight_plan=flight_plan,
            launch_time=flight_plan.waypoints[0].start_time
        )

    def recalculate_flight_plan(self, flight_plan: FlightPlan) -> None:
        """
        For a given flight plan, add any necessary refueling waypoints
        """
        finished = False
        while not finished:
            time_since_last_recharge = 0

            for index, waypoint in enumerate(flight_plan.waypoints):
                if waypoint.is_action:
                    if waypoint.is_being_recharged:
                        #print("Waypoint is being recharged")
                        time_since_last_recharge = 0
                        continue

                    # Else we will look at the duration of the action, and split it if necessary
                    time_since_last_recharge += waypoint.duration

                    bot = self.get_bot_by_model(flight_plan.bot_model)
                    threshold = bot.flight_time - self.remaining_flight_time_at_refuel - self.refuel_duration
                    if time_since_last_recharge > threshold:
                        # If the waypoint is giving performing a recharge, then we can't interrupt it
                        if waypoint.is_giving_recharge:
                            # Create the refueling waypoint
                            new_waypoint = ActionWaypoint(
                                action='being_recharged',
                                duration=self.refuel_duration
                            )

                            # So we recharge it before the action
                            flight_plan.waypoints.insert(index - 1, new_waypoint)
                        else:
                            overshoot = time_since_last_recharge - threshold

                            if waypoint.duration == overshoot:
                                # We don't split the existing waypoint, we just insert the refuel first

                                # Create the refueling waypoint
                                new_waypoint = ActionWaypoint(
                                    action='being_recharged',
                                    duration=self.refuel_duration
                                )

                                flight_plan.waypoints.insert(index, new_waypoint)
                            else:
                                # We split the existing waypoint, add a refuel point, and then create a new waypoint for the remaining action
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
                        #print("Breaking from action overshoot")
                        break

                    #print("Continuing from action")
                    continue

                elif waypoint.is_leg:
                    bot = self.get_bot_by_model(flight_plan.bot_model)
                    leg_time = int(distance_between(waypoint.from_pos, waypoint.to_pos)/bot.speed)
                    time_since_last_recharge += leg_time

                    threshold = bot.flight_time - self.remaining_flight_time_at_refuel - self.refuel_duration
                    #print(f"Leg, time since last {time_since_last_recharge}, threshold {threshold}")
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
                        #print("Breaking from leg overshoot")
                        break

                    #print("Continuing from leg")
                    continue

            else:
                finished = True

    def add_positions_to_action_waypoints(self, flight_plan: FlightPlan) -> None:
        """
        By default, action waypoints don't have the position because it is implicitly the position of the
        previous waypoint so it can be calculated, but this function adds them for functions which don't
        access the full waypoint context.
        """
        assert self.validate_flight_plan(flight_plan), "Flight plan invalid before adding positions"
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

        assert self.validate_flight_plan(flight_plan), "Flight plan invalid after adding positions"

    def create_dummy_refuel_flight_plans(self, waypoint: Waypoint) -> FlightPlan:
        """
        For a given waypoint, return a list of potential dummy flight plans
        """
        assert waypoint.is_action and waypoint.is_being_recharged
        nearest_towers = self.get_nearest_towers_to_waypoint(waypoint)
        dummy_flight_plans = []

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
                if bot.is_refueler:
                    flight_plan = FlightPlan(
                        waypoints=[
                            waypoint.copy()
                            for waypoint in waypoints
                            ],
                        bot_model=bot_model,
                        starting_position=tower.position
                    )
                    assert self.validate_flight_plan(flight_plan)
                    dummy_flight_plans.append(flight_plan)

        return dummy_flight_plans

    def create_refuel_flight_plans(self, flight_plan: FlightPlan, depth=0) -> dict:
        """
        For a given flight plan, determine the flight plans for any refueling bots
        """
        assert flight_plan.is_approximated

        if depth > 30:
            raise Exception("Exception")

        print(f"There are {len(flight_plan.refuel_waypoints)} refuel waypoints")
        calculated_flight_plans_per_waypoint_id = {}

        for index, refuel_waypoint in enumerate(flight_plan.refuel_waypoints):
            print(f"Looking at waypoint {index}")
            calculated_flight_plans_per_waypoint_id.setdefault(refuel_waypoint.id, [])

            # Get all the base flight plans for refuelers from different towers and different bot models
            dummy_potential_flight_plans = self.create_dummy_refuel_flight_plans(refuel_waypoint)
            print(f"There are {len(dummy_potential_flight_plans)} potential flight plans")

            for potential_flight_plan in dummy_potential_flight_plans:
                # We need to prevent a recursive loop by pre-recalculating the flight plan
                flight_plan_copy = potential_flight_plan.copy()
                self.recalculate_flight_plan(flight_plan_copy)
                assert self.validate_flight_plan(flight_plan_copy), "Invalid after recalculation"
                self.add_positions_to_action_waypoints(flight_plan_copy)

                # If there is a refuel needed while performing the refuel, we will end up in a loop
                giving_refuel_waypoint = flight_plan_copy.giving_refuel_waypoint
                print(f"Flight plan copy has {len(flight_plan.waypoints)} waypoints")
                for waypoint in flight_plan_copy.waypoints:
                    if waypoint.is_action and waypoint.is_being_recharged:
                        print("This one is being recharged")
                        if waypoint.position and waypoint.position == giving_refuel_waypoint.position:
                            print("And being recharged at the refuel location")
                            # We will inject a refuel point into the original potential flight plan to avoid this case
                            self.add_pre_giving_refuel_waypoint(potential_flight_plan)
                            assert self.validate_flight_plan(potential_flight_plan)

                # General flight plan preperation
                self.recalculate_flight_plan(potential_flight_plan)
                assert self.validate_flight_plan(potential_flight_plan)
                self.add_positions_to_action_waypoints(potential_flight_plan)

                self.approximate_timings_based_on_waypoint_eta(
                    flight_plan=potential_flight_plan,
                    waypoint_eta=refuel_waypoint.start_time - datetime.timedelta(seconds=self.refuel_anticipation_buffer),
                    waypoint_id="critical"
                )

            # The best suited flight plan is the one with the fewest waypoints
            flight_plan_waypoint_counts = [
                len(potential_flight_plan.waypoints)
                for potential_flight_plan in dummy_potential_flight_plans
            ]

            priority_flight_plan_index = flight_plan_waypoint_counts.index(min(flight_plan_waypoint_counts))
            priority_flight_plan = dummy_potential_flight_plans[priority_flight_plan_index]
            print(f"Priority flight plan requires {priority_flight_plan.refuel_waypoint_count} refuel points")
            print(priority_flight_plan.to_dict())

            # This needs to be monitored to limit recursion
            calculated_flight_plans_per_waypoint_id[refuel_waypoint.id].append({
                'flight_plan': priority_flight_plan,
                'related_sub_flight_plans': (
                    self.create_refuel_flight_plans(priority_flight_plan, depth + 1)
                    if potential_flight_plan.refuel_waypoint_count
                    else {}
                )
            })

        return calculated_flight_plans_per_waypoint_id

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

        if len(distances) >= 2:
            assert distances[0] <= distances[1]

        return [
            distance[1]
            for distance in distances
        ]

    def get_bot_by_model(self, model: str) -> Optional[Bot]:
        """
        Get the bot object from the catalogue for a given model
        """
        for bot in self.bots:
            if bot.model == model:
                return bot

    def add_pre_giving_refuel_waypoint(self, flight_plan: FlightPlan):
        """
        For a given flight plan with a GIVING_RECHARGE action, add refuel waypoint in the previous leg
        """
        assert self.validate_flight_plan(flight_plan), "Invalid flight plan prior to adding pre-giving refuel waypoint"
        assert flight_plan.has_giving_recharge_waypoint
        print("Before adding pre-giving refuel waypoint")
        print(flight_plan.to_dict())

        # Find the GIVING_RECHARGE waypoint
        giving_recharge_index = flight_plan.giving_recharge_index

        # The previous waypoint should be an action, and the previous previous a leg
        assert flight_plan.waypoints[giving_recharge_index - 1].is_action
        assert flight_plan.waypoints[giving_recharge_index - 2].is_leg

        leg_index = giving_recharge_index - 2

        # We want to refuel sufficiently before we reach the recharge position
        bot = self.get_bot_by_model(flight_plan.bot_model)
        time_to_refuel_before_end_of_leg = (
            bot.flight_time
            - self.refuel_duration
            - self.remaining_flight_time_at_refuel
            - self.refuel_anticipation_buffer
            - 60 # An additional buffer
        )

        #THIS IS WRONG, AND ALSO CONSIDER THAT IF THE NEWLY CALCULATED RECHARGE POINT IS AT THE TOWER LOCATION, DONT BOTHER

        leg_waypoint = flight_plan.waypoints[giving_recharge_index - 2]
        leg_time = int(distance_between(leg_waypoint.from_pos, leg_waypoint.to_pos)/bot.speed)

        # We will split the leg into two legs with a refuel inbetween
        overshoot_ratio = (leg_time - time_to_refuel_before_end_of_leg) / leg_time
        overshoot_ratio = overshoot_ratio if overshoot_ratio > 0.5 else 0.5
        assert overshoot_ratio < 1

        split_position = find_middle_position_by_ratio(leg_waypoint.from_pos, leg_waypoint.to_pos, overshoot_ratio)

        # Create the refuel
        new_waypoint = ActionWaypoint(
            action='being_recharged',
            duration=self.refuel_duration
        )

        flight_plan.waypoints.insert(leg_index + 1, new_waypoint)

        # Create the second leg
        new_waypoint = LegWaypoint(
            cartesian_positions={
                'from': split_position,
                'to': leg_waypoint.cartesian_positions['to']
            }
        )

        flight_plan.waypoints.insert(leg_index + 2, new_waypoint)

        # Turn the leg into just the first leg
        leg_waypoint.cartesian_positions['to'] = split_position

        print("After adding pre-giving refuel waypoint")
        print(flight_plan.to_dict())
        assert self.validate_flight_plan(flight_plan)

    def create_transit_schedule(self):
        """
        Return a schedule for transporting a payload from tower A to tower B
        considering inflight refuels, tower based refuels, and waypoint optimisation.
        """
        pass

    def cancel_active_schedule(self, schedule: Schedule):
        """
        For a given schedule in progress, create flight plans to handle return to base for all active flights
        """
        pass
