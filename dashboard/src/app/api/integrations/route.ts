/**
 * API Route — Estado das integrações (Proxy para a Engine Python).
 *
 * GET /api/integrations            → estado registrado na última análise
 * GET /api/integrations?live=true  → consulta cada API agora
 */

import { NextRequest, NextResponse } from 'next/server';

const ENGINE_API_URL = process.env.ENGINE_API_URL || 'http://localhost:8001';

export async function GET(request: NextRequest) {
  const live = request.nextUrl.searchParams.get('live') === 'true';
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120000);

  try {
    const response = await fetch(`${ENGINE_API_URL}/api/integrations?live=${live}`, {
      cache: 'no-store',
      signal: controller.signal,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      return NextResponse.json(
        { error: data.detail || 'Erro ao verificar integrações.' },
        { status: response.status }
      );
    }
    return NextResponse.json(data);
  } catch (error: any) {
    const message =
      error.name === 'AbortError'
        ? 'Timeout: a verificação das integrações demorou mais de 2 minutos.'
        : `Erro ao conectar com a Engine API: ${error.message}`;
    return NextResponse.json({ error: message }, { status: 504 });
  } finally {
    clearTimeout(timeoutId);
  }
}
