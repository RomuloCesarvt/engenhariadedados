/** Repasse das rotas do Next para a engine Python, preservando query string e mensagens de erro. */

import { NextRequest, NextResponse } from 'next/server';

export const ENGINE_API_URL = process.env.ENGINE_API_URL || 'http://localhost:8001';

async function repassar(url: string, init: RequestInit, timeoutMs: number) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...init, cache: 'no-store', signal: controller.signal });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      return NextResponse.json({ error: body.detail || body.error || `Erro ${response.status} na engine.` }, { status: response.status });
    }
    return NextResponse.json(body);
  } catch (error: any) {
    const mensagem =
      error?.name === 'AbortError'
        ? `A engine não respondeu em ${Math.round(timeoutMs / 1000)} segundos.`
        : `Não foi possível conectar à engine (${ENGINE_API_URL}): ${error?.message}`;
    return NextResponse.json({ error: mensagem }, { status: 503 });
  } finally {
    clearTimeout(timer);
  }
}

export function proxyGet(request: NextRequest, path: string, timeoutMs = 60000) {
  return repassar(`${ENGINE_API_URL}${path}${request.nextUrl.search}`, { method: 'GET' }, timeoutMs);
}

export async function proxyPost(request: NextRequest, path: string, timeoutMs = 60000) {
  const body = await request.text();
  return repassar(
    `${ENGINE_API_URL}${path}`,
    { method: 'POST', body: body || '{}', headers: { 'Content-Type': 'application/json' } },
    timeoutMs
  );
}

export function proxyDelete(request: NextRequest, path: string, timeoutMs = 60000) {
  return repassar(`${ENGINE_API_URL}${path}${request.nextUrl.search}`, { method: 'DELETE' }, timeoutMs);
}
