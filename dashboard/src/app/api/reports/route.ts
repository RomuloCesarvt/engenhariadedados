/**
 * API Route — Histórico de Relatórios (Proxy para Engine Python Cloud).
 *
 * GET /api/reports → Proxy para GET /api/reports da API Python
 */

import { NextResponse } from 'next/server';

const ENGINE_API_URL = process.env.ENGINE_API_URL || 'http://localhost:8001';

export async function GET() {
  try {
    const response = await fetch(`${ENGINE_API_URL}/api/reports`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || 'Erro ao buscar histórico na API Python.' },
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
