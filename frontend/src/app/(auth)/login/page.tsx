import { GuestGuard } from "@/components/layout/guest-guard";
import { LoginForm } from "@/features/auth/login-form";

export default function LoginPage() {
  return (
    <GuestGuard>
      <LoginForm />
    </GuestGuard>
  );
}
