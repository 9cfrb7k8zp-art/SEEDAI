@echo off
title Oracle Vision Startup



echo [Oracle] Checking OpenCV installation...
python -c "import cv2; print('✅ OpenCV working.')"

echo [Oracle] Starting WyzeBridge via Docker...
docker run -d --name wyze-bridge ^
--restart unless-stopped ^
-e WYZE_EMAIL="c-clarke@hotmail.com" ^
-e WYZE_PASSWORD="Connect$11" ^
-p 1935:1935 ^
-p 8554:8554 ^
-p 8888:8888 ^
mrlt8/wyze-bridge

echo [Oracle] Launching Oracle Vision system...
python "C:\AFM\QOS\scripts\oracle_vision.py"

@echo off
cd /d %~dp0spartan_core\hud
python C:\AFM\QOS\scripts\hud_init.py

@echo off
cd /d %~dp0spartan_core\hud
start python hud_init.py
cd ..\audio
start python spartan_listener.py
cd ..\systems
python sensor_matrix.py
pause
# Updated at 2025-06-15 10:48:10.650604
# Updated at 2025-06-15 21:03:48.123277