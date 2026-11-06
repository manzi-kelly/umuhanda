import "server-only";
import { cache } from "react";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import type { AdminIdentity, AdminSummary } from "./types";

const tokenPattern = /^[A-Za-z0-9_-]{43}$/;
const localHost = (hostname: string) => ["localhost", "127.0.0.1", "[::1]"].includes(hostname);

export function adminConfig() {
  const frontend = new URL(process.env.ADMIN_FRONTEND_ORIGIN ?? "http://localhost:3000");
  const api = new URL(process.env.ADMIN_API_ORIGIN ?? "http://127.0.0.1:8000");
  const local = process.env.NODE_ENV !== "production" || process.env.ADMIN_LOCAL_DEVELOPMENT === "1";
  for (const url of [frontend, api]) {
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.pathname !== "/" || url.search || url.hash) throw new Error("Invalid administrator server configuration.");
  }
  if (local && (!localHost(frontend.hostname) || !localHost(api.hostname))) throw new Error("Local administrator mode requires loopback hosts.");
  if (!local && (frontend.protocol !== "https:" || api.protocol !== "https:")) throw new Error("Administrator production services require HTTPS.");
  return { frontend: frontend.origin, api: api.origin, secure: !local,
    cookieName: local ? "roadrules_admin_ui" : "__Secure-roadrules_admin_ui",
    backendCookie: local ? "roadrules_admin" : "__Secure-roadrules_admin" };
}

export async function adminCredential() {
  const store = await cookies();
  const config = adminConfig();
  const values = store.getAll(config.cookieName);
  return values.length === 1 && tokenPattern.test(values[0].value) ? values[0].value : null;
}

export async function trustedAdminMutation() {
  const origin = (await headers()).get("origin");
  return origin === adminConfig().frontend;
}

export async function adminRequest(path: string, init: RequestInit = {}) {
  const config = adminConfig();
  const credential = await adminCredential();
  return fetch(config.api + path, { ...init, cache: "no-store", redirect: "error",
    signal: init.signal ?? AbortSignal.timeout(10000), headers: {
      ...(new Headers(init.headers).has("X-PDF-Filename") ? { "X-PDF-Filename": new Headers(init.headers).get("X-PDF-Filename")! } : {}),
      "Content-Type": new Headers(init.headers).get("Content-Type") ?? "application/json", Origin: config.frontend, "X-CSRF-Protection": "1",
      ...(credential ? { Cookie: `${config.backendCookie}=${credential}` } : {}),
    } });
}

export function isAdmin(value: unknown): value is AdminIdentity {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return item.role === "ADMIN" && typeof item.id === "string" && typeof item.fullName === "string" && typeof item.email === "string" && typeof item.expiresAt === "string" && Number.isFinite(Date.parse(item.expiresAt));
}

export const requireAdmin = cache(async (): Promise<AdminIdentity> => {
  let credential: string | null = null;
  try { credential = await adminCredential(); } catch { redirect("/admin/login?reason=unavailable"); }
  if (!credential) redirect("/admin/login");
  let admin: unknown;
  let unavailable = false;
  try {
    const response = await adminRequest("/api/v1/admin/auth/me");
    if (response.ok) admin = await response.json();
    else unavailable = response.status !== 401;
  } catch { unavailable = true; }
  if (!isAdmin(admin)) redirect(unavailable ? "/admin/login?reason=unavailable" : "/admin/login");
  return admin;
});

export async function getAdminSummary(): Promise<AdminSummary | null> {
  await requireAdmin();
  let response: Response;
  try {
    response = await adminRequest("/api/v1/admin/dashboard/summary");
  } catch { return null; }
  if (response.status === 401) redirect("/admin/login");
  try {
    if (!response.ok) return null;
    const value = await response.json() as AdminSummary;
    if (!Number.isSafeInteger(value.totalStudents) || value.totalStudents < 0 ||
      [value.totalExamAttempts, value.passedExams, value.failedExams, value.totalVerifiedRevenue, value.activePromoCodes].some(item => item !== null)) return null;
    return value;
  } catch { return null; }
}

export function backendSessionToken(response: Response): string | null {
  const prefix = adminConfig().backendCookie + "=";
  const header = response.headers.getSetCookie().find(value => value.startsWith(prefix));
  const token = header?.slice(prefix.length).split(";")[0];
  return token && tokenPattern.test(token) ? token : null;
}

export async function writeAdminCookie(token: string, expires: string) {
  const config = adminConfig();
  (await cookies()).set(config.cookieName, token, { httpOnly: true, secure: config.secure,
    sameSite: "strict", path: "/admin", expires: new Date(expires) });
}

export async function deleteAdminCookie() {
  const config = adminConfig();
  (await cookies()).set(config.cookieName, "", { httpOnly: true, secure: config.secure,
    sameSite: "strict", path: "/admin", maxAge: 0 });
}


export type BankStatus = {
  ready: boolean;
  activeRevisionId: string | null;
  activeDocumentId: string | null;
  policy: "DIFFICULTY_BALANCED" | "CATEGORY_BALANCED" | "DIFFICULTY_QUOTAS" | "UNSTRATIFIED" | null;
  lastProcessedAt: string | null;
  unavailableEvents: number;
  documents: {
    id: string;
    filename: string;
    processingStatus: string;
    errorCode: string | null;
    bankStatus: string | null;
    counts: Partial<Record<
      "extracted" | "road_sign" | "ELIGIBLE" | "INELIGIBLE_MISSING_ANSWER" |
      "INELIGIBLE_AMBIGUOUS_ANSWER" | "INELIGIBLE_IMAGE_ERROR" | "INELIGIBLE_INCOMPLETE_OPTIONS" | "INELIGIBLE_EXTRACTION_ERROR" | "supported_answers" | "parenthesized_answers" | "green_answers" | "image_only_options", number
    > & {
      category_targets: { ROAD_SIGN: number; GENERAL: number };
      category_available: { ROAD_SIGN: number; GENERAL: number };
      structural_warnings: number;
      blocking_warnings: number;
    }> | null;
  }[];
};

export async function getExamBankStatus(): Promise<BankStatus | null> {
  await requireAdmin();
  try {
    const response = await adminRequest("/api/v1/admin/exam-bank/status");
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}
