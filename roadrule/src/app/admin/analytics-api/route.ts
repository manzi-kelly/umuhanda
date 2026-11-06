import { adminRequest } from "@/features/admin/server";

export async function GET(request: Request) {
  const period = new URL(request.url).searchParams.get("period") ?? "weekly";
  if (!["daily", "weekly", "monthly", "yearly"].includes(period)) {
    return new Response(null, { status: 422 });
  }
  const headers = { "Cache-Control": "private, no-store" };
  try {
    const upstream = await adminRequest(
      `/api/v1/admin/analytics/overview?period=${period}`,
    );
    if (!upstream.ok)
      return new Response(null, { status: upstream.status, headers });
    return Response.json(await upstream.json(), { headers });
  } catch {
    return new Response(null, { status: 503, headers });
  }
}
