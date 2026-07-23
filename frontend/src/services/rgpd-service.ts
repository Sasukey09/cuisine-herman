import { api } from "@/lib/api";

/** RGPD art. 15/20 — everything the platform holds on the organization, as JSON.
 *  Admin-only (enforced server-side). */
export async function exportOrganizationData(): Promise<unknown> {
  const { data } = await api.get("/rgpd/export");
  return data;
}

/** RGPD art. 17 — irreversible erasure of the whole organization. Requires the
 *  exact organization name and (for password accounts) the current password. */
export async function deleteOrganization(confirmName: string, password: string): Promise<void> {
  await api.post("/rgpd/delete-organization", {
    confirm_name: confirmName,
    password,
  });
}
