// Opt-in diagnostic preload: log worker socket errors, never application payloads.
import net from 'node:net';
import { appendFileSync } from 'node:fs';
import { syncBuiltinESMExports } from 'node:module';

const connect = net.createConnection;
net.createConnection = function (...args) {
  const socket = Reflect.apply(connect, this, args);
  socket.once('error', error => {
    appendFileSync(new URL('../docs/evidence/worker-socket-errors.jsonl', import.meta.url),
      JSON.stringify({ pid: process.pid, code: error.code, syscall: error.syscall,
        address: error.address, port: error.port }) + '\n');
  });
  return socket;
};
syncBuiltinESMExports();
