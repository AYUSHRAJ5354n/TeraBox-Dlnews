FROM python:3.9-slim

# Install FFmpeg (required by yt-dlp to fix videos)
RUN apt-get update && apt-get install -y ffmpeg libsm6 libxext6 && apt-get clean

WORKDIR /app
COPY . .

# Install requirements
RUN pip install --no-cache-dir -r requirements.txt

# Ensure yt-dlp is up to date
RUN pip install -U yt-dlp

EXPOSE 8080

CMD ["python", "bot.py"]
