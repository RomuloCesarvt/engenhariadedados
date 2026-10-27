/**
 * API Route — Planilha de vendas (Proxy para a Engine Python).
 *
 * POST /api/sales/upload → envia CSV/XLSX (multipart, campo "file")
 * GET  /api/sales/upload → dados da planilha carregada mais recentemente
 */

import { NextRequest, NextResponse } from 'next/server';

const ENGINE_API_URL = process.env.ENGINE_API_URL || 'http://localhost:8001';

export async function POST(request: NextRequest) {
  try {
    const form = await request.formData();
    if (!form.get('file')) {
      return NextResponse.json({ error: 'Nenhum arquivo enviado.' }, { status: 400 });
    }

    const response = await fetch(`${ENGINE_API_URL}/api/sales/upload`, { method: 'POST', body: form });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      return NextResponse.json({ error: data.detail || 'Erro ao carregar a planilha.' }, { status: response.status });
    }
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: `Erro ao conectar com a Engine API: ${error.message}` }, { status: 500 });
  }
}

export async function GET() {
  try {
    const response = await fetch(`${ENGINE_API_URL}/api/sales/upload/latest`, { cache: 'no-store' });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      return NextResponse.json({ error: data.detail || 'Nenhuma planilha carregada.' }, { status: response.status });
    }
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: `Erro ao conectar com a Engine API: ${error.message}` }, { status: 500 });
  }
}
