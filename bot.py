import os
import time
import asyncio
import requests
import subprocess
from flask import Flask
from threading import Thread
from pyrogram import Client, filters
from pyrogram.types import Message

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API_BASE_URL = "https://terabox-api.mn-bots.workers.dev/download?url="

# Headers to mimic a real browser (Crucial for Terabox)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Referer": "https://www.terabox.com/"
}

# --- KOYEB TCP HEALTH CHECK ---
app_health = Flask(__name__)
@app_health.route('/')
def health(): return "Bot is Alive", 200

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    app_health.run(host='0.0.0.0', port=port)

# --- BOT CLIENT ---
bot = Client("terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def check_link(url):
    """Checks if the API link is ready using browser headers"""
    try:
        response = requests.head(url, headers=HEADERS, timeout=10)
        return response.status_code == 200 or response.status_code == 302
    except:
        return False

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ **Bot Ready.**\nSend a Terabox link. I will start the download as soon as the API link is live.")

@bot.on_message(filters.text & ~filters.command(["start"]))
async def handle_link(client, message: Message):
    url = message.text
    if "terabox" not in url and "1024tera" not in url:
        return

    status = await message.reply_text("🔎 **Link detected.** Testing link status...")
    file_name = f"video_{int(time.time())}.mp4"
    direct_stream_url = f"{API_BASE_URL}{url}"

    try:
        # --- SMART WAIT LOGIC ---
        start_time = time.time()
        max_wait = 5 * 60 
        link_ready = False

        while time.time() - start_time < max_wait:
            if check_link(direct_stream_url):
                link_ready = True
                break
            
            elapsed = int(time.time() - start_time)
            remaining = max_wait - elapsed
            await status.edit(f"⏳ **Link not ready yet.**\nPolling... `{remaining // 60}m {remaining % 60}s` left.")
            await asyncio.sleep(10)

        if not link_ready:
            await status.edit("❌ **Timeout:** Link didn't become active. API might be overloaded.")
            return

        # --- FFMPEG PROCESSING WITH HEADERS ---
        await status.edit("🚀 **Link Active! Initializing FFmpeg...**")
        
        # We pass headers to FFmpeg so the server doesn't block it
        cmd = [
            'ffmpeg',
            '-headers', f"User-Agent: {HEADERS['User-Agent']}\r\nReferer: {HEADERS['Referer']}\r\n",
            '-i', direct_stream_url,
            '-c', 'copy', 
            '-bsf:a', 'aac_adtstoasc',
            file_name, '-y'
        ]
        
        process = subprocess.run(cmd, capture_output=True, text=True)

        if not os.path.exists(file_name) or os.path.getsize(file_name) == 0:
            # Capturing the last 200 characters of the error log for debugging
            error_log = process.stderr[-200:] if process.stderr else "No error log available"
            await status.edit(f"❌ **FFmpeg Failed.**\nReason: `{error_log}`")
            return

        # --- UPLOADING ---
        await status.edit("📤 **Uploading...**")
        await message.reply_video(
            video=file_name,
            caption="✅ **Downloaded successfully!**",
            supports_streaming=True,
            progress=progress,
            progress_args=(status, "Uploading")
        )
        await status.delete()

    except Exception as e:
        await status.edit(f"⚠️ **Error:** `{str(e)}`")
    finally:
        if os.path.exists(file_name):
            os.remove(file_name)

async def progress(current, total, status_msg, type_msg):
    try:
        if current % (total // 5) == 0:
            await status_msg.edit(f"{type_msg}: **{current * 100 / total:.1f}%**")
    except: pass

if __name__ == "__main__":
    Thread(target=run_health_server, daemon=True).start()
    bot.run()
