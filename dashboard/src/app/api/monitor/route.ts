/**
 * Next.js API Route — Proxy para o backend Python do Monitor ao Vivo.
 * Faz proxy dos requests SSE e REST para evitar CORS.
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.MONITOR_BACKEND_URL || 'http://localhost:8765';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const action = searchParams.get('action') || 'status';

  try {
    if (action === 'status') {
      const res = await fetch(`${BACKEND_URL}/api/monitor/status`, { cache: 'no-store' });
      const data = await res.json();
      return NextResponse.json(data);
    }

    if (action === 'reset') {
      const res = await fetch(`${BACKEND_URL}/api/monitor/reset`, { cache: 'no-store' });
      const data = await res.json();
      return NextResponse.json(data);
    }

    return NextResponse.json({ error: 'Ação inválida' }, { status: 400 });
  } catch (error) {
    return NextResponse.json(
      { error: 'Não foi possível conectar ao backend do monitor. Verifique se o servidor está rodando na porta 8765.' },
      { status: 503 }
    );
  }
}
