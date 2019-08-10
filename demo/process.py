"""
This script is for processing the raw nested demos in this directory into faster mp4s and gifs
This script requires ffmpeg
"""
import os, argparse

def process(overwrite: bool):
    subdirs = [
        subdir
        for subdir in os.listdir(".")
        if os.path.isdir(subdir)
        and subdir.startswith("demo_")
    ]

    for subdir in subdirs:
        if os.path.exists(os.path.join('.', subdir, 'raw')):
            # Look at the nested files to find any mp4s
            mp4s = [
                (mp4, os.path.join('.', subdir, 'raw', mp4))
                for mp4 in os.listdir(os.path.join('.', subdir, 'raw'))
                if mp4.endswith('.mp4')
            ]

            # Create the new processed subdir
            if not os.path.exists(os.path.join('.', subdir, 'processed')):
                os.mkdir(os.path.join('.', subdir, 'processed'))

            # For each mp4, see if there is already a processed version
            for mp4, raw_mp4_path in mp4s:
                processed_mp4_path = os.path.join('.', subdir, 'processed', mp4)
                gif_path = os.path.join('.', subdir, 'processed', mp4.replace('.mp4', '.gif'))

                if not os.path.exists(processed_mp4_path) or overwrite and False:
                    # First we speed it up
                    print(f"Speeding up {mp4}")
                    os.system(f"ffmpeg -i {raw_mp4_path} -filter:v 'setpts=0.2*PTS' {processed_mp4_path}")
                else:
                    print(f"Skipping {mp4} as it already exists")

                if not os.path.exists(gif_path) or overwrite:
                    # Then convert it to a gif
                    print(f"Converting {mp4} to gif")#os.system(f"ffmpeg -i {processed_mp4_path} -vf scale=320:-1 -r 10 -f image2pipe -vcodec ppm - | convert -delay 5 -loop 0 - {gif_path}")
                    os.system(f"ffmpeg -i {processed_mp4_path} -filter_complex 'fps=15,scale=640:-1:flags=lanczos,split [o1] [o2];[o1] palettegen [p]; [o2] fifo [o3];[o3] [p] paletteuse' {gif_path}")

if __name__ == '__main__':
    process(overwrite=True)
