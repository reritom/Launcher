from typing import List

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
