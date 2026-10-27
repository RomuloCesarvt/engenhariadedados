import { NextRequest } from 'next/server';
import { proxyGet } from '../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

/** Dados da apresentação de segunda: leads por fonte, origem dos orgânicos, campeões, Google e site. */
export function GET(request: NextRequest) {
  return proxyGet(request, '/api/apresentacao', 120000);
}
