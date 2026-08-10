import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'BI de Leads e Vendas — Mídia online × CV',
  description: 'Leads online, vendas, funil e conferências entre CV, BeeViral, Meta Ads e Google Ads, por empreendimento.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="moura-leite-light antialiased selection:bg-sky-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
