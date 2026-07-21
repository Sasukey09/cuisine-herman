import { Suspense } from "react";

import { GuestGuard } from "@/components/layout/guest-guard";
import { ResetPasswordForm } from "@/features/auth/reset-password-form";

export default function ResetPasswordPage() {
  return (
    <GuestGuard>
      {/* useSearchParams (token in the URL) must sit under a Suspense boundary. */}
      <Suspense fallback={null}>
        <ResetPasswordForm />
      </Suspense>
    </GuestGuard>
  );
}
