const socket = io();
const term = new Terminal({
  cursorBlink: true,
  theme: {
    background: '#111827',
    foreground: '#c9d1d9',
    cursor: '#00ff41',
    selectionBackground: '#00ff4133',
  },
  fontSize: 14,
  fontFamily: "'Courier New', monospace",
});

term.open(document.getElementById('terminal'));
term.writeln('Welcome to the AI Honeypot Shell');
term.writeln('Type commands and see AI-generated responses.\n');

let currentLine = '';
term.write('$ ');

term.onData((data) => {
  if (data === '\r') { // Enter key
    const cmd = currentLine.trim();
    term.writeln('');
    if (cmd) {
      addLogEntry(cmd, '...'); // placeholder
      socket.emit('terminal_input', { command: cmd });
    }
    currentLine = '';
    term.write('$ ');
  } else if (data === '\u007f') { // Backspace
    if (currentLine.length > 0) {
      currentLine = currentLine.slice(0, -1);
      term.write('\b \b');
    }
  } else {
    currentLine += data;
    term.write(data);
  }
});

socket.on('terminal_output', (data) => {
  const response = data.response;
  term.writeln(response);
  updateLastLogEntry(response); // update the pending log entry
});

function addLogEntry(command, response) {
  const tbody = document.querySelector('#log-table tbody');
  const row = tbody.insertRow(0);
  const time = new Date().toLocaleTimeString();
  row.innerHTML = `<td>${time}</td><td>${command}</td><td class="ai-response">${response}</td>`;
}

function updateLastLogEntry(response) {
  const rows = document.querySelectorAll('#log-table tbody tr');
  if (rows.length > 0) {
    const lastRow = rows[0];
    lastRow.querySelector('.ai-response').textContent = response;
  }
}