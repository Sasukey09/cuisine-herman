import { ReceptionStation } from "@/features/receipts/reception-station";

export default async function ReceptionStationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ReceptionStation orderId={id} />;
}
