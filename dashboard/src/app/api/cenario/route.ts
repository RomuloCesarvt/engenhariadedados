import { NextRequest } from 'next/server';
import { proxyGet } from '../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

/** Por que o CPL mudou: decomposição, teste da eleição e concorrência por praça. */
export function GET(request: NextRequest) {
  return proxyGet(request, '/api/cenario', 120000);
}
