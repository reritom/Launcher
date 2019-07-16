import unittest
import math as maths
import json

from .scheduler import Scheduler
from .bot import Bot
from .flight_plan import FlightPlan
from .tower import Tower
from .action_waypoint import ActionWaypoint
from .leg_waypoint import LegWaypoint

class TestScheduler(unittest.TestCase):
    def test_init_ko(self):
        # If the tower has an inventory bot which isnt registered, an assertion error is raised
        pass

    def test_validate_flight_plan_ok(self):
        bots = [
            Bot(
                flight_time=500,
                speed=1,
                bot_type="Refueler",
                model="TestI"
            ),
            Bot(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI"
            )
        ]

        waypoints = [
            LegWaypoint(cartesian_positions={
                'from': [0,0,0],
                'to': [0,0,1000]
            }),
            LegWaypoint(cartesian_positions={
                'from': [1000,0,0],
                'to': [0,0,0]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            bot_model="CarrierI",
            starting_position=[0,0,0]
        )

        towers = [
            Tower(
                inventory=[{'model': "TestI", 'quantity': 5}],
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bots=bots,
            refuel_duration=100,
            remaining_flight_time_at_refuel=200,
            refuel_anticipation_buffer=100
        )

        try:
            scheduler.validate_flight_plan(flight_plan)
        except AssertionError as e:
            self.fail("Validation failed unexpectedly")

    def test_validate_flight_plan_ko_invalid_bot_model(self):
        bots = [
            Bot(
                flight_time=500,
                speed=1,
                bot_type="Refueler",
                model="TestI"
            ),
            Bot(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI"
            )
        ]

        waypoints = [
            LegWaypoint(cartesian_positions={
                'from': [0,0,0],
                'to': [0,0,1000]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            bot_model="This doesnt exist",
            starting_position=[0,0,0]
        )

        towers = [
            Tower(
                inventory=[{'model': "TestI", 'quantity': 5}],
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bots=bots,
            refuel_duration=100,
            remaining_flight_time_at_refuel=200,
            refuel_anticipation_buffer=100
        )

        # This will fail because the flight plan bot isnt registered in the scheduler
        with self.assertRaises(AssertionError) as ctx:
            scheduler.validate_flight_plan(flight_plan)

    def test_validate_flight_plan_ko_invalid_final_target(self):
        bots = [
            Bot(
                flight_time=500,
                speed=1,
                bot_type="Refueler",
                model="TestI"
            ),
            Bot(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI"
            )
        ]

        waypoints = [
            LegWaypoint(cartesian_positions={
                'from': [0,0,0],
                'to': [0,0,1000]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            bot_model="This doesnt exist",
            starting_position=[0,0,0]
        )

        towers = [
            Tower(
                inventory=[{'model': "TestI", 'quantity': 5}],
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bots=bots,
            refuel_duration=100,
            remaining_flight_time_at_refuel=200,
            refuel_anticipation_buffer=100
        )

        # This will fail because the flight plan final leg isnt targetting a tower
        with self.assertRaises(AssertionError) as ctx:
            scheduler.validate_flight_plan(flight_plan)

    def test_approximate_timings_from_launch_time(self):
        pass

    def test_approximate_timings_from_waypoint_eta(self):
        pass

    def test_recalculate_flight_plan_one_leg(self):
        bots = [
            Bot(
                flight_time=500,
                speed=1,
                bot_type="Refueler",
                model="TestI"
            ),
            Bot(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI"
            )
        ]

        waypoints = [
            LegWaypoint(cartesian_positions={
                'from': [0,0,0],
                'to': [0,0,1000]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            bot_model="CarrierI",
            starting_position=[0,0,0]
        )

        towers = [
            Tower(
                inventory=[{'model': "TestI", 'quantity': 5}],
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bots=bots,
            refuel_duration=100,
            remaining_flight_time_at_refuel=200,
            refuel_anticipation_buffer=100
        )

        expected_waypoints = [
            LegWaypoint(cartesian_positions={
                'from': [0,0,0],
                'to': [0,0,200]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(cartesian_positions={
                'from': [0,0,200],
                'to': [0,0,400]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(cartesian_positions={
                'from': [0,0,400],
                'to': [0,0,600]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(cartesian_positions={
                'from': [0,0,600],
                'to': [0,0,800]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(cartesian_positions={
                'from': [0,0,800],
                'to': [0,0,1000]
            }),
        ]

        expected_flight_plan = FlightPlan(
            waypoints=expected_waypoints,
            bot_model="CarrierI",
            starting_position=[0,0,0]
        )

        # The flight plan has only one leg, so we expect this leg to be split
        scheduler.recalculate_flight_plan(flight_plan)
        self.assertEqual(flight_plan, expected_flight_plan)

    def test_recalculate_flight_plan_roundtrip_with_action(self):
        bots = [
            Bot(
                flight_time=500,
                speed=1,
                bot_type="Refueler",
                model="TestI"
            ),
            Bot(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI"
            )
        ]

        waypoints = [
            LegWaypoint(cartesian_positions={
                'from': [0,0,0],
                'to': [0,0,1000]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            bot_model="CarrierI",
            starting_position=[0,0,0]
        )

        towers = [
            Tower(
                inventory=[{'model': "TestI", 'quantity': 5}],
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bots=bots,
            refuel_duration=100,
            remaining_flight_time_at_refuel=200,
            refuel_anticipation_buffer=100
        )

        expected_waypoints = [
            LegWaypoint(cartesian_positions={
                'from': [0,0,0],
                'to': [0,0,200]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(cartesian_positions={
                'from': [0,0,200],
                'to': [0,0,400]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(cartesian_positions={
                'from': [0,0,400],
                'to': [0,0,600]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(cartesian_positions={
                'from': [0,0,600],
                'to': [0,0,800]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(cartesian_positions={
                'from': [0,0,800],
                'to': [0,0,1000]
            }),
        ]

        expected_flight_plan = FlightPlan(
            waypoints=expected_waypoints,
            bot_model="CarrierI",
            starting_position=[0,0,0]
        )

        # The flight plan has only one leg, so we expect this leg to be split
        scheduler.recalculate_flight_plan(flight_plan)
        self.assertEqual(flight_plan, expected_flight_plan)

    def test_recalculate_flight_plan_roundtrip_with_giving_refuel_action(self):
        pass
