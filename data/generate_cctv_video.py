"""
Generate realistic sample CCTV road footage for KineticPothole AI visual detection demonstration.
Creates data/sample_cctv_pothole.mp4 simulating a traffic camera overlooking
the SRMIST Service Lane / GST Road corridor.
"""

import os
import math
import cv2
import numpy as np


def generate_cctv_video(output_path="data/sample_cctv_pothole.mp4", duration_sec=10.0, fps=30):
    width, height = 640, 480
    total_frames = int(duration_sec * fps)

    # Use MP4V codec compatible across platforms
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    if not out.isOpened():
        # Fallback to alternate fourcc if mp4v fails
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        output_path = output_path.replace(".mp4", ".avi")
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    print(f"Generating {total_frames} frames of CCTV road footage into {output_path}...")

    # Pothole appears in lane between 3.0s and 7.5s
    pothole_start_frame = int(3.0 * fps)
    pothole_end_frame = int(7.5 * fps)

    for i in range(total_frames):
        t = i / fps
        frame = np.zeros((height, width, 3), dtype=np.uint8)

        # Upper region: Road horizon / roadside (sky & shoulder)
        horizon_y = int(height * 0.35)
        frame[0:horizon_y, :] = (45, 55, 65)  # Dark roadside ambient

        # Lower region: Dark gray asphalt road surface
        asphalt = np.random.normal(55, 3, (height - horizon_y, width, 3)).astype(np.uint8)
        frame[horizon_y:height, :] = asphalt

        # Road boundaries (perspective trapezoid)
        left_top = (int(width * 0.25), horizon_y)
        right_top = (int(width * 0.75), horizon_y)
        left_bot = (int(width * 0.05), height)
        right_bot = (int(width * 0.95), height)

        # Yellow shoulder lines
        cv2.line(frame, left_top, left_bot, (0, 200, 230), 4)
        cv2.line(frame, right_top, right_bot, (0, 200, 230), 4)

        # White center dashes moving with vehicle/road motion
        dash_offset = (i * 12) % 60
        for y_dash in range(horizon_y + dash_offset, height, 60):
            # Perspective factor
            scale = (y_dash - horizon_y) / (height - horizon_y)
            dash_len = int(10 + scale * 25)
            x_center = int(width * 0.5)
            cv2.line(frame, (x_center, y_dash), (x_center, min(height, y_dash + dash_len)), (230, 230, 230), int(2 + scale * 4))

        # Pothole obstacle in the right lane (between 3.0s and 7.5s)
        if pothole_start_frame <= i <= pothole_end_frame:
            progress = (i - pothole_start_frame) / (pothole_end_frame - pothole_start_frame)
            # Pothole moves closer in perspective (y moves down, size grows)
            py = int(horizon_y + 40 + progress * (height - horizon_y - 120))
            px = int(width * 0.62 + progress * 20)
            
            p_scale = 0.5 + progress * 0.9
            major_axis = int(35 * p_scale)
            minor_axis = int(18 * p_scale)

            # Dark crater cavity
            cv2.ellipse(frame, (px, py), (major_axis, minor_axis), 15, 0, 360, (18, 20, 22), -1)
            # Rough textured jagged edge around crater
            cv2.ellipse(frame, (px, py), (major_axis + 4, minor_axis + 3), 15, 0, 360, (30, 35, 38), 2)
            cv2.ellipse(frame, (px - 4, py - 2), (int(major_axis * 0.6), int(minor_axis * 0.6)), 15, 0, 360, (8, 9, 10), -1)

        # Simulated CCTV on-screen display (OSD) overlay
        cv2.putText(
            frame,
            f"CAM-SRM-SERVICE-LANE-01 | 2026-11-01 {16:02d}:{int(t // 60):02d}:{int(t % 60):02d}.{int((t*10)%10)}",
            (14, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (200, 200, 200),
            1,
            cv2.LINE_AA
        )

        out.write(frame)

    out.release()
    print(f"CCTV sample video created successfully: {output_path}")


if __name__ == "__main__":
    generate_cctv_video()
