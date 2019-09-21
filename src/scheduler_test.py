import unittest
import math as maths
import json
import datetime

from .scheduler import Scheduler
from .bot import BotSchema
from .resource_manager import ResourceManager
from .flight_plan import FlightPlan
from .tower import Tower
from .flight_plan_meta import FlightPlanMeta
from .action_waypoint import ActionWaypoint
from .leg_waypoint import LegWaypoint

class TestScheduler(unittest.TestCase):
    def test_validate_flight_plan_ok(self):
        bot_schemas = [
            BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Refueler",
                model="TestI",
                cruising_altitude=100
            ),
            BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
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

        meta = FlightPlanMeta(
            bot_model=BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        )

        flight_plan = FlightPlan(
            waypoints=waypoints,
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
            meta=meta
        )

        towers = [
            Tower(
                id='TowerOne',
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1,
                landing_time=1,
                bot_capacity=10,
                payload_capacity=10
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bot_schemas=bot_schemas,
            payload_schemas=[],
            bot_manager=ResourceManager([]),
            payload_manager=ResourceManager([]),
            refuel_duration=datetime.timedelta(seconds=100),
            remaining_flight_time_at_refuel=datetime.timedelta(seconds=200),
            refuel_anticipation_buffer=datetime.timedelta(seconds=100)
        )

        try:
            scheduler.validate_flight_plan(flight_plan)
        except AssertionError as e:
            self.fail("Validation failed unexpectedly")

    def test_validate_flight_plan_ko_invalid_final_target(self):
        bot_schemas = [
            BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Refueler",
                model="TestI",
                cruising_altitude=100
            ),
            BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        ]

        waypoints = [
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,1000]
            })
        ]

        meta = FlightPlanMeta(
            bot_model=BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        )

        flight_plan = FlightPlan(
            waypoints=waypoints,
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
            meta=meta
        )

        towers = [
            Tower(
                id='TowerOne',
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1,
                landing_time=1,
                bot_capacity=10,
                payload_capacity=10
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bot_schemas=bot_schemas,
            payload_schemas=[],
            bot_manager=ResourceManager([]),
            payload_manager=ResourceManager([]),
            refuel_duration=datetime.timedelta(seconds=100),
            remaining_flight_time_at_refuel=datetime.timedelta(seconds=200),
            refuel_anticipation_buffer=datetime.timedelta(seconds=100)
        )

        # This will fail because the flight plan final leg isnt targetting a tower
        with self.assertRaises(AssertionError) as ctx:
            scheduler.validate_flight_plan(flight_plan)

    def test_approximate_timings_from_launch_time(self):
        bot_schemas = [
            BotSchema(
                flight_time=50,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        ]

        waypoints = [
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,10]
            }),
            ActionWaypoint(
                action="refuel_anticipation_buffer",
                duration=datetime.timedelta(seconds=10)
            ),
            ActionWaypoint(
                action="giving_recharge",
                duration=datetime.timedelta(seconds=10)
            ),
            LegWaypoint(positions={
                'from': [0,0,5],
                'to': [0,0,0]
            })
        ]

        meta = FlightPlanMeta(
            bot_model=BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        )

        flight_plan = FlightPlan(
            waypoints=waypoints,
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
            meta=meta
        )

        towers = [
            Tower(
                id='TowerOne',
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1,
                landing_time=1,
                bot_capacity=10,
                payload_capacity=10
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bot_schemas=bot_schemas,
            payload_schemas=[],
            bot_manager=ResourceManager([]),
            payload_manager=ResourceManager([]),
            refuel_duration=datetime.timedelta(seconds=100),
            remaining_flight_time_at_refuel=datetime.timedelta(seconds=150),
            refuel_anticipation_buffer=datetime.timedelta(seconds=100)
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
        bot_schemas = [
            BotSchema(
                flight_time=50,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        ]

        waypoints = [
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,10]
            }),
            ActionWaypoint(
                action="refuel_anticipation_buffer",
                duration=datetime.timedelta(seconds=10)
            ),
            ActionWaypoint(
                action="giving_recharge",
                duration=datetime.timedelta(seconds=10),
                id="critical"
            ),
            LegWaypoint(positions={
                'from': [0,0,5],
                'to': [0,0,0]
            })
        ]

        meta = FlightPlanMeta(
            bot_model=BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        )

        flight_plan = FlightPlan(
            waypoints=waypoints,
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
            meta=meta
        )

        towers = [
            Tower(
                id='TowerOne',
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1,
                landing_time=1,
                bot_capacity=10,
                payload_capacity=10
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bot_schemas=bot_schemas,
            payload_schemas=[],
            bot_manager=ResourceManager([]),
            payload_manager=ResourceManager([]),
            refuel_duration=datetime.timedelta(seconds=100),
            remaining_flight_time_at_refuel=datetime.timedelta(seconds=150),
            refuel_anticipation_buffer=datetime.timedelta(seconds=100)
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
        bot_schemas = [
            BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Refueler",
                model="TestI",
                cruising_altitude=100
            ),
            BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        ]

        waypoints = [
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,1000]
            })
        ]

        meta = FlightPlanMeta(
            bot_model=BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        )

        flight_plan = FlightPlan(
            waypoints=waypoints,
            starting_tower='TowerOne',
            finishing_tower='TowerTwo',
            meta=meta
        )

        towers = [
            Tower(
                id='TowerOne',
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1,
                landing_time=1,
                bot_capacity=10,
                payload_capacity=10
            ),
            Tower(
                id='TowerTwo',
                position=[0,0,1000],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1,
                landing_time=1,
                bot_capacity=10,
                payload_capacity=10
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bot_schemas=bot_schemas,
            payload_schemas=[],
            bot_manager=ResourceManager([]),
            payload_manager=ResourceManager([]),
            refuel_duration=datetime.timedelta(seconds=100),
            remaining_flight_time_at_refuel=datetime.timedelta(seconds=200),
            refuel_anticipation_buffer=datetime.timedelta(seconds=100)
        )

        expected_waypoints = [
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,200]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=datetime.timedelta(seconds=100)
            ),
            LegWaypoint(positions={
                'from': [0,0,200],
                'to': [0,0,400]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=datetime.timedelta(seconds=100)
            ),
            LegWaypoint(positions={
                'from': [0,0,400],
                'to': [0,0,600]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=datetime.timedelta(seconds=100)
            ),
            LegWaypoint(positions={
                'from': [0,0,600],
                'to': [0,0,800]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=datetime.timedelta(seconds=100)
            ),
            LegWaypoint(positions={
                'from': [0,0,800],
                'to': [0,0,1000]
            }),
        ]

        meta = FlightPlanMeta(
            bot_model=BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        )

        expected_flight_plan = FlightPlan(
            waypoints=expected_waypoints,
            starting_tower='TowerOne',
            finishing_tower='TowerTwo',
            meta=meta
        )

        # The flight plan has only one leg, so we expect this leg to be split
        scheduler.recalculate_flight_plan(flight_plan)
        self.assertEqual(flight_plan, expected_flight_plan)

    def test_recalculate_flight_plan_roundtrip_with_action(self):
        bot_schemas = [
            BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Refueler",
                model="TestI",
                cruising_altitude=100
            ),
            BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        ]

        waypoints = [
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,1000]
            }),
            ActionWaypoint(
                action="payload",
                duration=datetime.timedelta(seconds=500)
            ),
            LegWaypoint(positions={
                'from': [0,0,1000],
                'to': [0,0,0]
            })
        ]

        meta = FlightPlanMeta(
            bot_model=BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        )

        flight_plan = FlightPlan(
            waypoints=waypoints,
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
            meta=meta
        )

        towers = [
            Tower(
                id='TowerOne',
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1,
                landing_time=1,
                bot_capacity=10,
                payload_capacity=10
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bot_schemas=bot_schemas,
            payload_schemas=[],
            bot_manager=ResourceManager([]),
            payload_manager=ResourceManager([]),
            refuel_duration=datetime.timedelta(seconds=10),
            remaining_flight_time_at_refuel=datetime.timedelta(seconds=20),
            refuel_anticipation_buffer=datetime.timedelta(seconds=10)
        )

        expected_waypoints = [
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,470]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=datetime.timedelta(seconds=10)
            ),
            LegWaypoint(positions={
                'from': [0,0,470],
                'to': [0,0,940]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=datetime.timedelta(seconds=10)
            ),
            LegWaypoint(positions={
                'from': [0,0,940],
                'to': [0,0,1000]
            }),
            ActionWaypoint(
                action="payload",
                duration=datetime.timedelta(seconds=410)
            ),
            ActionWaypoint(
                action="being_recharged",
                duration=datetime.timedelta(seconds=10)
            ),
            ActionWaypoint(
                action="payload",
                duration=datetime.timedelta(seconds=90)
            ),
            LegWaypoint(positions={
                'from': [0,0,1000],
                'to': [0,0,620]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=datetime.timedelta(seconds=10)
            ),
            LegWaypoint(positions={
                'from': [0,0,620],
                'to': [0,0,150]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=datetime.timedelta(seconds=10)
            ),
            LegWaypoint(positions={
                'from': [0,0,150],
                'to': [0,0,0]
            }),
        ]

        meta = FlightPlanMeta(
            bot_model=BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        )

        expected_flight_plan = FlightPlan(
            waypoints=expected_waypoints,
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
            meta=meta
        )

        scheduler.recalculate_flight_plan(flight_plan)
        self.assertEqual(flight_plan, expected_flight_plan)

    def test_recalculate_flight_plan_roundtrip_with_giving_refuel_action(self):
        bot_schemas = [
            BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Refueler",
                model="TestI",
                cruising_altitude=100
            ),
            BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        ]

        waypoints = [
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,500]
            }),
            ActionWaypoint(
                action="refuel_anticipation_buffer",
                duration=datetime.timedelta(seconds=100)
            ),
            ActionWaypoint(
                action="giving_recharge",
                duration=datetime.timedelta(seconds=100)
            ),
            LegWaypoint(positions={
                'from': [0,0,500],
                'to': [0,0,0]
            })
        ]

        meta = FlightPlanMeta(
            bot_model=BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        )

        flight_plan = FlightPlan(
            waypoints=waypoints,
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
            meta=meta
        )

        towers = [
            Tower(
                id='TowerOne',
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1,
                landing_time=1,
                bot_capacity=10,
                payload_capacity=10
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bot_schemas=bot_schemas,
            payload_schemas=[],
            bot_manager=ResourceManager([]),
            payload_manager=ResourceManager([]),
            refuel_duration=datetime.timedelta(seconds=100),
            remaining_flight_time_at_refuel=datetime.timedelta(seconds=150),
            refuel_anticipation_buffer=datetime.timedelta(seconds=100)
        )

        expected_waypoints = [
            LegWaypoint(positions={
                'from': [0,0,0],
                'to': [0,0,250]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=datetime.timedelta(seconds=100)
            ),
            LegWaypoint(positions={
                'from': [0,0,250],
                'to': [0,0,500]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=datetime.timedelta(seconds=100)
            ),
            ActionWaypoint(
                action="refuel_anticipation_buffer",
                duration=datetime.timedelta(seconds=100)
            ),
            ActionWaypoint(
                action="giving_recharge",
                duration=datetime.timedelta(seconds=100)
            ),
            LegWaypoint(positions={
                'from': [0,0,500],
                'to': [0,0,450]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=datetime.timedelta(seconds=100)
            ),
            LegWaypoint(positions={
                'from': [0,0,450],
                'to': [0,0,200]
            }),
            ActionWaypoint(
                action="being_recharged",
                duration=datetime.timedelta(seconds=100)
            ),
            LegWaypoint(positions={
                'from': [0,0,200],
                'to': [0,0,0]
            }),
        ]

        meta = FlightPlanMeta(
            bot_model=BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        )

        expected_flight_plan = FlightPlan(
            waypoints=expected_waypoints,
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
            meta=meta
        )

        # The flight plan has only one leg, so we expect this leg to be split
        scheduler.recalculate_flight_plan(flight_plan)
        self.assertEqual(flight_plan, expected_flight_plan)

    def test_get_nearest_towers_to_waypoint(self):
        bot_schemas = [
            BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Refueler",
                model="TestI",
                cruising_altitude=100
            ),
            BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        ]

        waypoint = ActionWaypoint(
            action="being_recharged",
            duration=datetime.timedelta(seconds=100)
        )

        waypoint.position = [50,50,50]


        towers = [
            Tower(
                id='TowerOne',
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1,
                landing_time=1,
                bot_capacity=10,
                payload_capacity=10
            ),
            Tower(
                id='TowerTwo',
                position=[30,30,30],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1,
                landing_time=1,
                bot_capacity=10,
                payload_capacity=10
            ),
            Tower(
                id='TowerThree',
                position=[110,110,110],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1,
                landing_time=1,
                bot_capacity=10,
                payload_capacity=10
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bot_schemas=bot_schemas,
            payload_schemas=[],
            bot_manager=ResourceManager([]),
            payload_manager=ResourceManager([]),
            refuel_duration=datetime.timedelta(seconds=100),
            remaining_flight_time_at_refuel=datetime.timedelta(seconds=150),
            refuel_anticipation_buffer=datetime.timedelta(seconds=100)
        )

        nearest_towers = scheduler.get_nearest_towers_to_waypoint(waypoint)
        expected_nearest_towers = [towers[1], towers[0], towers[2]]
        self.assertEqual(nearest_towers, expected_nearest_towers)

    def test_stretch_flight_plan(self):
        bot_schemas = [
            BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
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

        meta = FlightPlanMeta(
            bot_model=BotSchema(
                flight_time=500,
                speed=1,
                bot_type="Carrier",
                model="CarrierI",
                cruising_altitude=100
            )
        )

        flight_plan = FlightPlan(
            waypoints=waypoints,
            starting_tower='TowerOne',
            finishing_tower='TowerOne',
            meta=meta
        )

        towers = [
            Tower(
                id='TowerOne',
                position=[0,0,0],
                parallel_launchers=1,
                parallel_landers=1,
                launch_time=1,
                landing_time=1,
                bot_capacity=10,
                payload_capacity=10
            )
        ]

        scheduler = Scheduler(
            towers=towers,
            bot_schemas=bot_schemas,
            payload_schemas=[],
            bot_manager=ResourceManager([]),
            payload_manager=ResourceManager([]),
            refuel_duration=datetime.timedelta(seconds=100),
            remaining_flight_time_at_refuel=datetime.timedelta(seconds=200),
            refuel_anticipation_buffer=datetime.timedelta(seconds=100)
        )

        now = datetime.datetime.now()

        scheduler.approximate_timings(
            flight_plan=flight_plan,
            launch_time=now
        )

        scheduler.add_positions_to_action_waypoints(flight_plan)

        start_time_before_stretch = flight_plan.start_time
        end_time_before_stretch = flight_plan.end_time

        scheduler.stretch_flight_plan(
            flight_plan=flight_plan,
            start_delta=datetime.timedelta(minutes=1),
            end_delta=datetime.timedelta(minutes=1)
        )

        print(f"Original start time {start_time_before_stretch} and end time {end_time_before_stretch}")
        print(f"New starting {flight_plan.start_time} and new end time {flight_plan.end_time}")
        self.assertEqual(flight_plan.start_time, start_time_before_stretch - datetime.timedelta(minutes=1))
        self.assertEqual(flight_plan.end_time, end_time_before_stretch + datetime.timedelta(minutes=1))
        self.assertEqual(len(flight_plan.waypoints), 6)
