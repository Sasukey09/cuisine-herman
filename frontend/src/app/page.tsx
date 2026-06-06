import { redirect } from "next/navigation";

export default function HomePage() {
  // The dashboard layout bounces unauthenticated users to /login.
  redirect("/dashboard");
}
