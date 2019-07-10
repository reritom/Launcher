class Tower:
    def __init__(self, inventory, position, parallel_launchers, launch_time):
        self.inventory = inventory
        self.position = position
        self.parallel_launchers = parallel_launchers
        self.launch_time = launch_time

    @classmethod
    def from_dict(cls, tower_dict) -> 'Tower':
        return cls(
            inventory=tower_dict['inventory'],
            position=tower_dict['cartesian_position'],
            parallel_launchers=tower_dict['parallel_launchers'],
            launch_time=tower_dict['launch_time']
        )
