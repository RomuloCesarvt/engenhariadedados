import { NextRequest } from 'next/server';
import { proxyPost } from '../../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

export function POST(request: NextRequest) {
  return proxyPost(request, '/api/diagnosticos/resolver');
}
