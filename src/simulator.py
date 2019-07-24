import numpy as np
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.animation
import pandas as pd
from typing import Optional
import datetime

from .bot import Bot
from .tools import distance_between, find_middle_position_by_ratio

class Simulator:
    def __init__(self, bots):
        self.bots = bots

    def get_bot_by_model(self, model: str) -> Optional[Bot]:
        """
        Get the bot object from the catalogue for a given model
        """
        for bot in self.bots:
            if bot.model == model:
                return bot

    def simulate_schedule(self, schedule):
        pass

    def simulate_flight_plan(self, flight_plan):
        # Determine the max and mins for each axis
        ranges = self.determine_flight_plan_ranges(flight_plan)
        print(f"Ranges are {ranges}")

        flight_plan_dataframe = self.get_flight_plan_dataframe(flight_plan)
        print(flight_plan_dataframe)
        #assert False

        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.set_xlim3d(int(ranges['xmin']), int(ranges['xmax']))
        ax.set_ylim3d(int(ranges['ymin']), int(ranges['ymax']))
        ax.set_zlim3d(int(ranges['zmin']), int(ranges['zmax']))
        title = ax.set_title('3D Test')

        def update_graph(num, *lines):
            data = flight_plan_dataframe.iloc[num]
            lines[0].set_data(data.x, data.y)
            lines[0].set_3d_properties(data.z)
            lines[0].set_color('green')

            if data.being_recharged == 1:
                lines[1].set_data([data.x, data.x], [data.y, data.y])
                lines[1].set_3d_properties([data.z, 0])
                lines[1].set_color('green')
            else:
                lines[1].set_data([data.x, data.x], [data.y, data.y])
                lines[1].set_3d_properties([data.z, data.z])
                lines[1].set_color('green')

            title.set_text('{}'.format(str(datetime.timedelta(seconds=num))))
            return title, lines,

        data = flight_plan_dataframe[flight_plan_dataframe['time']==0]

        # Bot point
        line, = ax.plot(data.x, data.y, data.z, linestyle="", marker="o", color='r')

        # Recharge line
        line1, = ax.plot([data.x, data.x], [data.y, data.y], [data.z, 0], linestyle=":", marker=",", color='r')
        lines = [line, line1]

        ani = matplotlib.animation.FuncAnimation(
            fig,
            update_graph,
            len(flight_plan_dataframe),
            interval=10,
            blit=False,
            fargs=(lines)
        )
        plt.show()

    def get_flight_plan_dataframe(self, flight_plan) -> pd.DataFrame:
        """
        Return a dataframe representation of the flight plan containing the coordinates and time in seconds
        from the start of the flight
        """
        bot = self.get_bot_by_model(flight_plan.bot_model)

        duration = 0
        for waypoint in flight_plan.waypoints:
            if waypoint.is_action:
                duration += waypoint.duration
            elif waypoint.is_leg:
                duration += int(distance_between(waypoint.from_pos, waypoint.to_pos)/bot.speed)

        time, x, y, z, being_refueled, fuel_percent = [], [], [], [], [], []

        current_waypoint_index = 0
        current_duration_into_waypoint = 0
        for second in range(duration):
            # See which waypoint this is in to determine the position
            current_duration_into_waypoint += 1
            try:
                current_waypoint = flight_plan.waypoints[current_waypoint_index]
            except IndexError:
                break
            current_waypoint_duration = (
                current_waypoint.duration
                if current_waypoint.is_action
                else int(distance_between(waypoint.from_pos, waypoint.to_pos)/bot.speed)
            )

            time.append(second)

            if current_duration_into_waypoint < current_waypoint_duration:
                if current_waypoint.is_leg:
                    ratio = current_duration_into_waypoint / current_waypoint_duration
                    split_position = find_middle_position_by_ratio(current_waypoint.from_pos, current_waypoint.to_pos, ratio)
                    x.append(int(split_position[0]))
                    y.append(int(split_position[1]))
                    z.append(int(split_position[2]))
                    being_refueled.append(0)
                elif current_waypoint.is_action:
                    x.append(int(current_waypoint.position[0]))
                    y.append(int(current_waypoint.position[1]))
                    z.append(int(current_waypoint.position[2]))
                    being_refueled.append(1 if current_waypoint.is_being_recharged else 0)
            else:
                current_waypoint_index += 1
                current_duration_into_waypoint = 0

                if current_waypoint.is_leg:
                    x.append(int(current_waypoint.to_pos[0]))
                    y.append(int(current_waypoint.to_pos[1]))
                    z.append(int(current_waypoint.to_pos[2]))
                    being_refueled.append(0)
                elif current_waypoint.is_action:
                    x.append(int(current_waypoint.position[0]))
                    y.append(int(current_waypoint.position[1]))
                    z.append(int(current_waypoint.position[2]))
                    being_refueled.append(1 if current_waypoint.is_being_recharged else 0)


        frame = pd.DataFrame({"time": time, "x": x, "y": y, "z": z, "being_recharged": being_refueled})
        return frame

    def determine_flight_plan_ranges(self, flight_plan) -> dict:
        """
        Return a dictionary containing the min/max ranges for each coordinate
        """
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

        return {
            'xmax': axis[0][0],
            'xmin': axis[0][1],
            'ymax': axis[1][0],
            'ymin': axis[1][1],
            'zmax': axis[2][0],
            'zmin': axis[2][1]
        }
