class Simulator:
    def simulate_schedule(self, schedule):
        pass

    def simulate_flight_plan(self, flight_plan):
        # Determine the max and mins for each axis
        ranges = self.determine_flight_plan_ranges(flight_plan)
        print(f"Ranges are {ranges}")
        pass

    def determine_flight_plan_ranges(self, flight_plan) -> tuple:
        # -> [[x_max, x_min], [y_max, y_min], [z_max, z_min]]
        axis = [[0, 0], [0, 0], [0, 0]]

        for waypoint in flight_plan.waypoints:
            if waypoint.is_leg:
                for index, value in enumerate(waypoint.to_pos):
                    axis[index] = [
                        value if value > axis[index][0] else axis[index][0],
                        value if value < axis[index][1] else axis[index][1]
                    ]

                for index, value in enumerate(waypoint.from_pos):
                    axis[index] = [
                        value if value > axis[index][0] else axis[index][0],
                        value if value < axis[index][1] else axis[index][1]
                    ]

        return axis[0][0], axis[0][1], axis[1][0], axis[1][1], axis[2][0], axis[2][1]
