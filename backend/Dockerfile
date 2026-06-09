FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Start both the watcher and Flask together via a shell script
CMD ["sh", "-c", "python cowrie_watcher.py & python app.py"]