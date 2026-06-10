import os
import time
import asyncio
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

# --- KOYEB TCP HEALTH CHECK ---
app_health = Flask(__name__)
@app_health.route('/')
def health(): return "Bot is Alive", 200

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    app_health.run(host='0.0.0.0', port=port)

# --- BOT CLIENT ---
bot = Client("terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ **Bot Ready (yt-dlp mode).**\nSend a Terabox link. I will wait for the API and then leech the file.")

@bot.on_message(filters.text & ~filters.command(["start"]))
async def handle_link(client, message: Message):
    url = message.text
    if "terabox" not in url and "1024tera" not in url:
        return

    status = await message.reply_text("🔎 **Analyzing link...**")
    direct_stream_url = f"{API_BASE_URL}{url}"
    
    # yt-dlp specific filename template
    file_template = f"video_{int(time.time())}.%(ext)s"
    output_file = ""

    try:
        # --- SMART WAIT LOGIC ---
        start_time = time.time()
        max_wait = 5 * 60 
        ready = False

        while time.time() - start_time < max_wait:
            # We use yt-dlp --get-url to check if the link is ready
            check = subprocess.run(['yt-dlp', '--get-url', direct_stream_url], capture_output=True, text=True)
            if check.returncode == 0:
                ready = True
                break
            
            remaining = max_wait - int(time.time() - start_time)
            await status.edit(f"⏳ **Waiting for API to generate file...**\n`{remaining // 60}m {remaining % 60}s` left.")
            await asyncio.sleep(15)

        if not ready:
            await status.edit("❌ **API Timeout.** The link didn't respond in time.")
            return

        # --- DOWNLOAD USING YT-DLP ---
        await status.edit("🚀 **Link Ready! Leeching...**")
        
        # yt-dlp command to download and auto-fix the video
        cmd = [
            'yt-dlp',
            '-o', file_template,
            '--no-playlist',
            '--merge-output-format', 'mp4',
            direct_stream_url
        ]
        
        subprocess.run(cmd, check=True)

        # Find the downloaded file (since extension might vary like .mp4 or .mkv)
        files = [f for f in os.listdir('.') if f.startswith(f"video_{int(start_time)}")]
        if not files:
            await status.edit("❌ **Download failed.** yt-dlp could not save the file.")
            return
        
        output_file = files[0]

        # --- UPLOADING ---
        await status.edit("📤 **Leeching to Telegram...**")
        await message.reply_video(
            video=output_file,
            caption="✅ **Leeched Successfully!**",
            supports_streaming=True,
            progress=progress,
            progress_args=(status, "Uploading")
        )
        await status.delete()

    except Exception as e:
        await status.edit(f"⚠️ **Leech Error:** `{str(e)}`")
    finally:
        if output_file and os.path.exists(output_file):
            os.remove(output_file)

async def progress(current, total, status_msg, type_msg):
    try:
        if current % (total // 5) == 0:
            await status_msg.edit(f"{type_msg}: **{current * 100 / total:.1f}%**")
    except: pass

if __name__ == "__main__":
    Thread(target=run_health_server, daemon=True).start()
    bot.run()
