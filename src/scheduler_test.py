import unittest
import math as maths
import json
import datetime

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
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,1000]
            }),
            LegWaypoint(positions={
                'from': [0,0,1000],
                'to': [0,0,0]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            bot_model="CarrierI",
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
        )

        towers = [
            Tower(
                id='TowerOne',
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
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,1000]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            bot_model="This doesnt exist",
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
        )

        towers = [
            Tower(
                id="TowerOne",
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
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,1000]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            bot_model="This doesnt exist",
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
        )

        towers = [
            Tower(
                id='TowerOne',
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
        bots = [
            Bot(
                flight_time=50,
                speed=1,
                bot_type="Carrier",
                model="CarrierI"
            )
        ]

        waypoints = [
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,10]
            }),
            ActionWaypoint(
                action="refuel_anticipation_buffer",
                duration=10
            ),
            ActionWaypoint(
                action="giving_recharge",
                duration=10
            ),
            LegWaypoint(positions={
                'from': [0,0,5],
                'to': [0,0,0]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            bot_model="CarrierI",
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
        )

        towers = [
            Tower(
                id='TowerOne',
                inventory=[{'model': "CarrierI", 'quantity': 5}],
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
            remaining_flight_time_at_refuel=150,
            refuel_anticipation_buffer=100
        )

        start_time = datetime.datetime(2010, 5, 5, 12, 30, 0)

        expected_timings = [
            (
                datetime.datetime(2010, 5, 5, 12, 30, 0),
                datetime.datetime(2010, 5, 5, 12, 30, 10)
            ),
            (
                datetime.datetime(2010, 5, 5, 12, 30, 10),
                datetime.datetime(2010, 5, 5, 12, 30, 20)
            ),
            (
                datetime.datetime(2010, 5, 5, 12, 30, 20),
                datetime.datetime(2010, 5, 5, 12, 30, 30)
            ),
            (
                datetime.datetime(2010, 5, 5, 12, 30, 30),
                datetime.datetime(2010, 5, 5, 12, 30, 35)
            )
        ]

        scheduler.approximate_timings(flight_plan, start_time)

        for index, waypoint in enumerate(flight_plan.waypoints):
            self.assertEqual(waypoint.start_time, expected_timings[index][0])
            self.assertEqual(waypoint.end_time, expected_timings[index][1])

    def test_approximate_timings_from_waypoint_eta(self):
        bots = [
            Bot(
                flight_time=50,
                speed=1,
                bot_type="Carrier",
                model="CarrierI"
            )
        ]

        waypoints = [
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,10]
            }),
            ActionWaypoint(
                action="refuel_anticipation_buffer",
                duration=10
            ),
            ActionWaypoint(
                action="giving_recharge",
                duration=10,
                id="critical"
            ),
            LegWaypoint(positions={
                'from': [0,0,5],
                'to': [0,0,0]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            bot_model="CarrierI",
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
        )

        towers = [
            Tower(
                id='TowerOne',
                inventory=[{'model': "CarrierI", 'quantity': 5}],
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
            remaining_flight_time_at_refuel=150,
            refuel_anticipation_buffer=100
        )

        waypoint_eta = datetime.datetime(2010, 5, 5, 12, 30, 20)

        expected_timings = [
            (
                datetime.datetime(2010, 5, 5, 12, 30, 0),
                datetime.datetime(2010, 5, 5, 12, 30, 10)
            ),
            (
                datetime.datetime(2010, 5, 5, 12, 30, 10),
                datetime.datetime(2010, 5, 5, 12, 30, 20)
            ),
            (
                datetime.datetime(2010, 5, 5, 12, 30, 20),
                datetime.datetime(2010, 5, 5, 12, 30, 30)
            ),
            (
                datetime.datetime(2010, 5, 5, 12, 30, 30),
                datetime.datetime(2010, 5, 5, 12, 30, 35)
            )
        ]

        scheduler.approximate_timings_based_on_waypoint_eta(flight_plan, waypoint_eta, 'critical')

        for index, waypoint in enumerate(flight_plan.waypoints):
            self.assertEqual(waypoint.start_time, expected_timings[index][0])
            self.assertEqual(waypoint.end_time, expected_timings[index][1])

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
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,1000]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            bot_model="CarrierI",
            starting_tower='TowerOne',
            finishing_tower='TowerTwo',
        )

        towers = [
            Tower(
                id='TowerOne',
                inventory=[{'model': "TestI", 'quantity': 5}],
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1
            ),
            Tower(
                id='TowerTwo',
                inventory=[{'model': "TestI", 'quantity': 5}],
                position=[0,0,1000],
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
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,200]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(positions={
                'from': [0,0,200],
                'to': [0,0,400]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(positions={
                'from': [0,0,400],
                'to': [0,0,600]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(positions={
                'from': [0,0,600],
                'to': [0,0,800]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(positions={
                'from': [0,0,800],
                'to': [0,0,1000]
            }),
        ]

        expected_flight_plan = FlightPlan(
            waypoints=expected_waypoints,
            bot_model="CarrierI",
            starting_tower='TowerOne',
            finishing_tower='TowerTwo',
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
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,1000]
            }),
            ActionWaypoint(
                action="payload",
                duration=500
            ),
            LegWaypoint(positions={
                'from': [0,0,1000],
                'to': [0,0,0]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            bot_model="CarrierI",
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
        )

        towers = [
            Tower(
                id='TowerOne',
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
            refuel_duration=10,
            remaining_flight_time_at_refuel=20,
            refuel_anticipation_buffer=10
        )

        expected_waypoints = [
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,470]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=10
            ),
            LegWaypoint(positions={
                'from': [0,0,470],
                'to': [0,0,940]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=10
            ),
            LegWaypoint(positions={
                'from': [0,0,940],
                'to': [0,0,1000]
            }),
            ActionWaypoint(
                action="payload",
                duration=410
            ),
            ActionWaypoint(
                action="being_recharged",
                duration=10
            ),
            ActionWaypoint(
                action="payload",
                duration=90
            ),
            LegWaypoint(positions={
                'from': [0,0,1000],
                'to': [0,0,620]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=10
            ),
            LegWaypoint(positions={
                'from': [0,0,620],
                'to': [0,0,150]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=10
            ),
            LegWaypoint(positions={
                'from': [0,0,150],
                'to': [0,0,0]
            }),
        ]

        expected_flight_plan = FlightPlan(
            waypoints=expected_waypoints,
            bot_model="CarrierI",
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
        )

        scheduler.recalculate_flight_plan(flight_plan)
        self.assertEqual(flight_plan, expected_flight_plan)

    def test_recalculate_flight_plan_roundtrip_with_giving_refuel_action(self):
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
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,500]
            }),
            ActionWaypoint(
                action="refuel_anticipation_buffer",
                duration=100
            ),
            ActionWaypoint(
                action="giving_recharge",
                duration=100
            ),
            LegWaypoint(positions={
                'from': [0,0,500],
                'to': [0,0,0]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            bot_model="CarrierI",
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
        )

        towers = [
            Tower(
                id='TowerOne',
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
            remaining_flight_time_at_refuel=150,
            refuel_anticipation_buffer=100
        )

        expected_waypoints = [
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,250]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(positions={
                'from': [0,0,250],
                'to': [0,0,500]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            ActionWaypoint(
                action="refuel_anticipation_buffer",
                duration=100
            ),
            ActionWaypoint(
                action="giving_recharge",
                duration=100
            ),
            LegWaypoint(positions={
                'from': [0,0,500],
                'to': [0,0,450]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(positions={
                'from': [0,0,450],
                'to': [0,0,200]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=100
            ),
            LegWaypoint(positions={
                'from': [0,0,200],
                'to': [0,0,0]
            }),
        ]

        expected_flight_plan = FlightPlan(
            waypoints=expected_waypoints,
            bot_model="CarrierI",
            starting_tower='TowerOne',
            finishing_tower='TowerOne'
        )

        # The flight plan has only one leg, so we expect this leg to be split
        scheduler.recalculate_flight_plan(flight_plan)
        self.assertEqual(flight_plan, expected_flight_plan)

    def test_get_nearest_towers_to_waypoint(self):
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

        waypoint = ActionWaypoint(
            action="being_recharged",
            duration=100
        )

        waypoint.position = [50,50,50]


        towers = [
            Tower(
                id='TowerOne',
                inventory=[{'model': "TestI", 'quantity': 5}],
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1
            ),
            Tower(
                id='TowerTwo',
                inventory=[{'model': "TestI", 'quantity': 5}],
                position=[30,30,30],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1
            ),
            Tower(
                id='TowerThree',
                inventory=[{'model': "TestI", 'quantity': 5}],
                position=[110,110,110],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bots=bots,
            refuel_duration=100,
            remaining_flight_time_at_refuel=150,
            refuel_anticipation_buffer=100
        )

        nearest_towers = scheduler.get_nearest_towers_to_waypoint(waypoint)
        expected_nearest_towers = [towers[1], towers[0], towers[2]]
        self.assertEqual(nearest_towers, expected_nearest_towers)
