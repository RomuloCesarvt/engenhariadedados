import { engineFetch } from '../../../../../lib/engineFetch';
import { NextRequest, NextResponse } from 'next/server';
import { ENGINE_API_URL } from '../../../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

/** A planilha vem como arquivo, não como JSON: o proxy comum não serve. */
export async function GET(request: NextRequest) {
  const url = `${ENGINE_API_URL}/api/analista/vendas-online/relatorio${request.nextUrl.search}`;
  try {
    const resposta = await engineFetch(url, { cache: 'no-store' });
    if (!resposta.ok) {
      const corpo = await resposta.json().catch(() => ({}));
      return NextResponse.json({ error: corpo.detail || `Erro ${resposta.status} na engine.` }, { status: resposta.status });
    }
    return new NextResponse(resposta.body, {
      headers: {
        'Content-Type': resposta.headers.get('content-type') || 'application/octet-stream',
        'Content-Disposition': resposta.headers.get('content-disposition') || 'attachment',
      },
    });
  } catch (error: any) {
    return NextResponse.json({ error: `Não foi possível conectar à engine: ${error?.message}` }, { status: 503 });
  }
}
