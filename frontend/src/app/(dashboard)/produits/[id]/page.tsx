import { PageHeader } from "@/components/page-header";
import { ProductDetail } from "@/features/products/product-detail";

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <>
      <PageHeader title="Fiche produit" description="Historique des prix et comparaison fournisseurs." />
      <ProductDetail productId={id} />
    </>
  );
}
