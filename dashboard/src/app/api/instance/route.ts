import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export function GET() {
  return NextResponse.json({
    appId: 'moura-leite-bi',
    name: 'Moura Leite BI',
    port: 3001,
  });
}
