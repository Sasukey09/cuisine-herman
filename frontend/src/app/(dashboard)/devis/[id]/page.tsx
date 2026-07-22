import { QuoteDetail } from "@/features/quotes/quote-detail";

export default async function QuoteDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <QuoteDetail quoteId={id} />;
}
