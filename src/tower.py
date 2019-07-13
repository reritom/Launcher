from .flight_plan import FlightPlan

import datetime
import json

class Tower:
    def __init__(self, inventory, position, parallel_launchers, parallel_landers, launch_time):
        self.inventory = inventory
        self.position = position
        self.parallel_launchers = parallel_launchers
        self.parallel_landers = parallel_landers
        self.launch_time = launch_time
        self.events = []

    @classmethod
    def from_file(cls, filepath):
        with open(filepath, 'r') as f:
            tower_dict = json.load(f)

        return cls.from_dict(tower_dict)

    @classmethod
    def from_dict(cls, tower_dict) -> 'Tower':
        return cls(
            inventory=tower_dict['inventory'],
            position=tower_dict['cartesian_position'],
            parallel_launchers=tower_dict['parallel_launchers'],
            parallel_landers=tower_dict['parallel_landers'],
            launch_time=tower_dict['launch_time']
        )

    def register_flight_plan(self, flight_plan: FlightPlan, when: datetime.datetime):
        pass
