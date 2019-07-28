import numpy as np
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.animation
import pandas as pd
from typing import Optional
import datetime
import math as maths

# To hide the df.set_value deprecation warning for now
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

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

    def determine_schedule_ranges(self, schedule) -> dict:
        """
        This method returns a dictionary containing the max and min value for each axis
        -> {
            'xmax': <int>,
            'xmin': <int>,
            'ymax': <int>,
            'ymin': <int>,
            'zmax': <int>,
            'zmin': <int>
        }
        """
        assert schedule.flight_plans

        flight_plan_range_dicts = [
            self.determine_flight_plan_ranges(flight_plan)
            for flight_plan in schedule.flight_plans
        ]

        ranges = flight_plan_range_dicts[0]

        if len(flight_plan_range_dicts) > 1:
            for flight_plan_range_dict in flight_plan_range_dicts[1:]:
                for key in ['xmin', 'ymin', 'zmin']:
                    if flight_plan_range_dict[key] < ranges[key]:
                        ranges[key] = flight_plan_range_dict[key]

                for key in ['xmax', 'ymax', 'zmax']:
                    if flight_plan_range_dict[key] > ranges[key]:
                        ranges[key] = flight_plan_range_dict[key]

        return ranges

    def simulate_schedule(self, schedule):
        # Determine the max and mins for each axis
        ranges = self.determine_schedule_ranges(schedule)

        flight_plan_dataframes = [
            self.get_flight_plan_dataframe(flight_plan)
            for flight_plan in schedule.flight_plans
        ]

        # Get the start time of the schedule to determine the offsets
        schedule_start_time = schedule.start_time # Computed, so we store it
        print(f"Schedule starts at {schedule_start_time} and ends at {schedule.end_time}")

        # Simulation duration in seconds
        simulation_duration = int(schedule.duration)

        # Plot setup
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.set_xlim3d(int(ranges['xmin']), int(ranges['xmax']))
        ax.set_ylim3d(int(ranges['ymin']), int(ranges['ymax']))
        ax.set_zlim3d(int(ranges['zmin']), int(ranges['zmax']))
        title = ax.set_title('3D Test')

        def update_graph(num, *lines):
            now = schedule_start_time + datetime.timedelta(seconds=num)

            for index, flight_plan in enumerate(schedule.flight_plans):
                # Look at relevent flight plans
                if now >= flight_plan.start_time and now <= flight_plan.end_time:
                    # Get the dataframe for this flight plan
                    dataframe = flight_plan_dataframes[index]
                    dataframe_index = int((now - flight_plan.start_time).total_seconds())

                    # Get the row
                    try:
                        data = dataframe.iloc[dataframe_index]
                    except Exception as e:
                        print(f"For FP {index} trying to access {dataframe_index}")
                        print(f"in {dataframe}")
                        print(e)
                        continue

                    # Then we show this bot position
                    lines[index][0].set_alpha(1.0)
                    lines[index][0].set_data(data.x, data.y)
                    lines[index][0].set_3d_properties(data.z)

                    if data.being_recharged == 1:
                        lines[index][1].set_data([data.x, data.x], [data.y, data.y])
                        lines[index][1].set_3d_properties([data.z, 0])
                        lines[index][1].set_alpha(1.0)
                    else:
                        lines[index][1].set_data([data.x, data.x], [data.y, data.y])
                        lines[index][1].set_3d_properties([data.z, data.z])
                        lines[index][1].set_alpha(0.0)
                else:
                    # We hide the line
                    lines[index][0].set_alpha(0.0)
                    lines[index][1].set_alpha(0.0)

            title.set_text('{}'.format(str(datetime.timedelta(seconds=num))))
            return title, lines,

        flight_plan_dot_lines = []
        for index, flight_plan_dataframe in enumerate(flight_plan_dataframes):
            row_zero = flight_plan_dataframe.iloc[0]

            dot_line, = ax.plot(
                [row_zero.x],
                [row_zero.y],
                row_zero.z,
                linestyle="",
                marker="o" if schedule.flight_plans[index].id == 'main' else '.',
                color='red' if schedule.flight_plans[index].id == 'main' else 'blue',
                alpha=1.0 if schedule.flight_plans[index].id == 'main' else 0.0
            )

            recharge_line, = ax.plot(
                [row_zero.x],
                [row_zero.y],
                row_zero.z,
                linestyle=":",
                marker=",",
                color='red' if schedule.flight_plans[index].id == 'main' else 'blue',
                alpha=0.0
            )

            flight_plan_dot_lines.append((dot_line, recharge_line))

        print(f"Simulation duration {simulation_duration}")

        ani = matplotlib.animation.FuncAnimation(
            fig,
            update_graph,
            simulation_duration,
            interval=10,
            blit=False,
            fargs=(flight_plan_dot_lines)
        )
        plt.show()

    def simulate_flight_plan(self, flight_plan):
        # Determine the max and mins for each axis
        ranges = self.determine_flight_plan_ranges(flight_plan)
        #print(f"Ranges are {ranges}")

        flight_plan_dataframe = self.get_flight_plan_dataframe(flight_plan)
        #print(flight_plan_dataframe)

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

    def get_flight_plan_duration(self, flight_plan):
        bot = self.get_bot_by_model(flight_plan.bot_model)

        duration = 0
        for waypoint in flight_plan.waypoints:
            if waypoint.is_action:
                duration += waypoint.duration
            elif waypoint.is_leg:
                duration += distance_between(waypoint.from_pos, waypoint.to_pos)/bot.speed

        return int(duration)

    def get_flight_plan_dataframe(self, flight_plan) -> pd.DataFrame:
        """
        Return a dataframe representation of the flight plan containing the coordinates and time in seconds
        from the start of the flight
        """
        bot = self.get_bot_by_model(flight_plan.bot_model)
        duration = self.get_flight_plan_duration(flight_plan)

        time, x, y, z, being_refueled, fuel_percent = [], [], [], [], [], []

        current_waypoint_index = 0
        current_duration_into_waypoint = 0
        for second in range(duration):
            # See which waypoint this is in to determine the position
            try:
                current_waypoint = flight_plan.waypoints[current_waypoint_index]
            except IndexError:
                break

            current_waypoint_duration = (
                current_waypoint.duration
                if current_waypoint.is_action
                else int(distance_between(current_waypoint.from_pos, current_waypoint.to_pos)/bot.speed)
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

            current_duration_into_waypoint += 1


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
