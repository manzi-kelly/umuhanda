"use client";
import { useActionState } from "react";
import { LogOut } from "lucide-react";
import { logoutAdmin } from "@/features/admin/actions";
import type { AuthState } from "@/features/admin/types";

export default function LogoutButton() {
  const [state, action, pending] = useActionState<AuthState, FormData>(logoutAdmin, {});
  return <form action={action}><button disabled={pending} className="flex min-h-11 w-full items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold text-brand-100 hover:bg-white/10 disabled:opacity-50"><LogOut className="size-4" aria-hidden="true" />{pending ? "Signing out…" : "Logout"}</button>{state.error && <p role="alert" className="px-4 py-2 text-xs leading-5 text-accent-200">{state.error}</p>}</form>;
}
