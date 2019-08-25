from .flight_plan import FlightPlan
from .interval_resource_allocator import IntervalResourceAllocator, Resource, AllocationError

import datetime
import json
from typing import List

class Tower:
    def __init__(self, id: str, position: tuple, parallel_launchers: int, parallel_landers: int, launch_time: int, landing_time: int):
        self.id = id
        self.position = position
        self.parallel_launchers = parallel_launchers
        self.parallel_landers = parallel_landers
        self.launch_time = launch_time
        self.landing_time = landing_time

        # Create the resource managers for the launchers and landers
        launch_resources = [Resource(id=i) for i in range(parallel_launchers)]
        self.launch_allocator = IntervalResourceAllocator(
            interval_duration=datetime.timedelta(seconds=self.launch_time),
            resources=launch_resources
        )

        landing_resources = [Resource(id=i) for i in range(parallel_landers)]
        self.landing_allocator = IntervalResourceAllocator(
            interval_duration=datetime.timedelta(seconds=self.landing_time),
            resources=landing_resources
        )

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
            position=tower_dict['position'],
            parallel_launchers=tower_dict['parallel_launchers'],
            parallel_landers=tower_dict['parallel_landers'],
            launch_time=tower_dict['launch_time'],
            landing_time=tower_dict['landing_time'],
            id=tower_dict['id']
        )

    def allocate_launch(self, flight_plan_id: str, date: datetime.datetime, interval: int) -> bool:
        """
        For a given flight plan, attempt to allocate the launch time
        """
        for resource in self.launch_allocator.resources:
            try:
                allocation_id = self.launch_allocator.allocate_resource(
                    resource_id=resource.id,
                    date=date,
                    interval=interval
                )
                return allocation_id
            except AllocationError:
                pass

        # None of the launchers are available for this launch window
        raise AllocationError("Unable to allocate launch")

    def deallocate_launch(self, allocation_id: str):
        """
        For a given allocation id, attempt to deallocate it from all launch resources
        """
        self.launch_allocator.delete_allocation(allocation_id)

    def allocate_landing(self, flight_plan_id: str, date: datetime.datetime, interval: int) -> str:
        """
        For a given flight plan, attempt to allocate the launch time
        """
        for resource in self.landing_allocator.resources:
            try:
                allocation_id = self.landing_allocator.allocate_resource(
                    resource_id=resource.id,
                    date=date,
                    interval=interval
                )
                return allocation_id
            except AllocationError:
                pass

        # None of the landers are available for this landing window
        raise AllocationError("Unable to allocate landing")

    def deallocate_landing(self, allocation_id: str):
        """
        For a given allocation id, attempt to deallocate it from all landing resources
        """
        self.landing_allocator.delete_allocation(allocation_id)

    def get_nearest_landing_time(self, reference_time: datetime.datetime) -> datetime.datetime:
        landing_window_start = reference_time
        landing_window_end = reference_time - datetime.timedelta(seconds=self.landing_time)
        ...

    def get_nearest_launch_time(self, reference_time: datetime.datetime) -> datetime.datetime:
        launch_window_start = reference_time - datetime.timedelta(seconds=self.launch_time)
        launch_window_end = reference_time
        ...

    def __repr__(self):
        return "Tower {}".format(self.position)
