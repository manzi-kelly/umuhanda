import { CircleAlert } from "lucide-react";
import type { PaymentStatus as Status } from "@/features/payment/types";
const messages: Record<Status, string> = {
  IDLE: "Hitamo uburyo bwo kwishyura cyangwa kode y’ubusonerwe.",
  INITIATING: "Turimo gutegura ubusabe bw’ubwishyu. Tegereza.",
  PENDING: "Ubwishyu buracyategereje kwemezwa. Nta ruhushya rwo gutangira urabona.",
  SUCCESS: "Imiterere y’ubwishyu igaragaza ko bwakiriwe. Uruhushya rwo gutangira rusaba igenzura ryihariye rya seriveri.",
  FAILED: "Ubwishyu ntibwakunze. Ongera ugenzure amakuru yawe.",
  CANCELLED: "Ubwishyu bwahagaritswe. Nta ruhushya rwo gutangira rwabonetse.",
  EXPIRED: "Igihe cy’ubusabe cyarangiye. Nta ruhushya rwo gutangira rwabonetse.",
  VERIFICATION_UNAVAILABLE: "Serivisi yo kwemeza ubwishyu na kode ntiraboneka. Nta mafaranga yakuweho, nta kode yemejwe kandi ikizamini ntikirafungurwa.",
};
export default function PaymentStatus({ status }: { status: Status }) {
  return <div role="status" aria-live="polite" aria-atomic="true" className="flex gap-3 rounded-2xl border border-accent-200 bg-accent-50 p-4 text-sm leading-6 text-ink-soft"><CircleAlert className="mt-1 size-4 shrink-0" aria-hidden="true" /><p>{messages[status]}</p></div>;
}
