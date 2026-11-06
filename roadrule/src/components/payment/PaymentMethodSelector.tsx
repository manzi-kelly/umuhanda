"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { normalizeRwandaPhone } from "@/lib/phone";
import {
  AccessRequestError,
  accessRequest,
  examUnavailableReason,
  type AccessState,
  type MockPayment,
} from "@/features/onboarding/access-client";

const methods = {
  MTN: "MTN Mobile Money",
  AIRTEL: "Airtel Money",
  PROMO: "Kode ya promo",
} as const;
type Provider = MockPayment["provider"];
type Method = keyof typeof methods;

export default function PaymentMethodSelector({
  access,
  onEdit,
  retake = false,
}: {
  access: AccessState;
  onEdit?: () => void;
  retake?: boolean;
}) {
  const router = useRouter();
  const [state, setState] = useState(access);
  const [method, setMethod] = useState<Method>("PROMO");
  const [phone, setPhone] = useState(access.phoneNumber);
  const [payments, setPayments] = useState<
    Partial<Record<Provider, MockPayment>>
  >({});
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const keys = useRef<Partial<Record<Provider, string>>>({});
  const payment = method === "PROMO" ? undefined : payments[method];
  const hasAccess = state.entitlements.some(
    (item) => item.status === "AVAILABLE",
  );

  async function run(action: () => Promise<void>) {
    if (pending.current) return;
    pending.current = true;
    setError("");
    setBusy(true);
    try {
      await action();
    } catch (failure) {
      if (failure instanceof AccessRequestError && failure.status === 401) {
        setState((previous) => ({
          ...previous,
          accessStatus: "INACTIVE",
          examReady: false,
          entitlements: [],
        }));
      }
      setError(
        failure instanceof Error ? failure.message : "Ongera ugerageze.",
      );
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  async function refreshAccess() {
    setState(await accessRequest<AccessState>("exam-access/me"));
  }

  return (
    <div className="space-y-5" aria-busy={busy}>
      <p className="font-semibold">{state.fullName}</p>
      {hasAccess ? (
        <section className="space-y-3 rounded-2xl border border-brand-200 bg-accent-50 p-4">
          <p role="status" className="font-semibold">
            Ufite uruhushya rwemejwe na seriveri.
          </p>
          <p role="status" className="text-sm leading-6">
            {state.bankReady
              ? "Ikizamini kiriteguye. Komeza ku rupapuro rw’ikizamini kugira ngo utangire."
              : examUnavailableReason(state.bankReason)}
          </p>
          <Link
            className="form-button inline-block"
            href={retake ? "/exam?retake=1" : "/exam"}
          >
            Komeza ku kwitegura ikizamini
          </Link>
        </section>
      ) : (
        <>
          <fieldset className="flex flex-wrap gap-2" disabled={busy}>
            <legend className="form-label mb-2">Uburyo bwo kwishyura</legend>
            {(Object.keys(methods) as Method[]).map((value) => (
              <label
                key={value}
                className="flex items-center gap-2 rounded-xl border border-brand-700 px-3 py-2 has-[:checked]:bg-brand-100"
              >
                <input
                  type="radio"
                  name="payment-method"
                  checked={method === value}
                  onChange={() => {
                    setMethod(value);
                    setError("");
                  }}
                />
                {methods[value]}
              </label>
            ))}
          </fieldset>

          {method === "PROMO" ? (
            <form
              className="space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                if (pending.current) return;
                const normalized = code.trim();
                if (!normalized) {
                  setError("Andika kode ya promo.");
                  return;
                }
                void run(async () => {
                  await accessRequest("promos/redeem", { code: normalized });
                  setCode("");
                  router.push("/exam");
                });
              }}
            >
              <label htmlFor="promo-code" className="form-label">
                Kode ya promo
              </label>
              <input
                id="promo-code"
                className="form-input"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                maxLength={80}
                required
                disabled={busy}
                autoComplete="off"
              />
              <button type="submit" className="form-button" disabled={busy}>
                {busy ? "Turimo kugenzura kode…" : "Koresha kode"}
              </button>
            </form>
          ) : (
            <section className="space-y-3 rounded-xl bg-accent-50 p-4">
              <label htmlFor="payer-phone" className="form-label">
                Nimero ya telefoni y’uwishyura
              </label>
              <input
                id="payer-phone"
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                maxLength={30}
                className="form-input"
                disabled={busy}
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
              />
              {state.mockEnabled ? (
                <>
                  <p className="font-semibold">
                    Ubu ni uburyo bwo kugerageza system. Nta mafaranga nyayo
                    yishyurwa.
                  </p>
                  <p className="text-sm">
                    Nimero yanditse hano ikoreshwa mu ifishi y’igerageza gusa.
                  </p>
                  <button
                    type="button"
                    disabled={busy || payment?.status === "PENDING"}
                    className="form-button"
                    onClick={() => {
                      if (pending.current) return;
                      const normalized = normalizeRwandaPhone(phone);
                      if (!normalized) {
                        setError("Andika nimero igendanwa yo mu Rwanda.");
                        return;
                      }
                      setPhone(normalized);
                      void run(async () => {
                        keys.current[method] ??= crypto.randomUUID();
                        const result = await accessRequest<MockPayment>(
                          "payments/mock/initiate",
                          {
                            provider: method,
                            idempotencyKey: keys.current[method],
                          },
                        );
                        setPayments((previous) => ({
                          ...previous,
                          [method]: result,
                        }));
                      });
                    }}
                  >
                    {busy ? "Tegereza gato…" : `${method} · Igerageza`}
                  </button>
                </>
              ) : (
                <p role="status">
                  Ubwishyu kuri telefoni ntibuboneka ubu. Ushobora gukoresha
                  kode ya promo.
                </p>
              )}
              {payment && (
                <div className="space-y-2 text-sm">
                  <p className="break-all">
                    {payment.reference} · {payment.amount} {payment.currency}
                  </p>
                  <p role="status">
                    {
                      {
                        PENDING: "Igerageza rirategereje kwemezwa.",
                        SUCCESSFUL: "Igerageza ryemejwe.",
                        FAILED: "Igerageza ntiryakunze.",
                        CANCELLED: "Igerageza ryahagaritswe.",
                      }[payment.status]
                    }
                  </p>
                  <button
                    type="button"
                    disabled={busy}
                    className="form-button"
                    onClick={() =>
                      void run(async () => {
                        const result = await accessRequest<MockPayment>(
                          `payments/${payment.id}/status`,
                        );
                        if (
                          result.status === "FAILED" ||
                          result.status === "CANCELLED"
                        )
                          delete keys.current[result.provider];
                        setPayments((previous) => ({
                          ...previous,
                          [result.provider]: result,
                        }));
                        if (result.status === "SUCCESSFUL")
                          await refreshAccess();
                      })
                    }
                  >
                    Reba uko igerageza rihagaze
                  </button>
                </div>
              )}
            </section>
          )}
          {error && (
            <p role="alert" className="text-red-800">
              {error}
            </p>
          )}
          <div className="flex flex-wrap gap-3">
            <Link className="form-button" href="/exam">
              Reba uko ikizamini gihagaze
            </Link>
            {onEdit && (
              <button
                type="button"
                disabled={busy}
                onClick={onEdit}
                className="rounded-xl border px-4 py-2"
              >
                Hindura amakuru
              </button>
            )}
          </div>
        </>
      )}
      {hasAccess && error && (
        <p role="alert" className="text-red-800">
          {error}
        </p>
      )}
      {hasAccess && onEdit && (
        <button
          type="button"
          disabled={busy}
          onClick={onEdit}
          className="rounded-xl border px-4 py-2"
        >
          Hindura amakuru
        </button>
      )}
    </div>
  );
}
