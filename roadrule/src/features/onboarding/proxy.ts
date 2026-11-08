/**
 * Pure configuration and request policy for the same-origin student API bridge.
 *
 * The bridge is the only implementation that forwards `/student-api/*` to
 * FastAPI. It deliberately keeps the backend guest cookie out of browser
 * JavaScript and translates it to the browser-only UI cookie.
 */

const LOOPBACK_HOSTS = ["localhost", "127.0.0.1", "[::1]"];
const DEFAULT_PRODUCTION_FRONTEND = "https://umuhanda.vercel.app";
const DEFAULT_LOCAL_FRONTEND = "http://localhost:3000";
const DEFAULT_LOCAL_API = "http://127.0.0.1:8000";
const API_PREFIX = "/api/v1";

const uuid = "[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}";
const reads = new RegExp(
  `^(exam-access/me|payments/${uuid}/status|exams/me|students/exams/history|exams/${uuid}/result|exams/${uuid}/current|exams/${uuid}/media/[0-9]{1,2}/[0-9]{1,2})$`,
);
const writes = new Set([
  "students/sessions",
  "payments/mock/initiate",
  "promos/redeem",
  "exams/start",
]);
const nextQuestion = new RegExp(`^exams/${uuid}/next$`);
const answer = new RegExp(`^exams/${uuid}/answer$`);

export type StudentProxyConfig = {
  frontend: string;
  api: string;
  secure: boolean;
  backendCookie: string;
  browserCookie: string;
};

type Environment = Record<string, string | undefined>;

function parseOrigin(value: string, label: string, api: boolean): URL {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`Invalid ${label}.`);
  }
  const pathname = url.pathname.replace(/\/+$/, "");
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    (pathname !== "" && (!api || pathname !== API_PREFIX))
  ) {
    throw new Error(`Invalid ${label}.`);
  }
  return new URL(url.origin);
}

/**
 * Resolve the bridge origins. Production only needs the existing
 * NEXT_PUBLIC_API_URL value. ADMIN_* and STUDENT_* names take precedence so
 * deployments can override either side without changing code.
 */
export function studentProxyConfig(
  env: Environment = process.env,
): StudentProxyConfig {
  const local =
    env.NODE_ENV !== "production" || env.ADMIN_LOCAL_DEVELOPMENT === "1";
  const apiValue =
    env.STUDENT_API_ORIGIN ??
    env.ADMIN_API_ORIGIN ??
    env.NEXT_PUBLIC_API_URL ??
    (local ? DEFAULT_LOCAL_API : "");
  const frontendValue =
    env.STUDENT_FRONTEND_ORIGIN ??
    env.ADMIN_FRONTEND_ORIGIN ??
    env.NEXT_PUBLIC_SITE_URL ??
    (local ? DEFAULT_LOCAL_FRONTEND : DEFAULT_PRODUCTION_FRONTEND);
  if (!apiValue) throw new Error("Student API origin is not configured.");

  const api = parseOrigin(apiValue, "student API origin", true);
  const frontend = parseOrigin(
    frontendValue,
    "student frontend origin",
    false,
  );
  if (
    local &&
    (!LOOPBACK_HOSTS.includes(api.hostname) ||
      !LOOPBACK_HOSTS.includes(frontend.hostname))
  ) {
    throw new Error("Local student mode requires loopback origins.");
  }
  if (!local && (api.protocol !== "https:" || frontend.protocol !== "https:")) {
    throw new Error("Student production services require HTTPS.");
  }

  return {
    frontend: frontend.origin,
    api: api.origin,
    secure: !local,
    backendCookie: local ? "roadrules_guest" : "__Secure-roadrules_guest",
    browserCookie: local
      ? "roadrules_student_ui"
      : "__Secure-roadrules_student_ui",
  };
}

/** Map a browser bridge path to the FastAPI versioned route. */
export function studentUpstreamUrl(
  api: string,
  path: string,
  query: URLSearchParams = new URLSearchParams(),
): URL {
  const target = new URL(`${api}${API_PREFIX}/${path}`);
  target.search = query.toString();
  return target;
}

/**
 * Keep the bridge allowlist explicit. Adding a frontend route must not silently
 * expose arbitrary FastAPI endpoints.
 */
export function studentRequestAllowed(method: string, path: string): boolean {
  if (method === "POST") return writes.has(path) || nextQuestion.test(path);
  if (method === "PUT") return answer.test(path);
  if (method === "GET") return reads.test(path);
  return false;
}
