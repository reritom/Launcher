import math as maths
from typing import List, Optional, Dict, Generator, Set
import json, datetime, random
import logging

logger = logging.getLogger(__name__)

from .schedule import Schedule
from .flight_plan import FlightPlan
from .flight_plan_meta import FlightPlanMeta
from .partial_flight_plan import PartialFlightPlan
from .tower import Tower
from .waypoint import Waypoint
from .leg_waypoint import LegWaypoint
from .action_waypoint import ActionWaypoint
from .bot_schema import BotSchema
from .bot import Bot
from .payload_schema import PayloadSchema
from .payload import Payload
from .resource_manager import ResourceManager
from .resource_allocator import AllocationError
from .tools import distance_between, find_middle_position_by_ratio, Encoder, ScheduleError, TrackerError, without_microseconds
from .resource_tools import get_payload_schema_by_model, print_waypoints, get_bot_schema_by_model, get_waypoint_duration

class Scheduler:
    def __init__(
        self,
        towers: List[Tower],
        bot_schemas: List[BotSchema],
        payload_schemas: List[PayloadSchema],
        bot_manager: ResourceManager,
        payload_manager: ResourceManager,
        refuel_duration: datetime.timedelta,
        remaining_flight_time_at_refuel: datetime.timedelta,
        refuel_anticipation_buffer: datetime.timedelta
        ):

        # Tower objects with their inventories and availabilities
        self.towers = towers

        # List of defined bot types
        self.bot_schemas = bot_schemas

        # Schemas for payloads
        self.payload_schemas = payload_schemas

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

        # The maximum seconds that a flight plan can be stretched to try and make it fit into tower launch and landing windows
        self.maximum_flight_plan_stretch_duration = datetime.timedelta(seconds=500)

        # To track allocations made per flight plan, mapped to their related deallocator
        # This is like a mock db
        self.flight_plan_allocation_to_deallocator = {}

        assert remaining_flight_time_at_refuel > refuel_duration

    def determine_schedule(
        self,
        flight_plan: FlightPlan,
        launch_time: datetime.datetime = None,
        landing_time: datetime.datetime = None,
        waypoint_eta: datetime.datetime = None,
        waypoint_id: str = None
        ) -> Schedule:
        """
        For a given flight plan, determine when all the supporting bots need to be deployed and their
        respective flight plans
        """
        assert launch_time or landing_time or (waypoint_eta and waypoint_id)
        assert flight_plan.has_meta

        # The associated bot model needs to exist in our context
        assert flight_plan.meta.bot_model.model in [bot.model for bot in self.bot_schemas], f"Unknown bot model {flight_plan.meta.bot_model}"

        self.validate_flight_plan(flight_plan)

        self.flight_plan_allocation_to_deallocator[flight_plan.id] = {}

        # Add an refueling waypoints to the flight plan
        logger.info(f"Initial recalculation for {flight_plan.id}")
        self.recalculate_flight_plan(flight_plan)

        # Flight plans don't consider absolute timings, so here will will add some approximates
        if launch_time:
            self.approximate_timings(flight_plan, launch_time)
        elif waypoint_eta and waypoint_id:
            assert waypoint_id in [waypoint.id for waypoint in flight_plan.waypoints]
            self.approximate_timings_based_on_waypoint_eta(
                flight_plan=flight_plan,
                waypoint_id=waypoint_id,
                waypoint_eta=waypoint_eta
            )
        elif landing_time:
            self.approximate_timings_based_on_landing_time(
                flight_plan=flight_plan,
                landing_time=landing_time
            )

        # Add the position to the action waypoints
        self.add_positions_to_action_waypoints(flight_plan)

        # Attempt to stretch the flight plan to fit it into launch and landing slots
        logger.info("Attempting to fit flight plan into tower allocations from determine_schedule")
        if not self.fit_flight_plan_into_tower_allocations(flight_plan):
            self.delete_allocations_for_flight_plan(flight_plan_id=flight_plan.id)
            logger.error(f"Failed to fit flight plan {flight_plan.id} into tower allocations")
            raise ScheduleError("Unable to fit flight plan into tower launch and landing windows")

        logger.info("Successfully fit the flight plan into the allocations")

        # The allocation ids are stored in self.flight_plan_allocation_to_deallocator
        allocation_successful = self.allocate_flight_plan(flight_plan)

        if not allocation_successful:
            logger.error(f"Allocation of flight plan {flight_plan.id} unsuccessful, deleting allocations")
            self.delete_allocations_for_flight_plan(flight_plan_id=flight_plan.id)
            raise ScheduleError(f"Failed to allocate flight plan {flight_plan.id}")

        flight_plan_start_tower = self.get_tower_by_id(flight_plan.starting_tower)
        flight_plan_finish_tower = self.get_tower_by_id(flight_plan.finishing_tower)
        assert flight_plan_start_tower is not None
        assert flight_plan_finish_tower is not None

        # We might need a transit schedule, so we initialise that here
        transit_schedule = None

        if flight_plan.meta.payload_id:
            # Is it available now?
            logger.debug(f"Payload id {flight_plan.meta.payload_id} trackers are {self.payload_manager.trackers[flight_plan.meta.payload_id].tracker}")
            available = self.is_payload_available(
                payload_id=flight_plan.meta.payload_id,
                from_datetime=flight_plan.start_time - datetime.timedelta(seconds=flight_plan_start_tower.launch_time),
                to_datetime=flight_plan.end_time + datetime.timedelta(seconds=flight_plan_finish_tower.landing_time)
            )
            logger.debug(f"Payload id {flight_plan.meta.payload_id} trackers are {self.payload_manager.trackers[flight_plan.meta.payload_id].tracker}")

            if not available:
                self.delete_allocations_for_flight_plan(flight_plan_id=flight_plan.id)
                raise ScheduleError("Specified payload id unavailable for given flight plan period")

            payload_tower = self.get_payload_tower_for_given_time(
                payload_id=flight_plan.meta.payload_id,
                reference_time=flight_plan.start_time
            )

            logger.info(f"Allocating payload {flight_plan.meta.payload_id}")
            payload_allocation_id = self.payload_manager.allocate_resource(
                resource_id=flight_plan.meta.payload_id,
                from_datetime=flight_plan.start_time - datetime.timedelta(seconds=flight_plan_start_tower.launch_time),
                to_datetime=flight_plan.end_time + datetime.timedelta(seconds=flight_plan_finish_tower.landing_time)
            )

            # Add the allocation to the context
            self.flight_plan_allocation_to_deallocator[flight_plan.id][payload_allocation_id] = self.payload_manager.allocator.delete_allocation

            # Is it located at the start tower or do we need a transit schedule?
            if payload_tower != flight_plan_start_tower:
                # We need a transit schedule
                transit_schedule = self.create_transit_schedule(
                    from_tower=payload_tower,
                    to_tower=flight_plan_start_tower,
                    arrival_time=flight_plan.start_time - datetime.timedelta(hours=1), # TODO, actually determine the best value for this
                    high_priority=True, # Actually determine and implement this
                    payload_id=flight_plan.meta.payload_id
                )

                # Add all the allocation from the subflight plans to the allocation for this flight plan
                for sub_flight_plan in transit_schedule.flight_plans:
                    self.flight_plan_allocation_to_deallocator[flight_plan.id].update(
                        self.flight_plan_allocation_to_deallocator[sub_flight_plan.id]
                    )

        elif flight_plan.meta.payload_model:
            # Which ids are available?
            available_payloads = self.get_available_payloads_for_given_window(
                payload_model=flight_plan.meta.payload_model.model,
                from_datetime=flight_plan.start_time - datetime.timedelta(seconds=flight_plan_start_tower.launch_time),
                to_datetime=flight_plan.end_time + datetime.timedelta(seconds=flight_plan_finish_tower.landing_time)
            )
            logger.debug(f"Available payloads for model {flight_plan.meta.payload_model} are {[payload.id for payload in available_payloads]}")

            if not available_payloads:
                self.delete_allocations_for_flight_plan(flight_plan_id=flight_plan.id)
                logger.error(f"No available payloads for {flight_plan.id} with payload model {flight_plan.meta.payload_model.model}")
                raise ScheduleError("No payloads available for specified model")

            # Are any of them located at this tower?
            # Which are available at our tower
            available_at_this_tower = [
                payload
                for payload in available_payloads
                if self.get_payload_tower_for_given_time(
                    payload_id=payload.id,
                    reference_time=flight_plan.start_time
                ) == flight_plan_start_tower
            ]

            if available_at_this_tower:
                payload_allocation_id = self.payload_manager.allocate_resource(
                    resource_id=available_at_this_tower[0].id,
                    from_datetime=flight_plan.start_time - datetime.timedelta(seconds=flight_plan_start_tower.launch_time),
                    to_datetime=flight_plan.end_time + datetime.timedelta(seconds=flight_plan_finish_tower.landing_time),
                    related_flight_plan=flight_plan.id,
                    from_tower=flight_plan_start_tower.id,
                    to_tower=flight_plan_finish_tower.id
                )

                # Add this allocation to the context
                self.flight_plan_allocation_to_deallocator[flight_plan.id][payload_allocation_id] = self.payload_manager.allocator.delete_allocation
            else:
                # We need an empty transit

                # Sort by the payload by distance from their current tower to our starting tower
                available_payloads.sort(
                    key=lambda payload: distance_between(
                        self.get_payload_tower_for_given_time(
                            payload_id=payload.id,
                            reference_time=flight_time.start_time
                        ).position,
                        flight_plan_start_tower.position
                    )
                )

                for payload in available_payloads:
                    from_tower = self.get_payload_tower_for_given_time(
                        payload_id=payload.id,
                        reference_time=flight_time.start_time
                    )

                    try:
                        allocation_id = self.payload_manager.allocate_resource(
                            resource_id=payload.id,
                            from_datetime=flight_plan.start_time - datetime.timedelta(seconds=flight_plan_start_tower.launch_time),
                            to_datetime=flight_plan.end_time + datetime.timedelta(seconds=flight_plan_finish_tower.landing_time),
                            related_flight_plan=flight_plan.id,
                            from_tower=flight_plan_start_tower.id,
                            to_tower=flight_plan_finish_tower.id
                        )

                        # Add the allocation to the context
                        self.flight_plan_allocation_to_deallocator[flight_plan.id][allocation_id] = self.payload_manager.allocator.delete_allocation
                    except AllocationError as e:
                        logger.warning(f"Failed to allocate payload {e}, will look at next")
                        continue

                    try:
                        transit_schedule = self.create_transit_schedule(
                            from_tower=from_tower,
                            to_tower=flight_plan_start_tower,
                            arrival_time=flight_plan.start_time - datetime.timedelta(hours=1), # TODO, actually determine the best value for this
                            high_priority=True, # Actually determine and implement this
                            payload_id=payload.id
                        )

                        # Add all the allocation from the subflight plans to the allocation for this flight plan
                        for sub_flight_plan in transit_schedule.flight_plans:
                            self.flight_plan_allocation_to_deallocator[flight_plan.id].update(
                                self.flight_plan_allocation_to_deallocator[sub_flight_plan.id]
                            )
                        break
                    except ScheduleError as e:
                        logger.warning(f"Failed to create transit schedule for payload {payload_id_index} / {len(available_ids)}, will try the next")

                        # Delete the allocation we just made for the payload
                        self.delete_allocations_for_flight_plan(
                            flight_plan_id=flight_plan.id,
                            allocation_id=allocation_id
                        )
                        continue
                else:
                    self.delete_allocations_for_flight_plan(flight_plan_id=flight_plan.id)
                    raise ScheduleError("Unable to create transit schedule")
        elif flight_plan.meta.bot_model:
            logger.info(f"Creating schedule by bot model for flight plan {flight_plan.id}")
            # Is there a bot available?
            available_bots = self.get_available_bots_for_given_window(
                bot_model=flight_plan.meta.bot_model.model,
                from_datetime=flight_plan.start_time - datetime.timedelta(seconds=flight_plan_start_tower.launch_time),
                to_datetime=flight_plan.end_time + datetime.timedelta(seconds=flight_plan_finish_tower.landing_time)
            )

            if not available_bots:
                self.delete_allocations_for_flight_plan(flight_plan_id=flight_plan.id)
                raise ScheduleError(f"No available bots for specified model {flight_plan.meta.bot_model}")

            # Which are available at our tower
            available_at_this_tower = [
                bot
                for bot in available_bots
                if self.get_bot_tower_for_given_time(
                    bot_id=bot.id,
                    reference_time=flight_plan.start_time
                ) == flight_plan_start_tower
            ]

            if available_at_this_tower:
                payload_allocation_id = self.bot_manager.allocate_resource(
                    resource_id=available_at_this_tower[0].id,
                    from_datetime=flight_plan.start_time - datetime.timedelta(seconds=flight_plan_start_tower.launch_time),
                    to_datetime=flight_plan.end_time + datetime.timedelta(seconds=flight_plan_finish_tower.landing_time),
                    related_flight_plan=flight_plan.id,
                    from_tower=flight_plan_start_tower.id,
                    to_tower=flight_plan_finish_tower.id
                )

                # Add this allocation to the context
                self.flight_plan_allocation_to_deallocator[flight_plan.id][payload_allocation_id] = self.payload_manager.allocator.delete_allocation
            else:
                # We need an empty transit

                # Sort by the bots by distance from their current tower to our starting tower
                available_bots.sort(
                    key=lambda bot: distance_between(
                        self.get_bot_tower_for_given_time(
                            bot_id=bot.id,
                            reference_time=flight_plan.start_time
                        ).position,
                        flight_plan_start_tower.position
                    )
                )

                for bot_id_index, bot in enumerate(available_bots):
                    from_tower = self.get_bot_tower_for_given_time(
                        bot_id=bot.id,
                        reference_time=flight_plan.start_time
                    )

                    try:
                        allocation_id = self.bot_manager.allocate_resource(
                            resource_id=bot.id,
                            from_datetime=flight_plan.start_time - datetime.timedelta(seconds=flight_plan_start_tower.launch_time),
                            to_datetime=flight_plan.end_time + datetime.timedelta(seconds=flight_plan_finish_tower.landing_time),
                            related_flight_plan=flight_plan.id,
                            from_tower=flight_plan_start_tower.id,
                            to_tower=flight_plan_finish_tower.id
                        )

                        # Add the allocation to the context
                        self.flight_plan_allocation_to_deallocator[flight_plan.id][allocation_id] = self.payload_manager.allocator.delete_allocation
                    except AllocationError as e:
                        logger.warning(f"Failed to allocate bot {e}, will try the next")
                        continue

                    try:
                        transit_schedule = self.create_transit_schedule(
                            from_tower=from_tower,
                            to_tower=flight_plan_start_tower,
                            arrival_time=flight_plan.start_time - datetime.timedelta(hours=1), # TODO, actually determine the best value for this
                            high_priority=True, # Actually determine and implement this
                            bot_id=bot.id
                        )

                        # Add all the allocation from the subflight plans to the allocation for this flight plan
                        for sub_flight_plan in transit_schedule.flight_plans:
                            self.flight_plan_allocation_to_deallocator[flight_plan.id].update(
                                self.flight_plan_allocation_to_deallocator[sub_flight_plan.id]
                            )
                        break
                    except ScheduleError as e:
                        logger.warning(f"Failed to create transit schedule {bot_id_index} / {len(available_ids)}, will try the next")

                        # Delete the allocation we just made for the payload
                        self.delete_allocations_for_flight_plan(
                            flight_plan_id=flight_plan.id,
                            allocation_id=allocation_id
                        )
                        continue

                else:
                    self.delete_allocations_for_flight_plan(flight_plan_id=flight_plan.id)
                    raise ScheduleError("Unable to create transit schedule for bot model")

        # For each refueling waypoint in the flight plan, create a resupply flight plan
        if flight_plan.refuel_waypoints:
            refuel_flight_plans_per_waypoint_id = self.create_refuel_flight_plans(flight_plan)
        else:
            refuel_flight_plans_per_waypoint_id = {}

        schedule_dict = {
            'flight_plan': flight_plan,
            'related_sub_flight_plans': refuel_flight_plans_per_waypoint_id
        }

        schedule = Schedule(raw_schedule=schedule_dict)
        logger.debug(f"Schedule contains {len(schedule.flight_plans)} flight plans")
        return schedule

    def validate_flight_plan(self, flight_plan: FlightPlan):
        """
        Perform some basic assertions on the flight plan to ensure it will work
        """
        starting_tower = self.get_tower_by_id(flight_plan.starting_tower)
        finishing_tower = self.get_tower_by_id(flight_plan.finishing_tower)
        assert starting_tower
        assert finishing_tower

        # Make sure the flight plan starts at a tower
        assert flight_plan.starting_tower in [tower.id for tower in self.towers]
        assert flight_plan.finishing_tower in [tower.id for tower in self.towers]
        assert starting_tower.position == flight_plan.waypoints[0].from_pos, "Starting point doesnt match first waypoint"
        assert finishing_tower.position == flight_plan.waypoints[-1].to_pos, f"Finishing point {finishing_tower.position} doesnt match final waypoint {flight_plan.waypoints[-1].to_pos}"

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
        assert flight_plan.meta.bot_model is not None

        for index, waypoint in enumerate(flight_plan.waypoints):
            waypoint.start_time = launch_time if not index else flight_plan.waypoints[index - 1].end_time

            if waypoint.is_action:
                waypoint.end_time = waypoint.start_time + waypoint.duration
            elif waypoint.is_leg:
                bot = flight_plan.meta.bot_model
                waypoint.end_time = waypoint.start_time + datetime.timedelta(seconds=distance_between(waypoint.from_pos, waypoint.to_pos)/bot.speed)

    def approximate_timings_based_on_landing_time(self, flight_plan: FlightPlan, landing_time: datetime.datetime):
        """
        For a given flight plan and landing time, approximate the start and end time of each waypoint
        We cheat by adding an waypoint at the end and then calculating based on waypoint eta
        """
        assert flight_plan.meta.bot_model is not None

        dummy_waypoint = ActionWaypoint(
            action='dummy',
            duration=datetime.timedelta(seconds=1)
        )

        flight_plan.waypoints.append(dummy_waypoint)

        # Calculate normally
        self.approximate_timings_based_on_waypoint_eta(
            flight_plan=flight_plan,
            waypoint_eta=landing_time,
            waypoint_id=flight_plan.waypoints[-1].id
        )

        # Delete the dummy
        flight_plan.waypoints.pop(-1)

    def approximate_timings_based_on_waypoint_eta(self, flight_plan: FlightPlan, waypoint_eta: datetime.datetime, waypoint_id: str):
        """
        For a given flight plan and launch time, approximate the start and end time of each waypoint
        """
        assert flight_plan.meta.bot_model is not None
        assert waypoint_id and waypoint_eta

        # Find the index of the waypoint we are interested in
        index = [index for index, waypoint in enumerate(flight_plan.waypoints) if waypoint.id == waypoint_id].pop(0)
        initial_index = index

        bot = flight_plan.meta.bot_model

        # We will work backwards from the index
        while index >= 0:
            reference_waypoint = flight_plan.waypoints[index]

            if index == initial_index:
                # Make the initial approximations
                reference_waypoint.start_time = waypoint_eta
                reference_waypoint.end_time = (
                    waypoint_eta + reference_waypoint.duration
                    if reference_waypoint.is_action
                    else waypoint_eta + datetime.timedelta(seconds=distance_between(reference_waypoint.from_pos, reference_waypoint.to_pos)/bot.speed)
                )
            else:
                # Work backwards from the timing we know
                reference_waypoint.start_time = (
                    flight_plan.waypoints[index + 1].start_time - reference_waypoint.duration
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
        logger.info(f"Recalculating flight plan {flight_plan.id}, original waypoint count {len(flight_plan.waypoints)}")
        #print_waypoints(flight_plan)
        assert flight_plan.meta.bot_model is not None

        finished = False
        while not finished:
            time_since_last_recharge = datetime.timedelta(seconds=0)

            for index, waypoint in enumerate(flight_plan.waypoints):
                if waypoint.is_action:
                    if waypoint.is_being_recharged:
                        #print("Waypoint is being recharged")
                        time_since_last_recharge = datetime.timedelta(seconds=0)
                        continue

                    # Else we will look at the duration of the action, and split it if necessary
                    time_since_last_recharge += waypoint.duration

                    bot_schema = flight_plan.meta.bot_model
                    threshold = (
                        datetime.timedelta(seconds=bot_schema.flight_time)
                        - self.remaining_flight_time_at_refuel
                        - self.refuel_duration
                    )

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
                    bot = flight_plan.meta.bot_model
                    leg_time = datetime.timedelta(seconds=int(distance_between(waypoint.from_pos, waypoint.to_pos)/bot.speed))
                    time_since_last_recharge += leg_time

                    threshold = (
                        datetime.timedelta(seconds=bot.flight_time)
                        - self.remaining_flight_time_at_refuel
                        - self.refuel_duration
                    )

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

        logger.debug(f"After recalculation for {flight_plan.id}, waypoint count {len(flight_plan.waypoints)}")

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
                        starting_tower=tower.id,
                        finishing_tower=tower.id
                    )
                    assert self.validate_flight_plan(flight_plan)
                    dummy_flight_plans.append(flight_plan)

        return dummy_flight_plans

    def create_refuel_flight_plans(self, flight_plan: FlightPlan) -> dict:
        """
        For a given flight plan, determine the flight plans for any refueling bots
        """
        logger.info(f"Creating refuel flight plans for flight plan {flight_plan.id}")
        assert flight_plan.is_approximated

        logger.debug(f"There are {len(flight_plan.refuel_waypoints)} refuel waypoints")
        calculated_flight_plans_per_waypoint_id = {}

        for index, refuel_waypoint in enumerate(flight_plan.refuel_waypoints):
            logger.debug(f"Looking at waypoint {index}")
            calculated_flight_plans_per_waypoint_id.setdefault(refuel_waypoint.id, [])

            # Get all the base flight plans for refuelers from different towers and different bot models
            dummy_potential_flight_plans = self.create_dummy_refuel_flight_plans(refuel_waypoint)
            dummy_potential_flight_plans.sort(key=lambda fp: fp.total_distance)

            refuel_schedule = None
            for index, flight_plan in enumerate(dummy_potential_flight_plans):
                for refuel_index, refuel_bot_schema in enumerate(self.get_refuel_bot_schemas()):
                    # Attach the meta
                    meta = FlightPlanMeta(bot_model=refuel_bot_schema)
                    flight_plan.set_meta(meta)

                    # We need to prevent a recursive loop by pre-recalculating the flight plan
                    flight_plan_copy = flight_plan.copy()
                    self.recalculate_flight_plan(flight_plan_copy)
                    assert self.validate_flight_plan(flight_plan_copy), "Invalid after recalculation"
                    self.add_positions_to_action_waypoints(flight_plan_copy)

                    # If there is a refuel needed while performing the refuel, we will end up in a loop
                    giving_refuel_waypoint = flight_plan_copy.giving_refuel_waypoint
                    for waypoint in flight_plan_copy.waypoints:
                        if waypoint.is_action and waypoint.is_being_recharged:
                            if waypoint.position and waypoint.position == giving_refuel_waypoint.position:
                                logger.info("Pregiving refuel is needed")
                                # We will inject a refuel point into the original potential flight plan to avoid this case
                                self.add_pre_giving_refuel_waypoint(flight_plan)

                                # Update the original part of the flight plan else later manipulations will lose that waypoint
                                flight_plan.update_original_state_waypoints()
                                self.add_positions_to_action_waypoints(flight_plan)
                                assert self.validate_flight_plan(flight_plan)

                    # Try to create a schedule and break
                    try:
                        refuel_schedule = self.determine_schedule(
                            flight_plan=flight_plan,
                            waypoint_eta=refuel_waypoint.start_time - datetime.timedelta(seconds=self.refuel_anticipation_buffer),
                            waypoint_id="critical"
                        )
                        break
                    except ScheduleError as e:
                        logger.warning(f"Failed to create schedule for dummy flight plan {index} / {len(dummy_potential_flight_plans)}, refuel schema {refuel_index}")
                        logger.warning(f"Schedule error {e}, looking at next")
                        refuel_schedule = None
                        continue
                if refuel_schedule:
                    break
            else:
                raise ScheduleError(f"Failed to create any refuel flight plan for waypoint {refuel_waypoint.id}")

            # This needs to be monitored to limit recursion
            calculated_flight_plans_per_waypoint_id[refuel_waypoint.id].append({
                'flight_plan': refuel_schedule.flight_plan,
                'related_sub_flight_plans': refuel_schedule.raw_schedule.get('related_sub_flight_plans')
            })

        return calculated_flight_plans_per_waypoint_id

    def get_nearest_towers_to_waypoint(self, waypoint: Waypoint, any: bool = False) -> List[Tower]:
        """
        For a given waypoint, return a list of towers with the first element being the closest
        if 'any', then look at either action or the 'to' position in a leg.
        if not 'any', we only accept action waypoints
        """
        assert isinstance(self.towers, list)

        if any:
            position = waypoint.position if waypoint.is_action else waypoint.to_pos
        else:
            assert waypoint.is_action
            position = waypoint.position

        distances = []
        logger.debug("Getting nearest towers")

        for tower in self.towers:
            distance = distance_between(position, tower.position)
            logger.debug(f"Distance between {position} and {tower.id} at {tower.position} is {distance}")
            distances.append((distance, tower))

        # We then sort by distance and return a list of towers with the first being the closest
        distances.sort(key=lambda value: value[0])
        logger.debug(f"Nearest is {distances[0][1].id}")
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
        assert isinstance(model, str), f"{model} is not a str"

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
        logger.info("Adding pre-giving refuel waypoint")
        assert self.validate_flight_plan(flight_plan), "Invalid flight plan prior to adding pre-giving refuel waypoint"
        assert flight_plan.has_giving_recharge_waypoint
        #print("Before adding pre-giving refuel waypoint")
        #print(flight_plan.to_dict())

        # Find the GIVING_RECHARGE waypoint
        giving_recharge_index = flight_plan.giving_recharge_index

        # The previous waypoint should be an action, and the previous previous a leg
        assert (
            (flight_plan.waypoints[giving_recharge_index - 1].is_action and flight_plan.waypoints[giving_recharge_index - 2].is_leg)
            or flight_plan.waypoints[giving_recharge_index - 1].is_leg
        ), f"Giving at {giving_recharge_index}, {print_waypoints(flight_plan)}"

        leg_index = giving_recharge_index - 2

        # We want to refuel sufficiently before we reach the recharge position
        bot = flight_plan.meta.bot_model
        time_to_refuel_before_end_of_leg = (
            datetime.timedelta(seconds=bot.flight_time)
            - self.refuel_duration
            - self.remaining_flight_time_at_refuel
            - self.refuel_anticipation_buffer
            - datetime.timedelta(seconds=60) # An additional buffer
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

    def create_transit_schedule(self, from_tower: Tower, to_tower: Tower, arrival_time: datetime.datetime, high_priority: bool, payload_id: str = None, bot_model: str = None) -> Schedule:
        """
        Return a schedule for transporting a payload from tower A to tower B
        considering inflight refuels, tower based refuels, and waypoint optimisation.
        If the schedule is high priority, it will go from tower A to tower B directly

        #TODO, For now we dont consider the flight gradients
        """
        logger.info("Creating transit schedule")
        assert bot_id or payload_id
        # Confirm the payload_id is located at the prescribed tower

        # TODO if not high priority, find the best route passing through different towers

        # Create a flight plan for that route considering bot cruise altitude TODO (and climb rates)
        flight_plan_meta = FlightPlanMeta(
            payload_id=payload_id,
            bot_model=bot_model
        ) # TODO populate the meta more

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

        # Create the schedule refuel plans
        return self.determine_schedule(
            flight_plan=flight_plan,
            landing_time=landing_time
        )

    def cancel_active_schedule(self, schedule: Schedule, now: datetime.datetime):
        """
        For a given schedule in progress, create flight plans to handle return to base for all active flights
        """
        pass

    @staticmethod
    def create_flight_plan_from_partial(partial_flight_plan: PartialFlightPlan, starting_tower: Tower, finishing_tower: Tower) -> FlightPlan:
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
        # For allocation logic to work, we need all the flight plan ids to be unique
        assert len({flight_plan.id for flight_plan in partial_flight_plans}) == len(partial_flight_plans), "Flight plans ids aren't unique"

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
            schedule = self.determine_schedule(
                flight_plan=flight_plan,
                waypoint_eta=critical_time,
                waypoint_id=flight_plan.waypoints[1].id
            )
            schedules.append(schedule)

        # Merge the schedules
        schedule = Schedule.from_schedules(schedules)
        return schedule

    def stretch_flight_plan(self, flight_plan: FlightPlan, start_delta: datetime.datetime, end_delta: datetime.datetime):
        """
        For a given flight plan, add buffer waypoints at the beginning and end of the flight plan
        """
        logger.info(f"Stretching flight plan {flight_plan.id} by start {start_delta} and end {end_delta}")

        launch_tower = self.get_tower_by_id(flight_plan.starting_tower)
        landing_tower = self.get_tower_by_id(flight_plan.finishing_tower)

        logger.debug(f"Flight plan meta is {flight_plan.meta}")
        bot = flight_plan.meta.bot_model
        original_start_time = flight_plan.start_time
        original_end_time = flight_plan.end_time

        if (
            flight_plan.waypoints[0].is_leg
            and flight_plan.waypoints[1].is_action
            and flight_plan.waypoints[1].action == 'waiting'
        ):
            logger.debug("Extending existing stretch")
            # We are extending an existing stretch
            # Extend the first waiting
            flight_plan.waypoints[1].duration = flight_plan.waypoints[1].duration + start_delta

            # Extend the landing wait if there is one
            if (
                flight_plan.waypoints[-1].is_leg
                and flight_plan.waypoints[-2].is_action
                and flight_plan.waypoints[-2].action == 'waiting'
            ):
                logger.debug("Extending an existing landing wait")
                flight_plan.waypoints[-2].duration = flight_plan.waypoints[-2].duration + end_delta
        else:
            logger.debug("Creating new stretch")
            logger.debug(f"Waypoints before new ones {len(flight_plan.waypoints)}")
            # We are stretching for the first time on this flight plan
            # TODO, Really the towers should define their waiting areas

            if start_delta.total_seconds():
                logger.debug("Looking at the launch part")

                # The existing leg will be modified, so we need to track the original duration of it
                real_first_leg_original_duration = get_waypoint_duration(flight_plan.waypoints[0], bot.speed)
                logger.debug(f"Original first leg duration {real_first_leg_original_duration}")

                # The modified first leg, the new first leg, and the waiting period need to match this constraint
                required_duration_until_end_of_first_real_leg = real_first_leg_original_duration + start_delta
                logger.debug(f"Required duration until end of first real leg {required_duration_until_end_of_first_real_leg}")

                # Determine the displacement of the waiting area in an inefficient non-mathematical way
                for i in range(1, 22):
                    # Create the delta for the first leg (the new one)
                    potential_new_first_leg_time = str(i/bot.speed)
                    potential_new_first_leg_time = datetime.timedelta(
                        seconds=int(potential_new_first_leg_time.split('.')[0]),
                        microseconds=int(potential_new_first_leg_time.split('.')[1][:6])
                    )

                    # Create the delta for the modified existing first leg
                    modified_original_first_leg_duration = str(distance_between(
                        [
                            launch_tower.position[0],
                            launch_tower.position[1],
                            launch_tower.position[2] + i
                        ],
                        flight_plan.waypoints[0].to_pos
                    ) / bot.speed)

                    modified_original_first_leg_duration = datetime.timedelta(
                        seconds=int(modified_original_first_leg_duration.split('.')[0]),
                        microseconds=int(modified_original_first_leg_duration.split('.')[1][:6])
                    )

                    this_total_time = modified_original_first_leg_duration + potential_new_first_leg_time
                    #logger.debug(f"For {i}, total time of legs is {this_total_time}")

                    if this_total_time > required_duration_until_end_of_first_real_leg:
                        #logger.debug(f"Which is greater than {required_duration_until_end_of_first_real_leg}")
                        # We will use the i-1 then
                        break

                logger.debug(f"Launch leg displacement is {i-1}")

                early_launch_leg = LegWaypoint(
                    positions={
                        'from': launch_tower.position,
                        'to': [launch_tower.position[0], launch_tower.position[1], launch_tower.position[2] + i - 1]
                    },
                    generated=True
                )

                early_launch_leg_time = get_waypoint_duration(early_launch_leg, bot.speed)
                logger.debug(f"Early launch leg time {early_launch_leg_time}")

                # Insert the new first leg and modify the existing leg
                flight_plan.waypoints.insert(0, early_launch_leg)
                flight_plan.waypoints[1].positions['from'] = early_launch_leg.to_pos

                # Just for debugging purposes
                real_first_leg_modified_duration = get_waypoint_duration(flight_plan.waypoints[1], bot.speed)
                logger.debug(f"Real launch leg modified duration {real_first_leg_modified_duration}")

                # For the remaining time difference, create a waiting action
                if start_delta > early_launch_leg_time:
                    logger.debug("Making waiting waypoint for launch")
                    early_launch_waiting_action = ActionWaypoint(
                        duration=required_duration_until_end_of_first_real_leg - real_first_leg_modified_duration - early_launch_leg_time,
                        action="waiting",
                        generated=True
                    )
                    logger.debug(f"Launching wait time {early_launch_waiting_action.duration}")
                    flight_plan.waypoints.insert(1, early_launch_waiting_action)

                    difference = required_duration_until_end_of_first_real_leg - (early_launch_waiting_action.duration + early_launch_leg_time + real_first_leg_modified_duration)
                    assert required_duration_until_end_of_first_real_leg == early_launch_waiting_action.duration + early_launch_leg_time + real_first_leg_modified_duration, difference

            # ------ For handling the landing -------
            if end_delta.total_seconds():
                logger.debug("Looking at the landing part")

                # The existing leg will be modified, so we need to track the original duration of it
                real_last_leg_original_duration = get_waypoint_duration(flight_plan.waypoints[-1], bot.speed)
                logger.debug(f"Real last leg original duration {real_last_leg_original_duration}")

                # The modified last leg, the new last leg, and the waiting period need to match this constraint
                required_duration_until_start_of_last_real_leg = real_last_leg_original_duration + end_delta
                logger.debug(f"Required duration from start of last real leg {required_duration_until_start_of_last_real_leg}")

                # Determine the displacement of the waiting area in an inefficient non-mathematical way
                for i in range(1, 22):
                    # Create the delta for the last leg (the new one)
                    potential_new_last_leg_time = str(i/bot.speed)
                    potential_new_last_leg_time = datetime.timedelta(
                        seconds=int(potential_new_last_leg_time.split('.')[0]),
                        microseconds=int(potential_new_last_leg_time.split('.')[1][:6])
                    )

                    # Create the delta for the modified existing first leg
                    modified_original_last_leg_duration = str(distance_between(
                        [
                            landing_tower.position[0],
                            landing_tower.position[1],
                            landing_tower.position[2] + i
                        ],
                        flight_plan.waypoints[-1].from_pos
                    ) / bot.speed)

                    modified_original_last_leg_duration = datetime.timedelta(
                        seconds=int(modified_original_last_leg_duration.split('.')[0]),
                        microseconds=int(modified_original_last_leg_duration.split('.')[1][:6])
                    )

                    this_total_time = modified_original_last_leg_duration + potential_new_last_leg_time
                    #logger.debug(f"For {i}, total leg time {this_total_time}")

                    if this_total_time > required_duration_until_start_of_last_real_leg:
                        #logger.debug(f"Which is greater than {required_duration_until_start_of_last_real_leg}")
                        # We will use the i-1 then
                        break

                logger.debug(f"Landing leg displacement is {i-1}")

                late_landing_leg = LegWaypoint(
                    positions={
                        'from': [landing_tower.position[0], landing_tower.position[1], landing_tower.position[2] + i - 1],
                        'to': landing_tower.position
                    },
                    generated=True
                )

                late_landing_leg_time = get_waypoint_duration(late_landing_leg,bot.speed)
                logger.debug(f"Late landing leg time {late_landing_leg_time}")

                # Insert the new last leg and modify the existing leg
                flight_plan.waypoints[-1].positions['to'] = late_landing_leg.from_pos
                flight_plan.waypoints.append(late_landing_leg)

                # Just for debugging
                modified_last_actual_leg_time = get_waypoint_duration(flight_plan.waypoints[-2], bot.speed)
                logger.debug(f"Modified real last leg duration {modified_last_actual_leg_time}")

                # For the remaining time difference, create a waiting action
                if end_delta > late_landing_leg_time:
                    logger.debug("Making waiting waypoint for landing")
                    late_landing_waiting_action = ActionWaypoint(
                        duration=required_duration_until_start_of_last_real_leg - modified_last_actual_leg_time - late_landing_leg_time,
                        action="waiting",
                        generated=True
                    )
                    logger.debug(f"Landing wait time {late_landing_waiting_action.duration}")
                    flight_plan.waypoints.insert(-1, late_landing_waiting_action)

                    difference = required_duration_until_start_of_last_real_leg - (late_landing_waiting_action.duration + late_landing_leg_time + modified_last_actual_leg_time)
                    assert required_duration_until_start_of_last_real_leg == late_landing_waiting_action.duration + late_landing_leg_time + modified_last_actual_leg_time, difference

        print_waypoints(flight_plan)

        # We reapproximate the timings based on the delta
        self.approximate_timings(
            flight_plan=flight_plan,
            launch_time=original_start_time - start_delta
        )

        logger.debug(f"Original start time {original_start_time}, new start time {flight_plan.start_time}")
        logger.debug(f"Original end time {original_end_time}, new end time {flight_plan.end_time}")

        self.add_positions_to_action_waypoints(flight_plan)
        logger.debug(f"Waypoints after new ones {len(flight_plan.waypoints)}")

        logger.debug(f"Old flight plan end time {original_end_time} - start time {original_start_time} = {original_end_time - original_start_time} == {(original_end_time - original_start_time).total_seconds()}")
        old_duration = original_end_time - original_start_time
        old_duration = without_microseconds(old_duration)

        new_duration = flight_plan.end_time - flight_plan.start_time
        logger.debug(f"New flight plan end time {flight_plan.end_time} - start time {flight_plan.start_time} = {flight_plan.end_time - flight_plan.start_time} == {(flight_plan.end_time - flight_plan.start_time).total_seconds()} == {new_duration.total_seconds()}")
        new_duration = without_microseconds(new_duration)
        logger.debug(f"New duration after strip {new_duration} == {new_duration.total_seconds()}")

        logger.debug(f"Old flight plan duration {old_duration.total_seconds()}, new duration {new_duration.total_seconds()} by extending {start_delta} and {end_delta}")
        logger.debug(f"New flight time {new_duration.total_seconds()}, expected new flight time {old_duration.total_seconds() + start_delta.total_seconds() + end_delta.total_seconds()}")
        assert old_duration + start_delta + end_delta == new_duration, old_duration + start_delta + end_delta - new_duration

    def fit_flight_plan_into_tower_allocations(self, flight_plan: FlightPlan) -> bool:
        """
        For a given flight plan, manipulate it to fit into the available launch and landing allocation slots
        This operates on the FlightPlan in place and returns a boolean if it is able to and has successfully done so
        """
        logger.info(f"Fitting flight plan {flight_plan.id} into tower allocations")
        assert flight_plan.is_approximated, print_waypoints(flight_plan)
        self.validate_flight_plan(flight_plan)

        launch_tower = self.get_tower_by_id(flight_plan.starting_tower)
        landing_tower = self.get_tower_by_id(flight_plan.finishing_tower)

        # Find the nearest launch window (looking before the launch time)
        nearest_launch_intervals = launch_tower.launch_allocator.get_nearest_intervals_to_window_end(flight_plan.start_time)
        if not nearest_launch_intervals:
            logger.warning(f"No intervals available for launch day {flight_plan.start_time} at tower {launch_tower} flight plan {flight_plan.id}")
            return False

        # A list of tuples of (interval, window start, window end) for each interval
        nearest_launch_windows = [
            (interval,) + launch_tower.launch_allocator.get_window_for_interval(interval=interval, date=flight_plan.start_time)
            for interval in nearest_launch_intervals
        ]

        # Consider only the windows before the launch time
        nearest_launch_windows = [
            nearest_window
            for nearest_window in nearest_launch_windows
            if nearest_window[2] <= flight_plan.start_time
        ]

        if not nearest_launch_windows:
            logger.warning(f"No intervals available for launch window of flight plan {flight_plan.id}")
            return False

        # Consider the first nearest window
        nearest_launch_window = nearest_launch_windows[0]

        # Now find the nearest landing window (looking after the landing time)
        nearest_landing_intervals = landing_tower.landing_allocator.get_nearest_intervals_to_window_start(flight_plan.end_time)
        if not nearest_landing_intervals:
            logger.warning(f"No intervals available for landing day {flight_plan.end_time} at tower {landing_tower} flight plan {flight_plan.id}")
            return False

        # A list of tuples of (interval, window start, window end) for each interval
        nearest_landing_windows = [
            (interval,) + landing_tower.landing_allocator.get_window_for_interval(interval=interval, date=flight_plan.end_time)
            for interval in nearest_landing_intervals
        ]

        # Consider only the windows after the landing time
        nearest_landing_windows = [
            nearest_window
            for nearest_window in nearest_landing_windows
            if nearest_window[1] >= flight_plan.end_time
        ]

        if not nearest_landing_windows:
            logger.warning(f"No intervals available for landing window of flight plan {flight_plan.id}")
            return False

        # Consider the first nearest window
        nearest_landing_window = nearest_landing_windows[0]
        logger.debug(f"Nearest landing window to {flight_plan.end_time} is {nearest_landing_window[1]}")
        logger.info(f"Trying to make flight plan start at {nearest_launch_window[2]} and end at {nearest_landing_window[1]}")

        # Copy the flight plan and strip it to make it raw
        #print("original")
        #print_waypoints(flight_plan)
        flight_plan_copy = flight_plan.from_original_state()
        #print("copy")
        #print_waypoints(flight_plan_copy)

        self.add_positions_to_action_waypoints(flight_plan_copy)
        self.approximate_timings(
            flight_plan=flight_plan_copy,
            launch_time=flight_plan.start_time
        )

        logger.debug(f"Flight plan start and end before stretching {flight_plan.start_time} {flight_plan.end_time}")
        logger.debug(f"Flight plan waypoint count before stretch {len(flight_plan.waypoints)}")

        # Determine the deltas
        start_delta = without_microseconds(flight_plan.start_time - nearest_launch_window[2])
        end_delta = without_microseconds(nearest_landing_window[1] - flight_plan.end_time)

        # Stretch the flight plan
        self.stretch_flight_plan(
            flight_plan=flight_plan_copy,
            start_delta=start_delta,
            end_delta=end_delta
        )

        # Recalculate the flight plan to add the refueling points
        logger.debug("Recalculation in stretch")
        self.recalculate_flight_plan(flight_plan_copy)
        self.add_positions_to_action_waypoints(flight_plan_copy)

        # Recalculate the timings
        self.approximate_timings(
            flight_plan=flight_plan_copy,
            launch_time=nearest_launch_window[2]
        )

        # If the recalculated flight plan has the same number of refuel waypoint as the original, apply it to the original
        if flight_plan_copy.refuel_waypoint_count == flight_plan.refuel_waypoint_count:
            logger.debug("Breaking fit recursion")
            flight_plan.copy_from(flight_plan_copy, full_copy=True)
            assert flight_plan.start_time == flight_plan_copy.start_time
            assert flight_plan.end_time == flight_plan_copy.end_time
            logger.debug(f"At end of stretch, start time is {flight_plan.start_time}, end time is {flight_plan.end_time}")
            return True

        # Else recurse on the stretched flight plan and then apply it to the original
        logger.debug("Recursing fit")
        recurse_flag = self.fit_flight_plan_into_tower_allocations(flight_plan_copy)

        if recurse_flag:
            logger.debug(f"In stretch, recursed child was successful, applying changes. Flight plan starts at {flight_plan_copy.start_time} and ends at {flight_plan_copy.end_time}")
            flight_plan.copy_from(flight_plan_copy, full_copy=True)
            return True
        else:
            return self.fit_flight_plan_into_tower_allocations(flight_plan_copy)

    def allocate_flight_plan(self, flight_plan: FlightPlan) -> bool:
        """
        For a given flight plan, attempt to make all the resource allocations and fallback if it fails.
        Calls to this function should be wrapped in a try-except to catch AllocationError(s).
        If successful, the allocations are stored in self.flight_plan_allocation_to_deallocator
        """
        logger.info("Allocating flight plan")
        assert flight_plan.is_approximated

        launch_tower = self.get_tower_by_id(flight_plan.starting_tower)
        landing_tower = self.get_tower_by_id(flight_plan.finishing_tower)

        # Find the nearest launch window (looking before the launch time)
        nearest_intervals = launch_tower.launch_allocator.get_nearest_intervals_to_window_end(flight_plan.start_time)
        if not nearest_intervals:
            logger.warning(f"No intervals available for launch day {flight_plan.start_time} at tower {launch_tower} flight plan {flight_plan.id}")
            return False

        # A list of tuples of (interval, window start, window end) for each interval
        nearest_windows = [
            (interval,) + launch_tower.launch_allocator.get_window_for_interval(interval=interval, date=flight_plan.start_time)
            for interval in nearest_intervals
        ]

        nearest_window = nearest_windows[0]
        if nearest_window[2] == without_microseconds(flight_plan.start_time):
            try:
                allocation_id = launch_tower.allocate_launch(
                    flight_plan_id=flight_plan.id,
                    date=flight_plan.start_time,
                    interval=nearest_window[0]
                )
                self.flight_plan_allocation_to_deallocator[flight_plan.id][allocation_id] = launch_tower.deallocate_launch
            except AllocationError as e:
                logger.warning(f"Failed to allocate launch window for {flight_plan.id}")
                return False
        else:
            logger.warning(f"Failed to allocate launch window for {flight_plan.id}, interval mismatch, window end is {nearest_window[2]}, flight plan start is {flight_plan.start_time}")
            return False

        # Now find the nearest landing window (looking after the landing time)
        nearest_intervals = landing_tower.landing_allocator.get_nearest_intervals_to_window_start(flight_plan.end_time)
        if not nearest_intervals:
            logger.warning(f"No intervals available for landing day {flight_plan.end_time} at tower {landing_tower} flight plan {flight_plan.id}")
            return False

        # A list of tuples of (interval, window start, window end) for each interval
        nearest_windows = [
            (interval,) + landing_tower.landing_allocator.get_window_for_interval(interval=interval, date=flight_plan.end_time)
            for interval in nearest_intervals
        ]

        nearest_window = nearest_windows[0]
        if nearest_window[1] == without_microseconds(flight_plan.end_time):
            try:
                allocation_id = landing_tower.allocate_landing(
                    flight_plan_id=flight_plan.id,
                    date=flight_plan.end_time,
                    interval=nearest_window[0]
                )
                self.flight_plan_allocation_to_deallocator[flight_plan.id][allocation_id] = landing_tower.deallocate_landing
            except AllocationError as e:
                logger.warning(f"Failed to allocate landing for {flight_plan.id}")
                return False
        else:
            logger.warning(f"Failed to allocate landing window for {flight_plan.id}, interval mismatch nearest landing window start is {nearest_window[1]}, flight plan ends at {flight_plan.end_time}")
            return False

        return True

    def is_bot_available(self, bot_id: str, from_datetime: datetime.datetime, to_datetime: datetime.datetime) -> bool:
        """
        Check if a given bot is available for a given time window
        """
        return self.bot_manager.is_allocation_available(
            resource_id=bot_id,
            from_datetime=from_datetime,
            to_datetime=to_datetime
        )

    def get_bot_tower_for_given_time(self, bot_id: str, reference_time: datetime.datetime) -> Tower:
        assert self.bot_manager.trackers.get(bot_id) is not None

        bot_tracker = self.bot_manager.trackers[bot_id]

        if not bot_tracker.tracker:
            initial_tower_id = bot_tracker.initial_context['tower_id']
            return self.get_tower_by_id(initial_tower_id)

        bot_tracker.tracker.sort(key=lambda tracking_dict: tracking_dict['to_datetime'], reverse=True)

        # We check the trackers to determine the tower location for the given time
        for tracker in reversed(bot_tracker.tracker):
            if reference_time <= tracker['to_datetime'] and reference_time >= tracker['from_datetime']:
                # The payload is allocated for this time and has not static location
                raise TrackerError("Bot is allocated, can't determine tower for given time")
            elif reference_time > tracker['to_datetime']:
                return self.get_tower_by_id(tracker['to_tower'])
        else:
            initial_tower_id = bot_tracker.initial_context['tower_id']
            return self.get_tower_by_id(initial_tower_id)

    def get_available_bots_for_given_window(self, bot_model: str, from_datetime: datetime.datetime, to_datetime: datetime.datetime) -> List[Bot]:
        """
        Return a list of bots of a given model available at the given time window
        """
        return [
            bot
            for bot in self.bot_manager.resources
            if bot.schema.model == bot_model
            and self.bot_manager.is_allocation_available(
                resource_id=bot.id,
                from_datetime=from_datetime,
                to_datetime=to_datetime
            )
        ]

    def is_payload_available(self, payload_id: str, from_datetime: datetime.datetime, to_datetime: datetime.datetime) -> bool:
        """
        Check if a given payload is available for a given time window
        """
        return self.payload_manager.is_allocation_available(
            resource_id=payload_id,
            from_datetime=from_datetime,
            to_datetime=to_datetime
        )

    def get_payload_tower_for_given_time(self, payload_id: str, reference_time: datetime.datetime) -> Optional[Tower]:
        logger.debug(f"Getting payload {payload_id} tower for given time")
        assert self.payload_manager.trackers.get(payload_id) is not None

        payload_tracker = self.payload_manager.trackers[payload_id]
        logger.debug(f"Trackers are {payload_tracker}")

        if not payload_tracker.tracker:
            initial_tower_id = payload_tracker.initial_context['tower_id']
            return self.get_tower_by_id(initial_tower_id)

        payload_tracker.tracker.sort(key=lambda tracking_dict: tracking_dict['to_datetime'], reverse=True)

        # We check the trackers to determine the tower location for the given time
        for tracker in reversed(payload_tracker.tracker):
            if reference_time <= tracker['to_datetime'] and reference_time >= tracker['from_datetime']:
                # The payload is allocated for this time and has not static location
                raise TrackerError(f"Payload is allocated, can't determine tower for given time, existing tracker {tracker}, reference time {reference_time}")
            elif reference_time > tracker['to_datetime']:
                return self.get_tower_by_id(tracker['tower_id'])
        else:
            initial_tower_id = bot_tracker.initial_context['tower_id']
            return self.get_tower_by_id(initial_tower_id)

    def get_available_payloads_for_given_window(self, payload_model: str, from_datetime: datetime.datetime, to_datetime: datetime.datetime) -> List[Payload]:
        """
        Return a list of payloads of a given model available at the given time window
        """
        return [
            payload
            for payload in self.payload_manager.resources
            if payload.schema.model == payload_model
            and self.payload_manager.is_allocation_available(
                resource_id=payload.id,
                from_datetime=from_datetime,
                to_datetime=to_datetime
            )
        ]

    def get_refuel_bot_schemas(self) -> Set[BotSchema]:
        """
        TODO, Refuel payloads should be determined by payload schema type
        """
        refuel_payload_schema = get_payload_schema_by_model('refuel_payload_mk1', self.payload_schemas)
        refuel_schemas = [
            self.get_bot_schema_by_model(compatable_bot_model.model)
            for compatable_bot_model in refuel_payload_schema.compatable_bots
        ]

        assert refuel_schemas
        assert isinstance(refuel_schemas[0], BotSchema), f"{type(list(refuel_schemas)[0])} is not a BotSchema"
        return refuel_schemas

    def delete_allocations_for_flight_plan(self, flight_plan_id: str, allocation_id: str = None):
        """
        For a given flight plan id, delete all related allocations, or a specific allocation if the id is supplied
        """
        if allocation_id:
            try:
                deallocator = self.flight_plan_allocation_to_deallocator[flight_plan_id][allocation_id]
            except KeyError as e:
                logger.debug(f"Failed to retrieve deallocator for flight plan {flight_plan_id} and allocation id {allocation_id}, {e}")
                return

            return deallocator(allocation_id)

        # Else we are deallocating all of them
        for allocation_id, deallocator in self.flight_plan_allocation_to_deallocator.get(flight_plan_id, {}).items():
            deallocator(allocation_id)
