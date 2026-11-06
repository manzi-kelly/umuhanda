import {
  adminRequest,
  isAdmin,
  trustedAdminMutation,
} from "@/features/admin/server";

const uuid =
  "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}";
const readable = new RegExp(
  `^(pdf-documents(?:/${uuid}(?:/jobs|/pages/[1-9][0-9]{0,3})?)?|pdf-import-jobs/${uuid}|question-drafts(?:/${uuid})?|question-draft-assets/${uuid}|promo-codes(?:/${uuid}/redemptions)?|mock-payments/summary)$`,
);
const postable = new RegExp(
  `^(pdf-documents|pdf-import-jobs/${uuid}/retry|promo-codes|promo-codes/${uuid}/(disable|enable))$`,
);
const patchable = new RegExp(`^promo-codes/${uuid}$`);
const deletable = new RegExp(`^promo-codes/${uuid}$`);
const limit = Number(process.env.PDF_MAX_FILE_BYTES ?? 26214400);
const safeHeaders = {
  "Cache-Control": "private, no-store",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
};
function error(status: number, code: string) {
  return Response.json({ error: { code } }, { status, headers: safeHeaders });
}

async function jsonBody(request: Request) {
  const reader = request.body?.getReader();
  const bytes = new Uint8Array(4096);
  let length = 0;
  if (reader)
    for (;;) {
      const item = await reader.read();
      if (item.done) break;
      if (length + item.value.length > bytes.length) {
        await reader.cancel();
        return null;
      }
      bytes.set(item.value, length);
      length += item.value.length;
    }
  return bytes.buffer.slice(0, length);
}

async function proxy(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const path = (await context.params).path.join("/");
  const method = request.method;
  const mutation = method !== "GET";
  const allowed =
    method === "GET"
      ? readable.test(path)
      : method === "POST"
        ? postable.test(path)
        : method === "PATCH"
          ? patchable.test(path)
          : method === "DELETE"
            ? deletable.test(path)
            : false;
  if (!allowed) return error(404, "NOT_FOUND");
  try {
    if (mutation && !(await trustedAdminMutation()))
      return error(403, "ORIGIN_REJECTED");
    const me = await adminRequest("/api/v1/admin/auth/me");
    if (!me.ok)
      return error(me.status === 401 ? 401 : 503, "ADMIN_AUTH_REQUIRED");
    if (!isAdmin(await me.json())) return error(401, "ADMIN_AUTH_REQUIRED");
    const url = new URL(request.url);
    const query = new URLSearchParams();
    for (const key of ["document_id", "page", "page_size", "offset"]) {
      const value = url.searchParams.get(key);
      if (value !== null) query.set(key, value);
    }
    const pdfUpload = method === "POST" && path === "pdf-documents";
    let body: ArrayBuffer | undefined;
    if (pdfUpload) {
      if (request.headers.get("content-type") !== "application/pdf")
        return error(415, "PDF_CONTENT_TYPE_REQUIRED");
      if (!Number.isSafeInteger(limit) || limit < 1024 || limit > 104857600)
        return error(503, "CONFIGURATION_ERROR");
      if (Number(request.headers.get("content-length")) > limit)
        return error(413, "FILE_SIZE_LIMIT");
      const reader = request.body?.getReader();
      if (!reader) return error(422, "EMPTY_PDF");
      const chunks: Uint8Array[] = [];
      let length = 0;
      for (;;) {
        const item = await reader.read();
        if (item.done) break;
        length += item.value.length;
        if (length > limit) {
          await reader.cancel();
          return error(413, "FILE_SIZE_LIMIT");
        }
        chunks.push(item.value);
      }
      const bytes = new Uint8Array(length);
      let offset = 0;
      for (const chunk of chunks) {
        bytes.set(chunk, offset);
        offset += chunk.length;
      }
      body = bytes.buffer;
    } else if (method === "POST" || method === "PATCH") {
      const parsed = await jsonBody(request);
      if (parsed === null) return error(413, "BODY_LIMIT");
      body = parsed;
    }
    const upstream = await adminRequest(
      `/api/v1/admin/${path}${query.size ? `?${query}` : ""}`,
      {
        method,
        body,
        signal: AbortSignal.timeout(60000),
        headers: {
          "Content-Type": pdfUpload ? "application/pdf" : "application/json",
          ...(pdfUpload
            ? { "X-PDF-Filename": request.headers.get("X-PDF-Filename") ?? "" }
            : {}),
        },
      },
    );
    const content = upstream.headers.get("content-type") ?? "application/json";
    return new Response(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: {
        ...safeHeaders,
        "Content-Type": content,
        ...(upstream.status === 429
          ? { "Retry-After": upstream.headers.get("retry-after") ?? "60" }
          : {}),
      },
    });
  } catch {
    return error(503, "SERVICE_UNAVAILABLE");
  }
}
export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
