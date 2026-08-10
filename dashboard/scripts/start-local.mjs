import net from 'node:net';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const APP_ID = 'moura-leite-bi';
const HOST = '127.0.0.1';
const PORT = Number(process.env.BI_PORT || 3001);
const command = process.argv[2] || 'dev';
const dashboardDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

async function readIdentity() {
  try {
    const response = await fetch(`http://${HOST}:${PORT}/api/instance`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(1500),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

function isPortOpen() {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: HOST, port: PORT });
    socket.setTimeout(1000);
    socket.once('connect', () => {
      socket.destroy();
      resolve(true);
    });
    const closed = () => {
      socket.destroy();
      resolve(false);
    };
    socket.once('timeout', closed);
    socket.once('error', closed);
  });
}

const identity = await readIdentity();

if (command === 'status') {
  if (identity?.appId === APP_ID) {
    console.log(`Moura Leite BI ativo em http://${HOST}:${PORT}`);
    process.exit(0);
  }
  if (await isPortOpen()) {
    console.error(`A porta ${PORT} esta ocupada por outro sistema.`);
    process.exit(2);
  }
  console.log(`Moura Leite BI parado. Porta ${PORT} livre.`);
  process.exit(1);
}

if (identity?.appId === APP_ID) {
  console.log(`Moura Leite BI ja esta ativo em http://${HOST}:${PORT}`);
  process.exit(0);
}

if (await isPortOpen()) {
  console.error(`A porta ${PORT} esta ocupada por outro sistema. O BI nao sera iniciado em outra porta.`);
  console.error(`Feche o processo que usa a porta ${PORT} e execute o comando novamente.`);
  process.exit(2);
}

if (!['dev', 'start'].includes(command)) {
  console.error(`Comando desconhecido: ${command}`);
  process.exit(1);
}

const nextBin = path.join(dashboardDir, 'node_modules', 'next', 'dist', 'bin', 'next');
const child = spawn(process.execPath, [nextBin, command, '-H', HOST, '-p', String(PORT)], {
  cwd: dashboardDir,
  env: { ...process.env, PORT: String(PORT) },
  stdio: 'inherit',
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => child.kill(signal));
}

child.on('exit', (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  process.exit(code ?? 1);
});
