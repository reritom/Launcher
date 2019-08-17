from .flight_plan import FlightPlan
from .resource_manager import ResourceManager, Resource, AllocationError

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
        self.landing_time = launch_time # TODO, USE NON-LAUNCH VALUE

        # Create the resource managers for the launchers and landers
        launch_resources = [Resource(id=i) for i in range(parallel_launchers)]
        self.launch_allocator = ResourceManager(resources=launch_resources)

        landing_resources = [Resource(id=i) for i in range(parallel_landers)]
        self.landing_allocator = ResourceManager(resources=landing_resources)

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
            position=tower_dict['position'],
            parallel_launchers=tower_dict['parallel_launchers'],
            parallel_landers=tower_dict['parallel_landers'],
            launch_time=tower_dict['launch_time'],
            id=tower_dict['id']
        )

    def allocate_launch(self, flight_plan_id: str, launch_time: datetime.datetime) -> bool:
        """
        For a given flight plan, attempt to allocate the launch time
        """
        launch_window_start = launch_time - datetime.timedelta(seconds=self.launch_time)

        for resource in self.launch_allocator.resources:
            try:
                self.launch_allocator.allocate_resource(
                    resource_id=resource.id,
                    from_datetime=launch_window_start,
                    to_datetime=launch_time
                )
            except AllocationError:
                continue
            else:
                return True

        # None of the launchers are available for this launch window
        return False

    def allocate_landing(self, flight_plan_id: str, landing_time: datetime.datetime) -> bool:
        """
        For a given flight plan, attempt to allocate the launch time
        """
        landing_window_end = landing_time - datetime.timedelta(seconds=self.landing_time)

        for resource in self.landing_allocator.resources:
            try:
                self.landing_allocator.allocate_resource(
                    resource_id=resource.id,
                    from_datetime=landing_time,
                    to_datetime=landing_window_end
                )
            except AllocationError:
                continue
            else:
                return True

        # None of the landers are available for this landing window
        return False

    def get_nearest_landing_time(self, reference_time: datetime.datetime) -> datetime.datetime:
        landing_window_start = reference_time
        landing_window_end = reference_time - datetime.timedelta(seconds=self.landing_time)

    def get_nearest_launch_time(self, reference_time: datetime.datetime) -> datetime.datetime:
        launch_window_start = reference_time - datetime.timedelta(seconds=self.launch_time)
        launch_window_end = reference_time

    def __repr__(self):
        return "Tower {}".format(self.position)

    @property
    def inventory_models(self):
        return [
            inventory['model']
            for inventory
            in self.inventory
        ]
