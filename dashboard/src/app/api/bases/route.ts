import { NextRequest } from 'next/server';
import { proxyGet, proxyPost } from '../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

/** GET  /api/bases → lista as bases salvas e o estado da atualização */
export function GET(request: NextRequest) {
  return proxyGet(request, '/api/bases');
}

/** POST /api/bases → dispara a atualização em segundo plano ({ bases?: string[] }) */
export function POST(request: NextRequest) {
  return proxyPost(request, '/api/bases/atualizar');
}
