import React, { useEffect, useRef, useState } from 'react';
import { Terminal as XTerm } from 'xterm';
import { FitAddon } from '@xterm/addon-fit';
import 'xterm/css/xterm.css';

const SESSION_ID = 'host_' + Math.random().toString(36).slice(2, 10);
const PROMPT = '\x1b[35mPS AegisLab\x1b[0m> ';

const TerminalComponent = ({ socket }) => {
  const containerRef = useRef(null);
  const termRef = useRef(null);
  const fitRef = useRef(null);
  const lineRef = useRef('');
  const [connected, setConnected] = useState(false);

  const writePrompt = () => {
    termRef.current?.write(PROMPT);
  };

  const printBanner = (term) => {
    term.clear();
    term.writeln('\x1b[36mAegis Lab PowerShell\x1b[0m');
    term.writeln('Run your project from this single console. Try: project status, start project, npm run build');
    term.writeln('');
    writePrompt();
  };

  useEffect(() => {
    const term = new XTerm({
      cursorBlink: true,
      scrollback: 3000,
      fontSize: 14,
      fontFamily: "'Cascadia Mono', 'Courier New', monospace",
      theme: {
        background: '#080b12',
        foreground: '#d8e2ef',
        cursor: '#8b5cf6',
        selectionBackground: '#8b5cf633',
        black: '#111827',
        brightBlack: '#6b7280',
        green: '#2dd4bf',
        brightGreen: '#2dd4bf',
        yellow: '#f59e0b',
        red: '#fb7185',
        cyan: '#38bdf8',
        magenta: '#a78bfa',
      },
    });

    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);
    fit.fit();

    termRef.current = term;
    fitRef.current = fit;

    printBanner(term);

    term.onData((data) => {
      const code = data.charCodeAt(0);

      if (data === '\r') {
        const cmd = lineRef.current.trim();
        term.writeln('');
        if (cmd) {
          if (cmd === 'clear') {
            printBanner(term);
          } else {
            socket.emit('host_terminal_input', { command: cmd, session_id: SESSION_ID });
          }
        } else {
          writePrompt();
        }
        lineRef.current = '';
        return;
      }

      if (data === '\u007f') {
        if (lineRef.current.length > 0) {
          lineRef.current = lineRef.current.slice(0, -1);
          term.write('\b \b');
        }
        return;
      }

      if (data === '\u0003') {
        term.writeln('^C');
        lineRef.current = '';
        writePrompt();
        return;
      }

      if (data === '\u000c') {
        printBanner(term);
        lineRef.current = '';
        return;
      }

      if (code >= 32) {
        lineRef.current += data;
        term.write(data);
      }
    });

    const onConnect = () => setConnected(true);
    const onDisconnect = () => setConnected(false);
    const onHostOutput = (data) => {
      if (!termRef.current) return;
      if (data.error) {
        termRef.current.writeln(`\x1b[31m${data.error}\x1b[0m`);
      }
      if (data.output) {
        data.output.split('\n').forEach((line) => termRef.current.writeln(line.replace(/\r$/, '')));
      }
      if (data.cwd) {
        termRef.current.writeln(`\x1b[90m${data.cwd}\x1b[0m`);
      }
      writePrompt();
    };

    socket.on('connect', onConnect);
    socket.on('disconnect', onDisconnect);
    socket.on('host_terminal_output', onHostOutput);
    setConnected(socket.connected);

    const ro = new ResizeObserver(() => {
      try {
        fitRef.current?.fit();
      } catch (_) {}
    });
    if (containerRef.current) ro.observe(containerRef.current);

    return () => {
      socket.off('connect', onConnect);
      socket.off('disconnect', onDisconnect);
      socket.off('host_terminal_output', onHostOutput);
      ro.disconnect();
      term.dispose();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="terminal-wrapper">
      <div className="terminal-header">
        <div className="terminal-title">
          <span />
          <span />
          <span />
          <strong>PowerShell</strong>
        </div>
        <span className={`connection-badge ${connected ? '' : 'offline'}`}>
          {connected ? 'Connected' : 'Disconnected'}
        </span>
      </div>
      <div ref={containerRef} className="terminal-screen" />
    </div>
  );
};

export default TerminalComponent;
