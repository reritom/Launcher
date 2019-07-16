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
    def test_recalculate_flight_plan_1(self):
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
