import datetime
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

from .resource_allocator import ResourceAllocator, Resource, AllocationError

class IntervalResourceAllocator(ResourceAllocator):
    """
    This module extends the resource manager to only allow allocation of predefined intervals.
    """
    def __init__(self, interval_duration: datetime.timedelta, resources: Optional[List[Resource]] = None):
        self.interval_duration = interval_duration
        assert isinstance(self.interval_duration, datetime.timedelta)

        self.daily_intervals = datetime.timedelta(days=1) // interval_duration
        assert self.daily_intervals >= 1

        # This is for storing allocation data for interval based referencing
        self.days = {}
        super().__init__(resources=resources)

    def allocate_resource(self, resource_id: str, date: datetime.datetime, interval: int, **kwargs) -> str:
        """
        This function wraps the ResourceManager function but with interval logic.
        Returns the allocation id or raises an AllocationError
        """
        from_datetime = datetime.datetime.strptime(date.strftime("%d/%m/%Y"), "%d/%m/%Y") + (interval)*self.interval_duration
        to_datetime = from_datetime + (interval+1)*self.interval_duration
        allocation_blob = {'interval': interval}
        allocation_blob.update(kwargs)

        try:
            allocation_id = super().allocate_resource(
                resource_id=resource_id,
                from_datetime=from_datetime,
                to_datetime=to_datetime,
                **allocation_blob
            )
            self.days.setdefault(date.strftime("%d/%m/%Y"), set())
            self.days[date.strftime("%d/%m/%Y")].add(interval)
            return allocation_id
        except AllocationError as e:
            # Explicitly catching and throwing to show we expect it
            raise e from None

    def delete_allocation(self, allocation_id: str):
        """
        Delete the allocation from the interval day dict in this class, and then perform
        the deletion in the parent class
        """
        allocation = self.get_allocation_by_id(allocation_id)

        if not allocation:
            return

        allocation_date = allocation.from_datetime.strftime("%d/%m/%Y")
        if allocation_date in self.days:
            try:
                self.days[allocation_date].remove(allocation.blob['interval'])
            except KeyError as e:
                logger.warning(f"Failed to delete allocation {e}")

        return super().delete_allocation(allocation_id)

    def get_available_intervals(self, date: datetime.datetime) -> List[int]:
        """
        Return a list of intervals available for a given day
        """
        date_string = date.strftime("%d/%m/%Y")
        interval_list = [interval for interval in range(self.daily_intervals)]

        if date_string in self.days:
            interval_list = [interval for interval in interval_list if interval not in self.days[date_string]]

        return interval_list

    def is_allocation_available(self, *args, **kwargs):
        """
        We don't want this parent method to be used, so we hide it for now
        """
        raise NotImplementedError()

    def get_window_for_interval(self, date: datetime.datetime, interval: int) -> tuple:
        """
        For a given interval number and date, return a tuple of the start and end of the window
        """
        assert interval <= self.daily_intervals
        date = datetime.datetime.strptime(date.strftime("%d/%m/%Y"), "%d/%m/%Y")
        return (
            date + interval*self.interval_duration,
            date + (interval + 1)*self.interval_duration
        )

    def get_nearest_intervals_to_window_start(self, reference_time: datetime.datetime) -> List[tuple]:
        """
        For a given day, list all the available intervals, nearest first, comparing the supplied
        date to the time at the start of the interval window
        """
        date = datetime.datetime.strptime(reference_time.strftime("%d/%m/%Y"), "%d/%m/%Y")
        available_intervals = self.get_available_intervals(date=date)

        starting_times = [
            (interval, date + interval*self.interval_duration)
            for interval in available_intervals
        ]

        # For each starting time, look at the difference
        starting_times_delta = [
            (interval_time_tuple[0], abs(interval_time_tuple[1] - reference_time))
            for interval_time_tuple in starting_times
        ]

        # Sort by smallest deltas
        starting_times_delta.sort(key=lambda item: item[1])

        # Return just the intervals
        return [
            interval_time_tuple[0]
            for interval_time_tuple in starting_times_delta
        ]

    def get_nearest_intervals_to_window_end(self, reference_time: datetime.datetime) -> List[tuple]:
        """
        For a given day, list all the available intervals, nearest first, comparing the supplied
        date to the time at the end of the interval window
        """
        date = datetime.datetime.strptime(reference_time.strftime("%d/%m/%Y"), "%d/%m/%Y")
        available_intervals = self.get_available_intervals(date=date)

        ending_times = [
            (interval, date + (interval+1)*self.interval_duration)
            for interval in available_intervals
        ]

        # For each ending time, look at the difference
        ending_times_delta = [
            (interval_time_tuple[0], abs(interval_time_tuple[1] - reference_time))
            for interval_time_tuple in ending_times
        ]

        # Sort by smallest deltas
        ending_times_delta.sort(key=lambda item: item[1])

        # Return just the intervals
        return [
            interval_time_tuple[0]
            for interval_time_tuple in ending_times_delta
        ]
