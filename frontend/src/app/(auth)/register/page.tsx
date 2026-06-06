import { GuestGuard } from "@/components/layout/guest-guard";
import { RegisterForm } from "@/features/auth/register-form";

export default function RegisterPage() {
  return (
    <GuestGuard>
      <RegisterForm />
    </GuestGuard>
  );
}
