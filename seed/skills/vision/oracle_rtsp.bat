@echo off
title Oracle RTSP Feed
"C:\ffmpeg\bin\ffmpeg.exe" -f dshow -i video="Integrated Camera" -f rtsp -rtsp_transport tcp rtsp://127.0.0.1:8554/live.stream
pause
# Updated at 2025-06-15 10:48:10.517719
# Updated at 2025-06-15 21:03:47.821671