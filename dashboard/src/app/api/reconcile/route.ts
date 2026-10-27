/**
 * API Route — Reconciliação de Leads (Proxy para Engine Python Cloud).
 *
 * GET  /api/reconcile       → Proxy para GET /api/reports/latest da API Python
 * POST /api/reconcile       → Proxy para POST /api/reconcile da API Python
 */

import { NextRequest, NextResponse } from 'next/server';

const ENGINE_API_URL = process.env.ENGINE_API_URL || 'http://localhost:8001';

export async function GET() {
  try {
    const response = await fetch(`${ENGINE_API_URL}/api/reports/latest`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store', // Always fetch fresh
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || 'Nenhum relatório encontrado na API Python.' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json(
      { error: `Erro ao conectar com a Engine API: ${error.message}` },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json().catch(() => ({}));
    
    // A análise lê 12 meses de leads do CV (~10 mil): leva de 2 a 3 minutos
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 360000);

    const response = await fetch(`${ENGINE_API_URL}/api/reconcile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || 'Erro na execução da Engine API.' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error: any) {
    if (error.name === 'AbortError') {
      return NextResponse.json(
        { error: 'Timeout: a análise demorou mais de 6 minutos. Tente um período menor.' },
        { status: 504 }
      );
    }
    return NextResponse.json(
      { error: `Erro ao conectar com a Engine API: ${error.message}` },
      { status: 500 }
    );
  }
}
