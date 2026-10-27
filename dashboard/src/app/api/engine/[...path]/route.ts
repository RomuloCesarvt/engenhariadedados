/**
 * Proxy para a API Python (projeto Vercel do motor).
 * - Mantém ENGINE_API_KEY no servidor.
 * - Só repassa as rotas conhecidas do motor.
 */

import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const maxDuration = 60; // reconciliação sob demanda consulta várias APIs

const ALLOWED_PATHS = [
  /^health$/,
  /^report\/latest$/,
  /^reconcile$/,
  /^monitor\/(status|tick|reset)$/,
];

async function proxy(request: NextRequest, { params }: { params: { path: string[] } }) {
  const path = params.path.join('/');
  if (!ALLOWED_PATHS.some((pattern) => pattern.test(path))) {
    return NextResponse.json({ detail: 'Rota não encontrada.' }, { status: 404 });
  }

  const engineUrl =
    process.env.ENGINE_URL || (process.env.NODE_ENV !== 'production' ? 'http://localhost:8765' : '');
  if (!engineUrl) {
    return NextResponse.json({ detail: 'ENGINE_URL não está configurada no dashboard.' }, { status: 503 });
  }

  const headers: Record<string, string> = {};
  if (process.env.ENGINE_API_KEY) headers.Authorization = `Bearer ${process.env.ENGINE_API_KEY}`;
  const hasBody = request.method === 'POST';
  if (hasBody) headers['Content-Type'] = 'application/json';

  try {
    const upstream = await fetch(`${engineUrl.replace(/\/$/, '')}/api/${path}${request.nextUrl.search}`, {
      method: request.method,
      headers,
      body: hasBody ? await request.text() : undefined,
      cache: 'no-store',
    });
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: { 'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json' },
    });
  } catch {
    return NextResponse.json(
      { detail: 'Não foi possível conectar ao motor de leads. Verifique ENGINE_URL e se o motor está no ar.' },
      { status: 502 }
    );
  }
}

export const GET = proxy;
export const POST = proxy;
