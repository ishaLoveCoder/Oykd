from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
import threading
from bot import run_bot

app = FastAPI(title="OnlyKDrama RSS Bot")


@app.get("/")
def home():
    return JSONResponse({
        "status": "running",
        "message": "OnlyKDrama RSS + Telegram Bot Active"
    })


@app.get("/rss")
def rss_feed():
    return FileResponse(
        "onlykdrama_all.xml",
        media_type="application/rss+xml",
        filename="onlykdrama_all.xml"
    )


# Start bot in background
@app.on_event("startup")
def startup_event():
    thread = threading.Thread(target=run_bot, daemon=True)
    thread.start()
