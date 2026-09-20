# Fie: hud_server.py
# Path: C:\SEED_ROOT\seed\ui\hud_server.py
#
#
# ========================================================================

import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import uvicorn
from collections import deque
import json

app = FastAPI()
clients = set()

# Internal storage for HUD
waveform_points = deque(maxlen=512)
fft_points = deque(maxlen=512)
waveform_peak = 0
fft_peak = 0

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await asyncio.sleep(0.05)
    finally:
        clients.remove(ws)

async def push_waveform(waveform: deque, fft: deque, w_peak: float, f_peak: float):
    global waveform_points, fft_points, waveform_peak, fft_peak
    waveform_points.clear()
    waveform_points.extend(list(waveform))
    fft_points.clear()
    fft_points.extend(list(fft))
    waveform_peak = w_peak
    fft_peak = f_peak

    if clients:
        msg = json.dumps({
            "waveform": list(waveform_points),
            "fft": list(fft_points),
            "waveform_peak": waveform_peak,
            "fft_peak": fft_peak
        })
        await asyncio.gather(*[client.send_text(msg) for client in clients])

@app.get("/")
async def get():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SEED HUD Waveform + FFT</title>
        <style>
            body { margin: 0; background: #111; }
            canvas { display: block; width: 100vw; height: 250px; background: #111; }
        </style>
    </head>
    <body>
        <canvas id="waveform"></canvas>
        <canvas id="fft"></canvas>
        <script>
            const canvasW = document.getElementById('waveform');
            const ctxW = canvasW.getContext('2d');
            canvasW.width = window.innerWidth;
            canvasW.height = 200;

            const canvasF = document.getElementById('fft');
            const ctxF = canvasF.getContext('2d');
            canvasF.width = window.innerWidth;
            canvasF.height = 200;

            const ws = new WebSocket('ws://localhost:8000/ws');
            let waveform = [], fft = [], waveform_peak = 1, fft_peak = 1;

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                waveform = data.waveform;
                fft = data.fft;
                waveform_peak = data.waveform_peak || 1;
                fft_peak = data.fft_peak || 1;
            };

            function draw(){
                // Waveform
                ctxW.fillStyle = '#111';
                ctxW.fillRect(0,0,canvasW.width,canvasW.height);
                ctxW.strokeStyle = '#0f0';
                ctxW.lineWidth = 2;
                ctxW.beginPath();
                for(let i=0; i<waveform.length; i++){
                    const x = i*(canvasW.width/waveform.length);
                    const y = canvasW.height - ((waveform[i]/waveform_peak)*canvasW.height);
                    if(i===0) ctxW.moveTo(x,y); else ctxW.lineTo(x,y);
                }
                ctxW.stroke();

                // Peak marker
                ctxW.strokeStyle = '#ff0';
                const peak_y = canvasW.height - canvasW.height;
                ctxW.beginPath();
                ctxW.moveTo(0, 0);
                ctxW.lineTo(canvasW.width, 0);
                ctxW.stroke();

                // FFT
                ctxF.fillStyle = '#111';
                ctxF.fillRect(0,0,canvasF.width,canvasF.height);
                ctxF.fillStyle = '#f00';
                for(let i=0; i<fft.length; i++){
                    const x = i*(canvasF.width/fft.length);
                    const y = (fft[i]/fft_peak)*canvasF.height;
                    ctxF.fillRect(x, canvasF.height - y, canvasF.width/fft.length, y);
                }

                requestAnimationFrame(draw);
            }

            draw();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)

def run_hud():
    uvicorn.run(app, host="0.0.0.0", port=8000)
