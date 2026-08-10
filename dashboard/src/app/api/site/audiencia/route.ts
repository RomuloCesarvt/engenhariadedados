import { NextRequest } from 'next/server';
import { proxyGet } from '../../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

/** Audiência do site no Google Analytics: origem, aparelho, cidade e produto, comparados com o período anterior. */
export function GET(request: NextRequest) {
  return proxyGet(request, '/api/site/audiencia');
}
