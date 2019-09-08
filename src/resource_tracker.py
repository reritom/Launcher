import datetime


class ResourceTracker:
    """
    For a given resource, track any changes to an arbritrary values
    """

    def __init__(self, initial_data):
        self.tracker = []
        self.initial_data = initial_data

    def add_track(self, from_time: datetime.datetime, to_time: datetime.datetime, **kwargs):
        self.tracker.append((from_time, to_time, kwargs))

    @property
    def most_recent_track(self) -> tuple:
        return self.tracker[-1]

    def append(self, data: dict) -> None:
        return self.tracker.append(data)

    @property
    def most_recent_track_data(self) -> dict:
        return self.most_recent_track[2]

    @property
    def initial_context(self):
        return self.initial_data
