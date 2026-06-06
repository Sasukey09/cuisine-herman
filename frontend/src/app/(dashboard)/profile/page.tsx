import { PageHeader } from "@/components/page-header";
import { ProfileView } from "@/features/auth/profile-view";

export default function ProfilePage() {
  return (
    <>
      <PageHeader title="Profil" description="Gérez les informations de votre compte." />
      <ProfileView />
    </>
  );
}
