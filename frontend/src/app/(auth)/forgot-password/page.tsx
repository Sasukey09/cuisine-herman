import { GuestGuard } from "@/components/layout/guest-guard";
import { ForgotPasswordForm } from "@/features/auth/forgot-password-form";

export default function ForgotPasswordPage() {
  return (
    <GuestGuard>
      <ForgotPasswordForm />
    </GuestGuard>
  );
}
