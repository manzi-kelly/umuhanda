export type AccessState = {
  fullName: string;
  phoneNumber: string;
  mockEnabled: boolean;
  accessStatus: "ACTIVE" | "INACTIVE";
  bankReady: boolean;
  bankReason: string | null;
  examReady: boolean;
  reason: string | null;
  entitlements: {
    id: string;
    status: string;
    accessStatus: string;
    source: string;
  }[];
};

export type MockPayment = {
  id: string;
  reference: string;
  provider: "MTN" | "AIRTEL";
  amount: number;
  currency: "RWF";
  status: "PENDING" | "SUCCESSFUL" | "FAILED" | "CANCELLED";
};

export const examUnavailable =
  "Hari ikibazo muri system. Ikizamini ntikiboneka muri uyu mwanya.";

export function examUnavailableReason(reason?: string | null) {
  if (reason === "NO_ACTIVE_BANK")
    return "Banki y’ibibazo y’ikizamini ntabwo yiteguye. Umuyobozi agomba kwemeza PDF y’ibibazo mbere y’uko ikizamini gitangira.";
  if (reason === "UNUSED_POOL_INSUFFICIENT")
    return "Nta bibazo bihagije bisigaye ku kizamini. Umuyobozi agomba kongeramo ibibazo byemewe.";
  return examUnavailable;
}

const messages: Record<string, string> = {
  STALE_QUESTION: "Ikibazo cyarahindutse. Reba ikibazo kiriho.",
  STALE_ANSWER: "Igisubizo cyarahindutse. Ongera urebe ikibazo.",
  EXAM_NOT_FOUND: "Iki kizamini ntikiboneka muri serivisi yawe.",
  EXAM_NOT_COMPLETED: "Ikizamini ntikirarangira.",
  EXAM_RESULT_UNAVAILABLE: "Ibisubizo ntibiboneka ubu. Ongera ugerageze nyuma.",
  EXAM_COMPLETED: "Ikizamini cyarangiye.",
  EXAM_ALREADY_ACTIVE: "Ufite ikizamini kiri gukorwa.",
  ENTITLEMENT_REQUIRED: "Ukeneye uruhushya rwemejwe na seriveri.",
  EXAM_UNAVAILABLE: examUnavailable,
  VALIDATION_ERROR: "Reba amakuru winjije wongere ugerageze.",
  UPSTREAM_TIMEOUT: "Seriveri yatinze gusubiza. Ongera ugerageze.",
  ORIGIN_REJECTED: "Ongera ufungure urupapuro kugira ngo ukomeze.",
  PROMO_INVALID: "Kode ntiyemewe. Reba neza wanditse.",
  PROMO_NOT_PUBLISHED: "Iyi kode ntiyigeze ishyirwa ahagaragara.",
  PROMO_DISABLED: "Iyi kode yahagaritswe n’umuyobozi.",
  PROMO_EXPIRED: "Iyi kode yararangiye. Saba indi kode.",
  PROMO_EXHAUSTED: "Iyi kode yarakoreshejwe ku bushobozi bwayo bwose.",
  PROMO_RATE_LIMITED: "Wagerageje inshuro nyinshi. Tegereza iminota itanu.",
  ACCESS_REQUIRED: "Nta ruhushya rwo gutangira ikizamini ufite.",
  GUEST_SESSION_REQUIRED:
    "Igihe cyo gukoresha serivisi cyarangiye. Subira ku makuru yawe.",
  MOCK_DISABLED: "Uburyo bwo kugerageza ubwishyu ntibufunguye.",
};

export class AccessRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export async function accessRequest<T>(
  path: string,
  body?: object,
  signal?: AbortSignal,
  method?: "PUT",
): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort(signal?.reason);
  if (signal?.aborted) abort();
  else signal?.addEventListener("abort", abort, { once: true });
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, 12_000);
  let response: Response | undefined;
  let data: { error?: { code?: string } } | null;
  try {
    response = await fetch("/student-api/" + path, {
      method: method ?? (body ? "POST" : "GET"),
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
      signal: controller.signal,
    });
    data = await response.json();
  } catch {
    if (timedOut) throw new AccessRequestError(messages.UPSTREAM_TIMEOUT, 504);
    if (signal?.aborted) throw signal.reason;
    if (response && !response.ok) {
      throw new AccessRequestError(
        response.status === 403
          ? messages.ORIGIN_REJECTED
          : "Serivisi ntibashije gusubiza. Ongera ugerageze.",
        response.status,
      );
    }
    throw new Error(
      "Ntitwabashije kuvugana na seriveri. Reba interineti wongere ugerageze.",
    );
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
  if (!response.ok) {
    throw new AccessRequestError(
      messages[data?.error?.code ?? ""] ??
        (response.status === 401
          ? messages.GUEST_SESSION_REQUIRED
          : "Serivisi ntibashije gusubiza. Ongera ugerageze."),
      response.status,
    );
  }
  return data as T;
}
