"use client";
import { useEffect, useState } from "react";

type Promo = {
  id: string;
  code: string | null;
  createdAt: string;
  publishedAt: string | null;
  updatedAt: string;
  expiresAt: string;
  usageLimit: number;
  used: number;
  status: string;
  disabledAt: string | null;
};
type Page = { items: Promo[]; hasMore: boolean };
type Redemption = {
  id: string;
  createdAt: string;
  status: string;
  accessStatus: string;
};
type EditState = { id: string; code: string; usageLimit: number; expiresAt: string };

const messages: Record<string, string> = {
  PROMO_CODE_INVALID:
    "Enter a code using letters, numbers, dots, hyphens or underscores.",
  PROMO_DUPLICATE: "That promo code already exists. Choose a different code.",
  PROMO_NOT_FOUND: "That promo code no longer exists.",
  PROMO_UPDATE_EMPTY: "Change at least one value before saving.",
  PROMO_EXPIRY_INVALID: "The expiry must be after the code was created.",
  ADMIN_AUTH_REQUIRED: "Your administrator session has expired. Sign in again.",
  ORIGIN_REJECTED: "Refresh the page and try again.",
  VALIDATION_ERROR: "Check the values you entered and try again.",
  BODY_LIMIT: "The request was too large.",
};

function localInput(iso: string) {
  const date = new Date(iso);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

async function api<T>(
  path: string,
  init?: { method?: "POST" | "PATCH" | "DELETE"; body?: object },
): Promise<T> {
  const response = await fetch("/admin/pdf-api/" + path, {
    cache: "no-store",
    method: init?.method ?? "GET",
    headers: { "Content-Type": "application/json" },
    body: init?.body ? JSON.stringify(init.body) : undefined,
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      messages[payload?.error?.code as string] ??
        "Unable to complete the request. Check the admin session and try again.",
    );
  return payload as T;
}

export default function PromoManager() {
  const [data, setData] = useState<Page | null>(null);
  const [limit, setLimit] = useState(1);
  const [hours, setHours] = useState(24);
  const [offset, setOffset] = useState(0);
  const [code, setCode] = useState("");
  const [published, setPublished] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [edit, setEdit] = useState<EditState | null>(null);
  const [history, setHistory] = useState<{
    id: string;
    items: Redemption[];
  } | null>(null);

  useEffect(() => {
    let active = true;
    api<Page>(`promo-codes?offset=${offset}`)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((failure) => {
        if (active) setError(failure.message);
      });
    return () => {
      active = false;
    };
  }, [offset]);

  async function refresh() {
    setData(await api<Page>(`promo-codes?offset=${offset}`));
  }

  async function action(operation: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await operation();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <form
        className="flex flex-wrap items-end gap-3 rounded-xl border border-ink/10 bg-surface p-4"
        onSubmit={(event) => {
          event.preventDefault();
          void action(async () => {
            const created = await api<Promo>("promo-codes", {
              method: "POST",
              body: { code, usageLimit: limit, expiresInHours: hours },
            });
            setPublished(created.code);
            setCode("");
            setOffset(0);
            await refresh();
          });
        }}
      >
        <label className="form-label">
          Promo code
          <input
            className="form-input uppercase"
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            minLength={1}
            maxLength={80}
            pattern="[A-Za-z0-9][A-Za-z0-9._\-]{0,79}"
            required
            autoComplete="off"
            spellCheck={false}
            placeholder="e.g. ROAD-2026"
          />
        </label>
        <label className="form-label">
          Usage limit
          <input
            type="number"
            min={1}
            max={100}
            required
            value={limit}
            onChange={(event) => setLimit(event.target.valueAsNumber)}
            className="form-input"
          />
        </label>
        <label className="form-label">
          Valid for (hours)
          <input
            type="number"
            min={1}
            max={8760}
            required
            value={hours}
            onChange={(event) => setHours(event.target.valueAsNumber)}
            className="form-input"
          />
        </label>
        <button className="form-button" disabled={busy}>
          {busy ? "Publishing…" : "Generate / Publish code"}
        </button>
      </form>
      {published && (
        <div
          role="status"
          className="rounded-xl border border-brand-200 bg-accent-50 p-4"
        >
          <p className="font-semibold">Published promo code</p>
          <code className="break-all font-bold">{published}</code>
          <button
            className="ml-3 underline"
            type="button"
            onClick={() => {
              void navigator.clipboard
                ?.writeText(published)
                .catch(() => undefined);
            }}
          >
            Copy code
          </button>
          <button
            className="ml-3 underline"
            type="button"
            onClick={() => setPublished(null)}
          >
            Hide code
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="text-red-800">
          {error}
        </p>
      )}
      <ul className="space-y-3">
        {data?.items.map((row) => (
          <li key={row.id} className="rounded-xl border border-ink/10 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="break-all font-semibold">
                  {row.code ?? "Legacy code (hidden)"}
                </p>
                <p className="text-sm text-ink-muted">
                  {row.status} · {row.used}/{row.usageLimit} used
                </p>
              </div>
              <span className="rounded-full bg-canvas px-3 py-1 text-xs font-bold uppercase tracking-wide">
                {row.status}
              </span>
            </div>
            <p className="mt-2 text-sm">
              Expires{" "}
              {new Date(row.expiresAt)
                .toISOString()
                .slice(0, 16)
                .replace("T", " ")}{" "}
              UTC
            </p>
            <div className="mt-3 flex flex-wrap gap-3">
              {row.disabledAt ? (
                <button
                  type="button"
                  className="underline"
                  disabled={busy}
                  onClick={() =>
                    action(async () => {
                      await api(`promo-codes/${row.id}/enable`, {
                        method: "POST",
                        body: {},
                      });
                      await refresh();
                    })
                  }
                >
                  Enable
                </button>
              ) : (
                <button
                  type="button"
                  className="underline"
                  disabled={busy}
                  onClick={() =>
                    action(async () => {
                      await api(`promo-codes/${row.id}/disable`, {
                        method: "POST",
                        body: {},
                      });
                      await refresh();
                    })
                  }
                >
                  Disable
                </button>
              )}
              <button
                type="button"
                className="underline"
                disabled={busy}
                onClick={() =>
                  setEdit({
                    id: row.id,
                    code: row.code ?? "",
                    usageLimit: row.usageLimit,
                    expiresAt: localInput(row.expiresAt),
                  })
                }
              >
                Edit
              </button>
              <button
                type="button"
                className="underline"
                disabled={busy}
                onClick={() => {
                  if (
                    !window.confirm(
                      "Delete this promo code? Existing redemptions stay valid, but the code can be reused or recreated.",
                    )
                  )
                    return;
                  void action(async () => {
                    await api(`promo-codes/${row.id}`, { method: "DELETE" });
                    if (history?.id === row.id) setHistory(null);
                    await refresh();
                  });
                }}
              >
                Delete
              </button>
              <button
                type="button"
                className="underline"
                disabled={busy}
                onClick={() =>
                  action(async () => {
                    setHistory({
                      id: row.id,
                      items: await api<Redemption[]>(
                        `promo-codes/${row.id}/redemptions`,
                      ),
                    });
                  })
                }
              >
                Redemption history
              </button>
            </div>
            {edit?.id === row.id && (
              <form
                className="mt-4 flex flex-wrap items-end gap-3 rounded-xl bg-canvas p-3"
                onSubmit={(event) => {
                  event.preventDefault();
                  void action(async () => {
                    await api(`promo-codes/${row.id}`, {
                      method: "PATCH",
                      body: {
                        code: edit.code,
                        usageLimit: edit.usageLimit,
                        expiresAt: new Date(edit.expiresAt).toISOString(),
                      },
                    });
                    setEdit(null);
                    await refresh();
                  });
                }}
              >
                <label className="form-label">
                  Promo code
                  <input
                    className="form-input uppercase"
                    value={edit.code}
                    onChange={(event) =>
                      setEdit({ ...edit, code: event.target.value.toUpperCase() })
                    }
                    minLength={1}
                    maxLength={80}
                    pattern="[A-Za-z0-9][A-Za-z0-9._\-]{0,79}"
                    required
                  />
                </label>
                <label className="form-label">
                  Usage limit
                  <input
                    type="number"
                    min={1}
                    max={100}
                    required
                    value={edit.usageLimit}
                    onChange={(event) =>
                      setEdit({
                        ...edit,
                        usageLimit: event.target.valueAsNumber,
                      })
                    }
                    className="form-input"
                  />
                </label>
                <label className="form-label">
                  Expires at
                  <input
                    type="datetime-local"
                    required
                    value={edit.expiresAt}
                    onChange={(event) =>
                      setEdit({ ...edit, expiresAt: event.target.value })
                    }
                    className="form-input"
                  />
                </label>
                <button className="form-button" disabled={busy}>
                  Save changes
                </button>
                <button
                  type="button"
                  className="underline"
                  disabled={busy}
                  onClick={() => setEdit(null)}
                >
                  Cancel
                </button>
              </form>
            )}
            {history?.id === row.id && (
              <div className="mt-3 text-sm">
                <p className="font-semibold">Redemption history</p>
                <ul className="mt-1 space-y-1">
                  {!history.items.length && <li>No redemptions.</li>}
                  {history.items.map((item) => (
                    <li key={item.id}>
                      {item.createdAt} · {item.status} · {item.accessStatus}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </li>
        ))}
      </ul>
      {data && !data.items.length && <p>No promo codes.</p>}
      <div className="flex gap-3">
        {offset > 0 && (
          <button className="underline" onClick={() => setOffset(offset - 50)}>
            Previous
          </button>
        )}
        {data?.hasMore && (
          <button className="underline" onClick={() => setOffset(offset + 50)}>
            Next
          </button>
        )}
      </div>
    </div>
  );
}
