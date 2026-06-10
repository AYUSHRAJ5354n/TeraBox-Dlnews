FROM python:3.9-slim

# Install FFmpeg and system tools
RUN apt-get update && apt-get install -y ffmpeg libsm6 libxext6 && apt-get clean

WORKDIR /app
COPY . .

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt

# Koyeb default port
EXPOSE 8080

CMD ["python", "bot.py"]
