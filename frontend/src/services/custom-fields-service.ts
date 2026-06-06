import { api } from "@/lib/api";
import type { CustomFieldDef, CustomFieldValues } from "./types";

export async function listFields(target?: string): Promise<CustomFieldDef[]> {
  const { data } = await api.get<CustomFieldDef[]>("/custom-fields/", {
    params: target ? { target } : {},
  });
  return data;
}

export async function createField(payload: {
  label: string;
  target: string;
  type: string;
  options?: string[];
  required?: boolean;
  description?: string;
}): Promise<CustomFieldDef> {
  const { data } = await api.post<CustomFieldDef>("/custom-fields/", payload);
  return data;
}

export async function deleteField(id: string): Promise<void> {
  await api.delete(`/custom-fields/${id}`);
}

export async function getEntityValues(
  target: string,
  entityId: string,
): Promise<CustomFieldValues> {
  const { data } = await api.get<CustomFieldValues>(
    `/custom-fields/values/${target}/${entityId}`,
  );
  return data;
}

export async function setEntityValues(
  target: string,
  entityId: string,
  values: Record<string, unknown>,
): Promise<{ values: Record<string, unknown> }> {
  const { data } = await api.put(`/custom-fields/values/${target}/${entityId}`, {
    values,
  });
  return data;
}
