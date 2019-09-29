from typing import List
import datetime, uuid
import logging

logger = logging.getLogger(__name__)

from src.resource_allocator import ResourceAllocator, Resource
from src.resource_tracker import ResourceTracker

class ResourceManager:
    """
    This class managers a list of resources
    We create an allocator that handles all the resources
    And a resource tracker for each of the resources
    """
    def __init__(self, reference: str, resources: List[Resource]):
        self.resources = resources
        self.reference = reference
        self.allocator = ResourceAllocator(reference=reference, resources=resources)
        self.trackers = {}

    def set_tracker(self, resource_id: str, initial_context: dict):
        if resource_id in self.trackers:
            logger.warning("Attempting to overwrite an already defined tracker")
            raise Exception("Attempting to overwrite an already defined tracker")

        self.trackers[resource_id] = ResourceTracker(initial_context)

    def is_allocation_available(self, resource_id: str, from_datetime: datetime.datetime, to_datetime: datetime.datetime) -> bool:
        return self.allocator.is_allocation_available(
            resource_id=resource_id,
            from_datetime=from_datetime,
            to_datetime=to_datetime
        )

    def delete_allocation(allocation_id: str):
        """
        Delete an allocation by allocation id, and delete the associated tracker
        """
        allocation = self.allocator.get_allocation_by_id(allocation_id)
        if allocation:
            for track in self.trackers[allocation.resource_id]:
                if track['tracker_id'] == allocation.blob['tracker_id']:
                    self.trackers[allocation.resource_id].pop(track)

        return self.allocator.delete_allocation(allocation_id)


    def allocate_resource(self, resource_id: str, from_datetime: datetime.datetime, to_datetime: datetime.datetime, **kwargs) -> bool:
        tracker_dict = {
            'tracker_id': str(uuid.uuid4()),
            'from_datetime': from_datetime,
            'to_datetime': to_datetime
        }
        tracker_dict.update(kwargs)
        self.trackers[resource_id].append(tracker_dict)

        return self.allocator.allocate_resource(
            resource_id=resource_id,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
            tracker_id=tracker_dict['tracker_id'],
            **kwargs
        )
