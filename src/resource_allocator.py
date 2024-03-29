from typing import List, Optional
import datetime, uuid
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

class AllocationError(Exception):
    pass

@dataclass
class Allocation:
    id: str
    from_datetime: datetime.datetime
    to_datetime: datetime.datetime
    blob: dict

@dataclass
class Resource:
    id: str

class ResourceAllocator:
    """
    This class handles the scheduling of resources
    A Resource is a single object which can't have overlapping allocations
    """
    def __init__(self, reference: str, resources: List[Resource] = None):
        self.resources = {resource.id: resource for resource in resources} if resources else {}
        self.allocator = {resource.id: [] for resource in resources} if resources else {}
        self.reference = f"{reference} Allocator"

    def add_resource(self, resource: Resource):
        if resource.id in self.resources:
            raise AllocationError("Attempting to add resource with existing id")

        self.resources[resource.id] = resource
        self.allocator[resource.id] = []

    def allocate_resource(self, resource_id: str, from_datetime: datetime.datetime, to_datetime: datetime.datetime, **kwargs) -> Optional[str]:
        """
        Attempt to allocate a resource or raise an AllocationError if unable
        :returns: Allocation id if an allocation was made
        """
        for allocation in reversed(self.allocator[resource_id]):
            # If either of the points of the requested allocation lie on or between an existing one, reject it
            if (
                to_datetime > allocation.from_datetime and to_datetime <= allocation.to_datetime
                or from_datetime >= allocation.from_datetime and from_datetime < allocation.to_datetime
            ):
                logger.warning(f"{self.reference} - Allocation from {allocation.from_datetime} to {allocation.to_datetime} already taken by {allocation}")
                logger.warning(f"{self.reference} - Attempted allocation from {from_datetime} to {to_datetime} failed for resource id {resource_id}")
                raise AllocationError(f"Resource {resource_id} already allocated")

        logger.info(f"{self.reference} - Allocating {resource_id} from {from_datetime} to {to_datetime} {kwargs}")
        self.allocator[resource_id].append(
            Allocation(
                id=uuid.uuid4(),
                from_datetime=from_datetime,
                to_datetime=to_datetime,
                blob=kwargs
            )
        )

        return self.allocator[resource_id][-1].id

    def get_allocations(self, resource_id: str) -> Optional[List[Allocation]]:
        """
        Get a list of all the allocations for a given resource
        """
        if resource_id in self.allocator:
            return list(reversed(self.allocator[resource_id]))

    def get_allocation_by_time(self, resource_id: str, allocation_time: datetime.datetime):
        """
        Find the allocation of a given resource for a given time
        """
        for allocation in self.allocator.get(resource_id, []):
            if allocation_time >= allocation.from_datetime and allocation_time <= allocation.to_datetime:
                return allocation

    def get_allocation_by_id(self, allocation_id: str) -> Optional[Allocation]:
        """
        Retrieve an allocation by id if it exists
        """
        for resource_id in self.allocator:
            for index, allocation in enumerate(self.allocator[resource_id]):
                if allocation.id == allocation_id:
                    return allocation

    def delete_allocation(self, allocation_id: str) -> None:
        """
        Delete an allocation by allocation id if it exists
        """
        logger.debug(f"{self.reference} -  Deleting allocation")
        for resource_id in self.allocator:
            for index, allocation in enumerate(self.allocator[resource_id]):
                if allocation.id == allocation_id:
                    logger.debug(f"{self.reference} - Allocation successfully removed")
                    self.allocator[resource_id].pop(index)
                    return

    def is_allocation_available(self, resource_id: str, from_datetime: datetime.datetime, to_datetime: datetime.datetime) -> bool:
        """
        We check if the allocation is available by attempting to create it
        """
        logger.debug(f"{self.reference} - Checking if allocation is available for {resource_id} from {from_datetime} to {to_datetime}")
        try:
            allocation_id = self.allocate_resource(resource_id, from_datetime, to_datetime)
            self.delete_allocation(allocation_id)
            return True
        except AllocationError:
            return False
