"""
FastAPI backend - Hikvision camera frame streaming with minimal latency.
Uses MJPEG streaming for real-time display in the browser.
"""
from dotenv import load_dotenv
load_dotenv()
import cv2
import io
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import os

# Fix FFmpeg threading issue
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|threads;1"

# Configuration
RTSP_URL = os.getenv(
    "RTSP_URL",
    "rtsp://admin:nanjing12345@192.168.1.64:554/Streaming/Channels/101"
)

# Global video capture with thread lock
cap = None
cap_lock = threading.Lock()

def get_capture():
    """Get or create video capture object with thread safety."""
    global cap
    with cap_lock:
        if cap is None or not cap.isOpened():
            if cap is not None:
                cap.release()
            
            cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
            # Set properties for low latency
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FPS, 15)  # Limit FPS if needed
            
            # Give it a moment to initialize
            if not cap.isOpened():
                return None
        return cap

def get_frame():
    """Read a single frame from the camera."""
    capture = get_capture()
    if capture is None:
        return None
    
    with cap_lock:
        ret, frame = capture.read()
        if not ret:
            return None
        return frame

def generate_frames():
    """Generator that yields MJPEG frames for streaming."""
    while True:
        frame = get_frame()
        if frame is None:
            # Reconnect on failure
            global cap
            with cap_lock:
                if cap is not None:
                    cap.release()
                    cap = None
            continue
        
        # Encode as JPEG with quality setting
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
        _, buffer = cv2.imencode(".jpg", frame, encode_param)
        frame_bytes = buffer.tobytes()
        
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize camera on startup, release on shutdown."""
    yield
    global cap
    with cap_lock:
        if cap is not None:
            cap.release()
            cap = None

app = FastAPI(title="Hikvision Camera Stream", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Hikvision Camera Stream API", "stream": "/stream"}

@app.get("/api/stream")
async def video_stream():
    """MJPEG stream endpoint - use in img src for minimal latency display."""
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )