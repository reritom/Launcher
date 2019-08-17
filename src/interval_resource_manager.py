from .resource_manager import ResourceManager, Resource, AllocationError

import datetime
from typing import Optional, List

class IntervalResourceManager(ResourceManager):
    """
    This module extends the resource manager to only allow allocation of predefined intervals.
    """
    def __init__(self, interval_duration: datetime.timedelta, resources: Optional[List[Resource]] = None):
        self.interval_duration = interval_duration
        assert isinstance(self.interval_duration, datetime.timedelta)
        self.daily_intervals = datetime.timedelta(days=1) // interval_duration
        assert self.daily_intervals >= 1
        self.days = {}
        super().__init__(resources=resources)

    def allocate_resource(self, resource_id: str, date: datetime.datetime, interval: int, **kwargs) -> str:
        """
        This function wraps the ResourceManager function but with interval logic.
        Returns the allocation id or raises an AllocationError
        """
        from_datetime = datetime.datetime.strptime(date.strftime("%d/%m/%Y"), "%d/%m/%Y") + (interval)*self.interval_duration
        to_datetime = from_datetime + (interval+1)*self.interval_duration

        try:
            allocation_id = super().allocate_resource(
                resource_id=resource_id,
                from_datetime=from_datetime,
                to_datetime=to_datetime,
                **kwargs
            )
            self.days.setdefault(date.strftime("%d/%m/%Y"), set())
            self.days[date.strftime("%d/%m/%Y")].add(interval)
            return allocation_id
        except AllocationError as e:
            # Explicitly catching and throwing to show we expect it
            raise e from None

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
        We don't want this parent method to be used, so we hide it
        """
        raise NotImplementedError("This method is unavailable")

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
        starting_times_delta = [
            (interval_time_tuple[0], abs(interval_time_tuple[1] - reference_time))
            for interval_time_tuple in starting_times
        ]

        starting_times_delta.sort(key=lambda item: item[1])
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
        ending_times_delta = [
            (interval_time_tuple[0], abs(interval_time_tuple[1] - reference_time))
            for interval_time_tuple in ending_times
        ]

        ending_times_delta.sort(key=lambda item: item[1])
        return [
            interval_time_tuple[0]
            for interval_time_tuple in ending_times_delta
        ]
