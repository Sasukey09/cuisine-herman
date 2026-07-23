import { ReceiptDetail } from "@/features/receipts/receipt-detail";

export default async function ReceptionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ReceiptDetail receiptId={id} />;
}
