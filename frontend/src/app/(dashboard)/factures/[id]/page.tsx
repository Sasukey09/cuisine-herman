import { InvoiceDetail } from "@/features/invoices/invoice-detail";

export default async function InvoiceDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <InvoiceDetail invoiceId={id} />;
}
