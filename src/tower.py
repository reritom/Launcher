from .flight_plan import FlightPlan

import datetime
import json
from typing import List

class Tower:
    def __init__(self, id, inventory, position, parallel_launchers, parallel_landers, launch_time):
        self.id = id
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
    def from_catalogue_file(cls, file_path: str) -> List['Tower']:
        """
        A catalogue file is a file containing a list of tower definitions
        """
        with open(file_path, 'r') as f:
            catalogue = json.load(f)

        return [
            cls.from_dict(tower_dict)
            for tower_dict in catalogue
        ]

    @classmethod
    def from_dict(cls, tower_dict) -> 'Tower':
        return cls(
            inventory=tower_dict['inventory'],
            position=tower_dict['cartesian_position'],
            parallel_launchers=tower_dict['parallel_launchers'],
            parallel_landers=tower_dict['parallel_landers'],
            launch_time=tower_dict['launch_time'],
            id=tower_dict['id']
        )

    def register_flight_plan(self, flight_plan: FlightPlan, when: datetime.datetime):
        pass

    def __repr__(self):
        return "Tower {}".format(self.position)

    @property
    def inventory_models(self):
        return [
            inventory['model']
            for inventory
            in self.inventory
        ]
