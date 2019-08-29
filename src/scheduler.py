import math as maths
from typing import List, Optional, Dict, Generator
import json, datetime, random

from .schedule import Schedule
from .flight_plan import FlightPlan
from .partial_flight_plan import PartialFlightPlan
from .tower import Tower
from .waypoint import Waypoint
from .leg_waypoint import LegWaypoint
from .action_waypoint import ActionWaypoint
from .bot import BotSchema
from .payload_schema import PayloadSchema
from .resource_manager import ResourceManager
from .tools import distance_between, find_middle_position_by_ratio, Encoder


class Scheduler:
    def __init__(
        self,
        towers: List[Tower],
        bot_schemas: List[BotSchema],
        payload_schemas: List[PayloadSchema],
        bot_manager: ResourceManager,
        payload_manager: ResourceManager,
        refuel_duration: int,
        remaining_flight_time_at_refuel: int,
        refuel_anticipation_buffer: str
        ):

        # Tower objects with their inventories and availabilities
        self.towers = towers

        # List of defined bot types
        self.bot_schemas = bot_schemas

        # Schemas for payloads
        self.payloads_schemas = payload_schemas

        # The actual bot physical resource manager
        self.bot_manager = bot_manager

        # The actual payload physical resource manager
        self.payload_manager = payload_manager

        # The seconds that a refueler should arrive at the refuel location before the refueling
        self.refuel_anticipation_buffer = refuel_anticipation_buffer

        # The duration of the refuel, the refuel is considered complete at the end of this time
        self.refuel_duration = refuel_duration

        # The flight time a bot should have remaining when it initiates the refueling, it needs to be greater than the refuel_duration
        self.remaining_flight_time_at_refuel = remaining_flight_time_at_refuel

        # To track allocations made per flight plan, mapped to their related deallocator
        # This is like a mock db
        self.flight_plan_allocation_to_deallocator = {}

        assert remaining_flight_time_at_refuel > refuel_duration

    def determine_schedule_from_waypoint_eta(self, flight_plan: FlightPlan, waypoint_eta: datetime.datetime, waypoint_id: str) -> Schedule:
        """
        Determine the schedule based on the time the client wants the bot to reach a certain waypoint.
        If the schedules requires the first launch to be in the past, the schedule is marked as unapplicable.
        """
        assert waypoint_id in [waypoint.id for waypoint in flight_plan.waypoints]
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

        # TODO Determine if there is a bot available? or find the required payload type or id -> bot types
        # TODO Create transit schedule

        # For each refueling waypoint in the flight plan, create a resupply flight plan
        refuel_flight_plans_per_waypoint_id = self.create_refuel_flight_plans(flight_plan)

        schedule_dict = {
            'flight_plan': flight_plan,
            'related_sub_flight_plans': refuel_flight_plans_per_waypoint_id
        }

        schedule = Schedule(raw_schedule=schedule_dict)
        print(f"Schedule contains {len(schedule.flight_plans)} flight plans")
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

        schedule = Schedule(raw_schedule=schedule_dict)
        print(f"Schedule contains {len(schedule.flight_plans)} flight plans")
        return schedule

    def calculate_sourcing_schedule(self, schedule: Schedule) -> Schedule:
        pass

    def validate_flight_plan(self, flight_plan: FlightPlan):
        """
        Perform some basic assertions on the flight plan to ensure it will work
        """
        # The associated bot model needs to exist in our context
        assert flight_plan.bot_model in [bot.model for bot in self.bot_schemas], "Unknown bot model"

        # Make sure the flight plan starts at a tower
        assert flight_plan.starting_tower in [tower.id for tower in self.towers]
        assert flight_plan.finishing_tower in [tower.id for tower in self.towers]
        assert self.get_tower_by_id(flight_plan.starting_tower).position == flight_plan.waypoints[0].from_pos, "Starting point doesnt match first waypoint"
        assert self.get_tower_by_id(flight_plan.finishing_tower).position == flight_plan.waypoints[-1].to_pos, "Starting point doesnt match first waypoint"

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
                bot = self.get_bot_schema_by_model(flight_plan.bot_model)
                waypoint.end_time = waypoint.start_time + datetime.timedelta(seconds=distance_between(waypoint.from_pos, waypoint.to_pos)/bot.speed)

    def approximate_timings_based_on_waypoint_eta(self, flight_plan: FlightPlan, waypoint_eta: datetime.datetime, waypoint_id: str):
        """
        For a given flight plan and launch time, approximate the start and end time of each waypoint
        """
        # Find the index of the waypoint we are interested in
        index = [index for index, waypoint in enumerate(flight_plan.waypoints) if waypoint.id == waypoint_id].pop(0)
        initial_index = index

        bot = self.get_bot_schema_by_model(flight_plan.bot_model)

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

                    bot_schema = self.get_bot_schema_by_model(flight_plan.bot_model)
                    threshold = bot_schema.flight_time - self.remaining_flight_time_at_refuel - self.refuel_duration
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
                                # TODO MAKE THIS VARIABLE PART OF THE FLIGHT PLAN
                                refuel_in_parallel_with_payload = False

                                if refuel_in_parallel_with_payload and waypoint.is_payload_action:
                                    # We don't need to add additional time to the action waypoint unless necessary

                                    # TODO THIS IF-ELIF-ELSE ISNT CORRECT
                                    if overshoot > waypoint.duration:
                                        # Create the refueling waypoint
                                        new_waypoint = ActionWaypoint(
                                            action='being_recharged',
                                            duration=self.refuel_duration
                                        )

                                        flight_plan.waypoints.insert(index + 1, new_waypoint)
                                    elif overshoot == waypoint.duration:
                                        waypoint.action = "payload being_recharged"
                                    else:
                                        waypoint.duration = waypoint.duration - overshoot

                                        # Create the refueling waypoint
                                        new_waypoint = ActionWaypoint(
                                            action='payload being_recharged',
                                            duration=self.refuel_duration
                                        )

                                        flight_plan.waypoints.insert(index + 1, new_waypoint)
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
                    bot = self.get_bot_schema_by_model(flight_plan.bot_model)
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
                            positions={
                                'from': split_position,
                                'to': waypoint.positions['to']
                            }
                        )

                        flight_plan.waypoints.insert(index + 2, new_waypoint)

                        # Turn the leg into just the first leg
                        waypoint.positions['to'] = split_position
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
                        waypoint.position = self.get_tower_by_id(flight_plan.starting_tower).position
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
                    positions={
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
                    positions={
                        'from': waypoint.position,
                        'to': tower.position
                    }
                )
            ]

            # Each tower can multiple types of refueler models, so we will check each
            for bot_schema in self.bot_schemas:
                if bot_schema.is_refueler:
                    flight_plan = FlightPlan(
                        waypoints=[
                            waypoint.copy()
                            for waypoint in waypoints
                            ],
                        bot_model=bot_schema.model,
                        starting_tower=tower.id,
                        finishing_tower=tower.id
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
                        #print("This one is being recharged")
                        if waypoint.position and waypoint.position == giving_refuel_waypoint.position:
                            #print("And being recharged at the refuel location")
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
            print(f"Waypoint counts are {flight_plan_waypoint_counts}")
            """
            priority_flight_plan_index = flight_plan_waypoint_counts.index(min(flight_plan_waypoint_counts))
            priority_flight_plan = dummy_potential_flight_plans[priority_flight_plan_index]
            """
            minimum_waypoints = min(flight_plan_waypoint_counts)
            priority_waypoints = [
                potential_flight_plan
                for potential_flight_plan in dummy_potential_flight_plans
                if len(potential_flight_plan.waypoints) == minimum_waypoints
            ]

            priority_flight_plan = random.choice(priority_waypoints)


            #print(f"Priority flight plan requires {priority_flight_plan.refuel_waypoint_count} refuel points")
            #print(priority_flight_plan.to_dict())

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

    def get_nearest_towers_to_waypoint(self, waypoint: Waypoint, any: bool = False) -> List[Tower]:
        """
        For a given waypoint, return a list of towers with the first element being the closest
        if 'any', then look at either action or the 'to' position in a leg.
        if not 'any', we only accept action waypoints
        """
        if any:
            position = waypoint.position if waypoint.is_action else waypoint.to_pos
        else:
            assert waypoint.is_action
            position = waypoint.position

        distances = []
        print("Getting nearest towers")

        for tower in self.towers:
            distance = distance_between(position, tower.position)
            print(f"Distance between {position} and {tower.id} at {tower.position} is {distance}")
            distances.append((distance, tower))

        # We then sort by distance and return a list of towers with the first being the closest
        distances.sort(key=lambda value: value[0])
        print(f"Nearest is {distances[0][1].id}")
        if len(distances) >= 2:
            assert distances[0][0] <= distances[1][0]

        return [
            distance[1]
            for distance in distances
        ]

    def get_bot_schema_by_model(self, model: str) -> Optional[BotSchema]:
        """
        Get the bot object from the catalogue for a given model
        """
        for bot_schema in self.bot_schemas:
            if bot_schema.model == model:
                return bot_schema

    def get_tower_by_id(self, id: str) -> Optional[Tower]:
        """
        Get the tower for the given id
        """
        for tower in self.towers:
            if tower.id == id:
                return tower

    def add_pre_giving_refuel_waypoint(self, flight_plan: FlightPlan):
        """
        For a given flight plan with a GIVING_RECHARGE action, add refuel waypoint in the previous leg
        """
        assert self.validate_flight_plan(flight_plan), "Invalid flight plan prior to adding pre-giving refuel waypoint"
        assert flight_plan.has_giving_recharge_waypoint
        #print("Before adding pre-giving refuel waypoint")
        #print(flight_plan.to_dict())

        # Find the GIVING_RECHARGE waypoint
        giving_recharge_index = flight_plan.giving_recharge_index

        # The previous waypoint should be an action, and the previous previous a leg
        assert flight_plan.waypoints[giving_recharge_index - 1].is_action
        assert flight_plan.waypoints[giving_recharge_index - 2].is_leg

        leg_index = giving_recharge_index - 2

        # We want to refuel sufficiently before we reach the recharge position
        bot = self.get_bot_schema_by_model(flight_plan.bot_model)
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
            positions={
                'from': split_position,
                'to': leg_waypoint.positions['to']
            }
        )

        flight_plan.waypoints.insert(leg_index + 2, new_waypoint)

        # Turn the leg into just the first leg
        leg_waypoint.positions['to'] = split_position

        #print("After adding pre-giving refuel waypoint")
        #print(flight_plan.to_dict())
        assert self.validate_flight_plan(flight_plan)

    def create_transit_schedule(self, payload_id: str, from_tower: Tower, to_tower: Tower, arrival_time: datetime.datetime, high_priority: bool) -> Schedule:
        """
        Return a schedule for transporting a payload from tower A to tower B
        considering inflight refuels, tower based refuels, and waypoint optimisation.
        If the schedule is high priority, it will go from tower A to tower B directly

        #TODO, For now we dont consider the flight gradients
        """
        # Confirm the payload_id is located at the prescribed tower

        # TODO if not high priority, find the best route passing through different towers

        # Create a flight plan for that route considering bot cruise altitude TODO (and climb rates)
        flight_plan_meta = FlightPlanMeta(
            payload_id=payload_id
        )

        waypoints = [
            LegWaypoint( # Leg to cruising altitude
                positions={
                    'from': from_tower.position,
                    'to': [
                        from_tower.position[0],
                        from_tower.position[1],
                        from_tower.position[2] + bot.cruising_altitude
                    ]
                }
            ),
            LegWaypoint( # Main cruise between the two towers
                positions={
                    'from': [
                        from_tower.position[0],
                        from_tower.position[1],
                        from_tower.position[2] + bot.cruising_altitude
                    ],
                    'to': [
                        to_tower.position[0],
                        to_tower.position[1],
                        to_tower.position[2] + bot.cruising_altitude
                    ]
                }
            ),
            LegWaypoint( # Landing leg
                positions={
                    'from': [
                        to_tower.position[0],
                        to_tower.position[1],
                        to_tower.position[2] + bot.cruising_altitude
                    ],
                    'to': to_tower.position
                }
            )
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            starting_tower=from_tower.id,
            finishing_tower=to_tower.id,
            meta=flight_plan_meta
        )

        # Create the schedule refuel plansP
        pass

    def cancel_active_schedule(self, schedule: Schedule, now: datetime.datetime):
        """
        For a given schedule in progress, create flight plans to handle return to base for all active flights
        """
        pass

    def create_flight_plan_from_partial(self, partial_flight_plan: PartialFlightPlan, starting_tower: Tower, finishing_tower: Tower) -> FlightPlan:
        """
        For a given partial flight plan, add the legs to make it into a full flight plan
        """
        waypoints = [
            waypoint.copy()
            for waypoint in partial_flight_plan.waypoints
        ]

        first_leg = LegWaypoint(
            positions={
                'from': starting_tower.position,
                'to': (
                    waypoints[0].positions['from']
                    if waypoints[0].is_leg
                    else waypoints[0].position
                )
            }
        )
        waypoints.insert(0, first_leg)

        last_leg = LegWaypoint(
            positions={
                'from': (
                    waypoints[-1].positions['to']
                    if waypoints[-1].is_leg
                    else waypoints[-1].position
                ),
                'to': finishing_tower.position
            }
        )
        waypoints.append(last_leg)

        flight_plan = FlightPlan(
            id=partial_flight_plan.id,
            waypoints=waypoints,
            bot_model=partial_flight_plan.bot_model,
            starting_tower=starting_tower.id,
            finishing_tower=finishing_tower.id
        )

        return flight_plan

    def generate_potential_flight_plans_from_partial(self, partial_flight_plan: PartialFlightPlan) -> Generator[FlightPlan, None, None]:
        """
        Return a generator for producing potential flight plans from a partial
        with the closest tower being highest priority
        """
        nearest_starting_towers = self.get_nearest_towers_to_waypoint(partial_flight_plan.waypoints[0], any=True)
        nearest_finishing_towers = self.get_nearest_towers_to_waypoint(partial_flight_plan.waypoints[-1], any=True)

        class PlanGenerator:
            def __init__(this):
                this.starts = nearest_starting_towers
                this.finishes = nearest_finishing_towers
                this.to_change = 'starts'
                this.current_start = 0
                this.current_finish = 0

            def change_start(this):
                this.to_change = 'starts'

            def change_finish(this):
                this.to_change = 'finishes'

            def __iter__(this):
                return this

            def __next__(this):
                if not (this.current_start == 0 and this.current_finish == 0):
                    if this.to_change == 'starts':
                        this.current_start += 1
                    elif this.to_change == 'finishes':
                        this.current_finish += 1
                try:
                    return self.create_flight_plan_from_partial(partial_flight_plan, this.starts[this.current_start], this.finishes[this.current_finish])
                except IndexError:
                    raise StopIteration()

        return PlanGenerator()

    def determine_schedule_for_partial_flight_plans_orchestration(self, partial_flight_plans: List[PartialFlightPlan], critical_time: datetime.datetime) -> Schedule:
        """
        For a given list of PartialFlightPlans and a critical time, determine the schedule and sub flight plans required
        """
        # For each partial flight plan, determine the closest tower and create a full flight plan
        flight_plans = []
        for partial_flight_plan in partial_flight_plans:
            potential_flight_plans = self.generate_potential_flight_plans_from_partial(partial_flight_plan)
            # TODO Here will be come priority logic on the potential plans
            full_flight_plan = next(potential_flight_plans)
            flight_plans.append(full_flight_plan)

        # For each full flight plan, determine a schedule
        schedules = []
        for flight_plan in flight_plans:
            schedule = self.determine_schedule_from_waypoint_eta(
                flight_plan=flight_plan,
                waypoint_eta=critical_time,
                waypoint_id=flight_plan.waypoints[1].id
            )
            schedules.append(schedule)

        # Merge the schedules
        schedule = Schedule.from_schedules(schedules)
        return schedule

    @staticmethod
    def strip_flight_plan(flight_plan: FlightPlan):
        """
        For a given flight plan, remove any scheduler generated attributes
        """
        # Remove timings
        for waypoint in flight_plan.waypoints:
            if waypoint.is_approximated:
                waypoint.start_time = None
                waypoint.end_time = None

        # Remove refuel waypoints
        finished = False
        while not finished:
            for index, waypoint in enumerate(flight_plan.waypoints):
                if index is 0:
                    continue

                # Handle any refuel injection waypoints
                if waypoint.is_action and waypoint.is_being_recharged:
                    if flight_plan.waypoints[index - 1].is_leg and flight_plan.waypoints[index + 1].is_leg:
                        # Remove the waypoint and rejoin the legs
                        flight_plan.waypoints[index - 1].positions['to'] = flight_plan.waypoints[index + 1].to_pos
                        flight_plan.waypoints.pop(index)
                        flight_plan.waypoints.pop(index + 1)
                        break
                    elif flight_plan.waypoints[index + 1].is_action:
                        # TODO, here we might need to consider whether the action is being overlapped or not
                        flight_plan.waypoints.pop(index)
                        break
                    else:
                        raise NotImplementedError()
            else:
                finished = True

        # Remove any launching waiting buffers
        first_waypoint = flight_plan.waypoints[0]
        if first_waypoint.generated and first_waypoint.is_leg:
            # This is a waiting leg for early launchs

            # If the next waypoint is a generated action waypoint, then it is part of the early launch buffer
            second_waypoint = flight_plan.waypoints[1]
            if second_waypoint.is_action and second_waypoint.generated:
                flight_plan.waypoints.pop(1)

            # Rejoin the legs
            flight_plan.waypoints[1].positions['from'] = first_waypoint.from_pos

            # Delete the first leg
            flight_plan.waypoints.pop(0)

        # Remove any landing buffers
        last_waypoint = flight_plan.waypoints[-1]
        if last_waypoint.generated and last_waypoint.is_leg:
            # This is a waiting leg for late landing

            # If the waypoint before is a generated action waypoint, then it is part of the early launch buffer
            second_to_last_waypoint = flight_plan.waypoints[-2]
            if second_to_last_waypoint.is_action and second_to_last_waypoint.generated:
                second_to_last_waypoint.waypoints.pop(-2)

            # Rejoin the legs
            flight_plan.waypoints[-2].positions['to'] = last_waypoint.to_pos

            # Delete the last leg
            flight_plan.waypoints.pop(-1)

    def stretch_flight_plan(self, flight_plan: FlightPlan, start_delta: datetime.datetime, end_delta: datetime.datetime):
        """
        For a given flight plan, add buffer waypoints at the beginning and end of the flight plan
        """
        launch_tower = self.get_tower_by_id(flight_plan.starting_tower)
        landing_tower = self.get_tower_by_id(flight_plan.finishing_tower)
        bot = self.get_bot_schema_by_model(flight_plan.bot_model)

        # TODO, Really the towers should define their waiting areas
        early_launch_leg = LegWaypoint(
            positions={
                'from': launch_tower.position,
                'to': [launch_tower.position[0], launch_tower.position[1], launch_tower.position[2] + 20]
            },
            generated=True
        )
        # Insert the new first leg and modify the existing leg
        flight_plan.waypoints.insert(0, early_launch_leg)
        flight_plan.waypoints[1].positions['from'] = early_launch_leg.to_pos

        early_launch_leg_time = distance_between(early_launch_leg.to_pos, early_launch_leg.from_pos) / bot.speed

        # For the remaining time difference, create a waiting action
        if early_launch_leg_time > start_delta:
            early_launch_waiting_action = ActionWaypoint(
                duration=(start_delta-early_launch_leg_time).seconds,
                action="waiting",
                generated=True
            )
            flight_plan.waypoints.insert(1, early_launch_waiting_action)

        late_landing_leg = LegWaypoint(
            positions={
                'from': [landing_tower.position[0], landing_tower.position[1], landing_tower.position[2] + 20],
                'to': launch_tower.position
            },
            generated=True
        )

        # Insert the new final leg and modify the existing final leg
        flight_plan.waypoints.append(late_landing_leg)
        flight_plan.waypoints[-2].positions['to'] = late_landing_leg.from_pos

        late_landing_leg_time = distance_between(late_landing_leg.to_pos, late_landing_leg.from_pos) / bot.speed

        # For the remaining time difference, create a waiting action
        if late_landing_leg_time > end_delta:
            late_landing_waiting_action = ActionWaypoint(
                duration=(end_delta-late_landing_leg_time).seconds,
                action="waiting",
                generated=True
            )
            flight_plan.waypoints.insert(-2, late_landing_waiting_action)

    def fit_flight_plan_into_tower_allocations(self, flight_plan: FlightPlan) -> bool:
        """
        For a given flight plan, manipulate it to fit into the available launch and landing allocation slots
        This operates on the FlightPlan in place and returns a boolean if it is able to and has successfully done so
        """
        launch_tower = self.get_tower_by_id(flight_plan.starting_tower)
        landing_tower = self.get_tower_by_id(flight_plan.finishing_tower)

        # Find the nearest launch window (looking before the launch time)
        nearest_intervals = launch_tower.get_nearest_intervals_to_window_end(flight_plan.start_time)
        if not nearest_intervals:
            print(f"No intervals available for launch day {flight_plan.start_time} at tower {launch_tower} flight plan {flight_plan.id}")
            return False

        # A list of tuples of (interval, window start, window end) for each interval
        nearest_windows = [
            (interval,) + launch_tower.get_window_for_interval(interval)
            for interval in nearest_intervals
        ]

        # Consider only the windows before the launch time
        nearest_windows = [
            nearest_window
            for nearest_window in nearest_windows
            if nearest_window[2] <= flight_plan.start_time
        ]

        if not nearest_intervals:
            print(f"No intervals available for launch window of flight plan {flight_plan.id}")
            return False

        # Consider the first nearest window
        nearest_start_window = nearest_windows[0]

        # Now find the nearest landing window (looking after the landing time)
        nearest_intervals = landing_tower.get_nearest_intervals_to_window_start(flight_plan.end_time)
        if not nearest_intervals:
            print(f"No intervals available for landing day {flight_plan.end_time} at tower {landing_tower} flight plan {flight_plan.id}")
            return False

        # A list of tuples of (interval, window start, window end) for each interval
        nearest_windows = [
            (interval,) + landing_tower.get_window_for_interval(interval)
            for interval in nearest_intervals
        ]

        # Consider only the windows after the landing time
        nearest_windows = [
            nearest_window
            for nearest_window in nearest_windows
            if nearest_window[2] >= flight_plan.end_time
        ]

        if not nearest_intervals:
            print(f"No intervals available for landing window of flight plan {flight_plan.id}")
            return False

        # Consider the first nearest window
        nearest_end_window = nearest_windows[0]

        # Copy the flight plan and strip it to make it raw
        flight_plan_copy = flight_plan.copy()
        self.strip_flight_plan(flight_plan_copy)

        # Stretch the flight plan
        self.stretch_flight_plan(
            flight_plan=flight_plan_copy,
            start_delta=flight_plan.start_time - nearest_start_window[2],
            end_delta=nearest_end_window[1] - flight_plan.end_time
        )

        # Recalculate the flight plan to add the refueling points
        self.recalculate_flight_plan(flight_plan_copy)

        # If the recalculated flight plan has the same number of refuel waypoint as the original, apply it to the original
        if flight_plan_copy.refuel_waypoint_count == flight_plan.refuel_waypoint_count:
            flight_plan.copy_from(flight_plan_copy)
            return True

        # Else recurse on the stretched flight plan and then apply it to the original
        return self.fit_flight_plan_into_tower_allocations(flight_plan_copy)

    def allocate_flight_plan(self, flight_plan: FlightPlan) -> bool:
        """
        For a given flight plan, attempt to make all the resource allocations and fallback if it fails.
        Calls to this function should be wrapped in a try-except to catch AllocationError(s).
        If successful, the allocations are stored in self.flight_plan_allocation_to_deallocator
        """
        def deallocate(allocation_id_to_deallocator: dict):
            """
            Mini function for deallocating any allocations made if all allocations cant be made
            """
            for deallocation_key, deallocator in allocation_id_to_deallocator.items():
                deallocator(deallocation_key)

        allocation_id_to_deallocator = {}
        launch_tower = self.get_tower_by_id(flight_plan.starting_tower)
        landing_tower = self.get_tower_by_id(flight_plan.finishing_tower)

        # Find the nearest launch window (looking before the launch time)
        nearest_intervals = launch_tower.get_nearest_intervals_to_window_end(flight_plan.start_time)
        if not nearest_intervals:
            print(f"No intervals available for launch day {flight_plan.start_time} at tower {launch_tower} flight plan {flight_plan.id}")
            return False

        # A list of tuples of (interval, window start, window end) for each interval
        nearest_windows = [
            (interval,) + launch_tower.get_window_for_interval(interval)
            for interval in nearest_intervals
        ]

        nearest_window = nearest_windows[0]
        if nearest_window[2] == flight_plan.start_time:
            try:
                allocation_id = launch_tower.allocate_launch(
                    flight_plan_id=flight_plan.id,
                    date=flight_plan.start_time,
                    interval=nearest_window[0]
                )
                allocation_id_to_deallocator[allocation_id] = launch_tower.deallocate_launch
            except Exception as e:
                print(f"Failed to allocate launch window for {flight_plan.id}")
                raise e from None
        else:
            print(f"Failed to allocate launch window for {flight_plan.id}, interval mismatch")
            return False

        # Now find the nearest landing window (looking after the landing time)
        nearest_intervals = landing_tower.get_nearest_intervals_to_window_start(flight_plan.end_time)
        if not nearest_intervals:
            print(f"No intervals available for landing day {flight_plan.end_time} at tower {landing_tower} flight plan {flight_plan.id}")
            return False

        # A list of tuples of (interval, window start, window end) for each interval
        nearest_windows = [
            (interval,) + landing_tower.get_window_for_interval(interval)
            for interval in nearest_intervals
        ]

        nearest_window = nearest_windows[0]
        if nearest_window[1] == flight_plan.end_time:
            try:
                allocation_id = landing_tower.allocate_landing(
                    flight_plan_id=flight_plan.id,
                    date=flight_plan.start_time,
                    interval=nearest_window[0]
                )
                allocation_id_to_deallocator[allocation_id] = landing_tower.deallocate_landing
            except Exception as e:
                print(f"Failed to allocate landing for {flight_plan.id}")
                deallocate(allocation_id_to_deallocator)
                raise e from None
        else:
            print(f"Failed to allocate landing window for {flight_plan.id}, interval mismatch")
            deallocate(allocation_id_to_deallocator)
            return False

        # Store the allocation data in the class context
        self.flight_plan_allocation_to_deallocator[flight_plan.id] = allocation_id_to_deallocator
        return True
