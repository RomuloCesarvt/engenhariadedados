import { NextRequest } from 'next/server';
import { proxyGet } from '../../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

export function GET(request: NextRequest) {
  return proxyGet(request, '/api/vendas/auditoria');
}
