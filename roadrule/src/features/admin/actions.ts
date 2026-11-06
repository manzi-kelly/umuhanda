"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { adminRequest, backendSessionToken, deleteAdminCookie, isAdmin, trustedAdminMutation, writeAdminCookie } from "./server";
import type { AuthState } from "./types";

export async function loginAdmin(_previous: AuthState, form: FormData): Promise<AuthState> {
  try { if (!await trustedAdminMutation()) return { error: "This sign-in request could not be verified. Reload and try again." }; }
  catch { return { error: "Administrator access is not configured. Contact the platform operator." }; }
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  const fields: NonNullable<AuthState["fields"]> = {};
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254) fields.email = "Enter a valid administrator email.";
  if (!password || password.length > 256) fields.password = "Enter your password (up to 256 characters).";
  if (Object.keys(fields).length) return { fields };
  let response: Response;
  try { response = await adminRequest("/api/v1/admin/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }); }
  catch { return { error: "The administrator service is unavailable. Please try again." }; }
  if (response.status === 429) return { error: "Too many sign-in attempts. Please wait and try again." };
  if (response.status === 422) return { fields: { email: "Enter a valid administrator email." } };
  if (response.status === 401) return { error: "Unable to sign in. Check your credentials and try again." };
  if (!response.ok) return { error: "The administrator service is unavailable. Please try again." };
  let identity: unknown;
  try { identity = await response.json(); } catch { return { error: "Sign-in could not be verified." }; }
  const token = backendSessionToken(response);
  if (!isAdmin(identity) || !token) return { error: "Sign-in could not be verified." };
  await writeAdminCookie(token, identity.expiresAt);
  revalidatePath("/admin", "layout");
  redirect("/admin/dashboard");
}

export async function logoutAdmin(_previous: AuthState, _form: FormData): Promise<AuthState> {
  void _previous; void _form;
  try { if (!await trustedAdminMutation()) return { error: "Sign-out request could not be verified." }; }
  catch { return { error: "Administrator access is not configured. Contact the platform operator." }; }
  try {
    const response = await adminRequest("/api/v1/admin/auth/logout", { method: "POST" });
    if (![204, 401].includes(response.status)) return { error: "Sign-out could not be confirmed. Please try again." };
  } catch { return { error: "The service is unavailable. Sign-out could not be confirmed." }; }
  await deleteAdminCookie();
  revalidatePath("/admin", "layout");
  redirect("/admin/login");
}
