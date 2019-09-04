from typing import List
import datetime

from src.resource_allocator import ResourceAllocator, Resource
from src.resource_tracker import ResourceTracker

class ResourceManager:
    """
    This class managers a list of resources
    We create an allocator that handles all the resources
    And a resource tracker for each of the resources
    """
    def __init__(self, resources: List[Resource]):
        self.resources = resources
        self.allocator = ResourceAllocator(resources)
        self.trackers = {}

    def set_tracker(self, resource_id: str, initial_context: dict):
        if resource_id in self.trackers:
            raise Exception("Attempting to overwrite an already defined tracker")

        self.trackers[resource_id] = ResourceTracker(initial_context)

    def is_allocation_available(resource_id: str, from_datetime: datetime.datetime, to_datetime: datetime.datetime) -> bool:
        return self.allocator.is_allocation_available(
            resource_id=resource_id,
            from_datetime=from_datetime,
            to_datetime=to_datetime
        )

    def allocate_resource(resource_id: str, from_datetime: datetime.datetime, tower_id: datetime.datetime, **kwargs) -> bool:
        tracker_dict = {
            'from_datetime': from_datetime,
            'to_datetime': to_datetime,
        }
        tracker_dict.update(kwargs)
        self.trackers[resource_id].append(tracker_dict)

        return self.allocator.allocate_resource(
            resource_id=resource_id,
            from_datetime=from_datetime,
            to_datetime=to_datetime
            **kwargs
        )
