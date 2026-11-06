import { NextResponse } from "next/server";
import { adminConfig } from "@/features/admin/server";

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

function error(status: number, code: string) {
  return Response.json(
    { error: { code } },
    {
      status,
      headers: { "Cache-Control": "private, no-store" },
    },
  );
}

async function bridge(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const started = performance.now();
  const timeout = AbortSignal.timeout(10_000);
  const path = (await context.params).path.join("/");
  const post = request.method === "POST";
  const put = request.method === "PUT";
  const allowed = post
    ? writes.has(path) || new RegExp(`^exams/${uuid}/next$`).test(path)
    : put
      ? new RegExp(`^exams/${uuid}/answer$`).test(path)
      : reads.test(path);
  if (!allowed) return new Response(null, { status: 404 });
  try {
    const config = adminConfig();
    if ((post || put) && request.headers.get("origin") !== config.frontend)
      return error(403, "ORIGIN_REJECTED");
    if (
      (post || put) &&
      request.headers
        .get("content-type")
        ?.split(";")[0]
        .trim()
        .toLowerCase() !== "application/json"
    )
      return error(415, "VALIDATION_ERROR");
    const backendCookie = config.secure
      ? "__Secure-roadrules_guest"
      : "roadrules_guest";
    const browserCookie = config.secure
      ? "__Secure-roadrules_student_ui"
      : "roadrules_student_ui";
    const tokens = (request.headers.get("cookie") ?? "")
      .split(";")
      .map((part) => part.trim())
      .filter((part) => part.startsWith(browserCookie + "="));
    const credential =
      tokens.length === 1 ? tokens[0].slice(browserCookie.length + 1) : "";
    const headers = new Headers({
      Origin: config.frontend,
      "X-CSRF-Protection": "1",
      "Content-Type": "application/json",
    });
    if (/^[A-Za-z0-9_-]{43}$/.test(credential))
      headers.set("Cookie", backendCookie + "=" + credential);
    let body: string | undefined;
    if (post || put) {
      const reader = request.body?.getReader();
      const decoder = new TextDecoder();
      let size = 0;
      body = "";
      if (reader)
        for (;;) {
          const chunk = await reader.read();
          if (chunk.done) break;
          size += chunk.value.length;
          if (size > 4096) {
            await reader.cancel();
            return new Response(null, { status: 413 });
          }
          body += decoder.decode(chunk.value, { stream: true });
        }
      body += decoder.decode();
    }
    const query = new URLSearchParams();
    if (path === "students/exams/history") {
      const requested = new URL(request.url).searchParams;
      for (const key of ["limit", "offset"]) {
        const value = requested.get(key);
        if (value !== null) query.set(key, value);
      }
    }
    const target = new URL(config.api + "/api/v1/" + path);
    target.search = query.toString();
    const forwarding = performance.now();
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: "error",
      signal: timeout,
    });
    const response = new NextResponse(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: {
        "Content-Type":
          upstream.headers.get("content-type") === "image/png"
            ? "image/png"
            : "application/json",
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
      },
    });
    if (!config.secure) {
      const backend = upstream.headers.get("Server-Timing");
      if (backend) response.headers.set("Server-Timing", backend);
      const done = performance.now();
      response.headers.append(
        "Server-Timing",
        `upstream;dur=${(done - forwarding).toFixed(2)}, bridge;dur=${(done - started).toFixed(2)}`,
      );
    }
    const options = {
      httpOnly: true,
      secure: config.secure,
      sameSite: "lax" as const,
      path: "/student-api",
    };
    if (path === "students/sessions" && upstream.status === 201) {
      const cookie = upstream.headers
        .getSetCookie()
        .find((value) => value.startsWith(backendCookie + "="));
      const value = cookie?.split(";")[0].slice(backendCookie.length + 1);
      const ttl = cookie?.match(/;\s*Max-Age=(\d+)/i)?.[1];
      if (!value || !/^[A-Za-z0-9_-]{43}$/.test(value) || !ttl)
        return new Response(null, { status: 502 });
      response.cookies.set(browserCookie, value, {
        ...options,
        maxAge: Number(ttl),
      });
    } else if (upstream.status === 401) {
      response.cookies.set(browserCookie, "", { ...options, maxAge: 0 });
    }
    return response;
  } catch {
    return timeout.aborted
      ? error(504, "UPSTREAM_TIMEOUT")
      : error(503, "SERVICE_UNAVAILABLE");
  }
}
export const GET = bridge;
export const POST = bridge;

export const PUT = bridge;
