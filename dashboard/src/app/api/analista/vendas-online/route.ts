import { NextRequest } from 'next/server';
import { proxyGet, proxyPost } from '../../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

export function GET(request: NextRequest) {
  return proxyGet(request, '/api/analista/vendas-online');
}

export function POST(request: NextRequest) {
  return proxyPost(request, '/api/analista/vendas-online');
}
