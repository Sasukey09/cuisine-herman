import { PageHeader } from "@/components/page-header";
import { AdminView } from "@/features/admin/admin-view";

export default function AdministrationPage() {
  return (
    <>
      <PageHeader
        title="Administration"
        description="Gérez les utilisateurs, les rôles et les permissions."
      />
      <AdminView />
    </>
  );
}
