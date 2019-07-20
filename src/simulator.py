import numpy as np
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.animation
import pandas as pd

class Simulator:
    def simulate_schedule(self, schedule):
        pass

    def simulate_flight_plan(self, flight_plan):
        # Determine the max and mins for each axis
        ranges = self.determine_flight_plan_ranges(flight_plan)
        print(f"Ranges are {ranges}")

        a = np.random.rand(2000, 3)*10
        t = np.array([np.ones(100)*i for i in range(20)]).flatten()
        df = pd.DataFrame({"time": t ,"x" : a[:,0], "y" : a[:,1], "z" : a[:,2]})
        
        def update_graph(num):
            data=df[df['time']==num]
            graph.set_data (data.x, data.y)
            graph.set_3d_properties(data.z)
            title.set_text('3D Test, time={}'.format(num))
            return title, graph,

        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        title = ax.set_title('3D Test')
        data=df[df['time']==0]
        graph, = ax.plot(data.x, data.y, data.z, linestyle="", marker="o")
        ani = matplotlib.animation.FuncAnimation(
            fig,
            update_graph,
            19,
            interval=40,
            blit=True
        )
        plt.show()


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
