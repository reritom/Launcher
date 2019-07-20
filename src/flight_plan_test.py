import unittest

from .flight_plan import FlightPlan
from .leg_waypoint import LegWaypoint
from .action_waypoint import ActionWaypoint

class TestFlightPlan(unittest.TestCase):
    def test_flight_plan_to_dict(self):
        waypoints = [
            LegWaypoint(cartesian_positions={
                'from': [0,0,0],
                'to':[10,10,10]
            }),
            ActionWaypoint(
                action="TestAction",
                duration=10
            ),
            LegWaypoint(cartesian_positions={
                'from': [10,10,10],
                'to':[0,0,0]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            starting_position=[0,0,0],
            bot_model="MarkI"
        )

        dict_representation = flight_plan.to_dict()
        expected_representation = {
           'bot_model':'MarkI',
           'starting_position':[0,0,0],
           'waypoints':[
              {
                 'cartesian_positions':{
                    'from':[0,0,0],
                    'to':[10,10,10],
                 },
                 'id':'4e6ac29a-387f-45af-b798-c0e875ddd86c',
                 'type':'leg'
              },
              {
                 'action':'TestAction',
                 'duration':10,
                 'id':'08c9d42f-c0d2-44b2-ab1c-863d1fa13975',
                 'type':'action'
              },
              {
                 'cartesian_positions':{
                    'from':[10,10,10],
                    'to':[0,0,0],
                 },
                 'id':'5640fa37-b6e6-4efd-893d-0d529e64dce2',
                 'type':'leg'
              }
           ]
        }

        # Remove the ids
        for waypoint in expected_representation['waypoints']:
            waypoint['id'] = None

        for waypoint in dict_representation['waypoints']:
            waypoint['id'] = None

        self.assertEqual(dict_representation, expected_representation)

    def test_flight_plan_equals_1(self):
        # This test compares two flight plans with the same construction.
        # This is tested because there are internal values which need to be ignored, like uuids

        waypoints_1 = [
            LegWaypoint(cartesian_positions={
                'from': [0,0,0],
                'to':[10,10,10]
            }),
            ActionWaypoint(
                action="TestAction",
                duration=10
            ),
            LegWaypoint(cartesian_positions={
                'from': [10,10,10],
                'to':[0,0,0]
            })
        ]

        waypoints_2 = [
            LegWaypoint(cartesian_positions={
                'from': [0,0,0],
                'to':[10,10,10]
            }),
            ActionWaypoint(
                action="TestAction",
                duration=10
            ),
            LegWaypoint(cartesian_positions={
                'from': [10,10,10],
                'to':[0,0,0]
            })
        ]

        flight_plan_1 = FlightPlan(
            waypoints=waypoints_1,
            starting_position=[0,0,0],
            bot_model="MarkI"
        )

        flight_plan_2 = FlightPlan(
            waypoints=waypoints_2,
            starting_position=[0,0,0],
            bot_model="MarkI"
        )

        self.assertEqual(flight_plan_1, flight_plan_2)

    def test_flight_plan_equals_ko_invalid_type(self):
        # This test makes sure that comparing a flight plan to another type returns false
        
        waypoints = [
            LegWaypoint(cartesian_positions={
                'from': [0,0,0],
                'to':[10,10,10]
            }),
            ActionWaypoint(
                action="TestAction",
                duration=10
            ),
            LegWaypoint(cartesian_positions={
                'from': [10,10,10],
                'to':[0,0,0]
            })
        ]

        flight_plan = FlightPlan(
            waypoints=waypoints,
            starting_position=[0,0,0],
            bot_model="MarkI"
        )

        self.assertNotEqual(flight_plan, 1)