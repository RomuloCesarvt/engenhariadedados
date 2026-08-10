/**
 * API Route — Auditoria de Vendas (Proxy para a Engine Python).
 *
 * GET /api/sales-audit → Proxy para GET /api/sales-audit/latest da API Python.
 *
 * O bloco de auditoria também acompanha o relatório completo em /api/reconcile;
 * esta rota existe para consultar apenas o cruzamento Vendas x Leads.
 */

import { NextResponse } from 'next/server';

const ENGINE_API_URL = process.env.ENGINE_API_URL || 'http://localhost:8001';

export async function GET() {
  try {
    const response = await fetch(`${ENGINE_API_URL}/api/sales-audit/latest`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || 'Nenhuma auditoria de vendas encontrada.' },
        { status: response.status }
      );
    }

    return NextResponse.json(await response.json());
  } catch (error: any) {
    return NextResponse.json(
      { error: `Erro ao conectar com a Engine API: ${error.message}` },
      { status: 500 }
    );
  }
}
