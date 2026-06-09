import requests, json, csv, os

url = "https://raw.githubusercontent.com/praetorian-inc/cowrie-log-data/master/data/cowrie.json.2023-01-01"
print("Downloading Cowrie log...")
response = requests.get(url, stream=True)
response.raise_for_status()

# Parse JSON lines, group by session
sessions = {}
for line in response.iter_lines():
    try:
        event = json.loads(line)
    except:
        continue
    sess = event.get('session')
    if not sess:
        continue
    if sess not in sessions:
        sessions[sess] = []
    sessions[sess].append(event)

pairs = []
for sess_id, events in sessions.items():
    events.sort(key=lambda x: x.get('timestamp', ''))
    input_cmd = None
    for ev in events:
        eid = ev.get('eventid')
        if eid == 'cowrie.command.input':
            input_cmd = ev.get('input', '').strip()
        elif eid in ('cowrie.command.success', 'cowrie.command.failed') and input_cmd:
            output = ev.get('message', '') or ''
            pairs.append((input_cmd, output))
            input_cmd = None

# Save as training_data.txt with special tokens
with open("training_data.txt", "w", encoding="utf-8") as f:
    for cmd, resp in pairs:
        resp = resp.strip()[:400]  # truncate
        f.write(f"<|attacker|> {cmd}\n<|system|> {resp}\n<|endoftext|>\n")

print(f"✅ Created training_data.txt with {len(pairs)} examples.")