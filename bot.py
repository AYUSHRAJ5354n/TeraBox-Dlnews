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

# --- KOYEB HEALTH CHECK ---
app_health = Flask(__name__)
@app_health.route('/')
def health(): return "Bot is Alive", 200

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    app_health.run(host='0.0.0.0', port=port)

# --- BOT CLIENT ---
bot = Client("terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def check_link(url):
    """Checks if the API link is ready to stream"""
    try:
        # We use stream=True and a short timeout to check if the link is active 
        # without downloading the whole file yet.
        response = requests.get(url, stream=True, timeout=10)
        return response.status_code == 200
    except:
        return False

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ **Bot Ready.**\nSend a Terabox link. I will monitor the link and start downloading as soon as it's active (Max wait 5 mins).")

@bot.on_message(filters.text & ~filters.command(["start"]))
async def handle_link(client, message: Message):
    url = message.text
    if "terabox" not in url and "1024tera" not in url:
        return

    status = await message.reply_text("🔎 **Link detected.** Checking status...")
    file_name = f"video_{int(time.time())}.mp4"
    direct_stream_url = f"{API_BASE_URL}{url}"

    try:
        # --- SMART WAIT LOGIC ---
        start_time = time.time()
        max_wait = 5 * 60  # 5 minutes
        link_ready = False

        while time.time() - start_time < max_wait:
            elapsed = int(time.time() - start_time)
            remaining = max_wait - elapsed
            
            if check_link(direct_stream_url):
                link_ready = True
                break
            
            await status.edit(f"⏳ **Link not ready yet.**\nPolling API... `{remaining // 60}m {remaining % 60}s` left.\n(Will start immediately when found)")
            await asyncio.sleep(10)

        if not link_ready:
            await status.edit("❌ **Timeout:** API did not become ready within 5 minutes. Try again later.")
            return

        # --- FFMPEG PROCESSING ---
        await status.edit("🚀 **Link Found! Starting Download & Conversion...**")
        
        cmd = [
            'ffmpeg', '-i', direct_stream_url,
            '-c', 'copy', '-bsf:a', 'aac_adtstoasc',
            file_name, '-y'
        ]
        
        # Run FFmpeg in a sub-process
        process = subprocess.run(cmd, capture_output=True, text=True)

        if not os.path.exists(file_name) or os.path.getsize(file_name) == 0:
            await status.edit("❌ **FFmpeg Error:** Could not capture the stream. The link might have died.")
            return

        # --- UPLOADING ---
        await status.edit("📤 **Uploading to Telegram...**")
        await message.reply_video(
            video=file_name,
            caption="✅ **Successfully Processed!**",
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
    print("Bot is running...")
    bot.run()
