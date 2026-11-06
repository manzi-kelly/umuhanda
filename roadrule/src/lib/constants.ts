import {
  Ban,
  BadgeCheck,
  CheckCircle2,
  Clock3,
  FileCheck2,
  ListChecks,
  LockKeyhole,
  Mail,
  MapPin,
  MoveRight,
  Phone,
  ShieldAlert,
  Smartphone,
  Ticket,
  Timer,
  TimerOff,
  Trophy,
  UserRound,
  Wallet,
  type LucideIcon,
} from "lucide-react";

import { ROUTES, SITE } from "./navigation";

export { NAV_LINKS, ROUTES, SITE } from "./navigation";

export type Step = {
  number: string;
  title: string;
  description: string;
  icon: LucideIcon;
  hint?: string;
};

export const HOW_IT_WORKS_STEPS: Step[] = [
  {
    number: "01",
    title: "Tanga amazina yawe na telefoni",
    description:
      "Uzuza amazina yombi n'umubare wa telefoni yawe. Nta konti, email cyangwa ijambo ry'ibanga bisabwa.",
    icon: UserRound,
    hint: "Nta konti isabwa",
  },
  {
    number: "02",
    title: "Ishyura cyangwa ukoreshe kode",
    description:
      "Hitamo MTN MoMo, Airtel Money cyangwa kode y'ubusonerwe yemewe. Kwemeza bizakorwa kuri telefoni yawe.",
    icon: Wallet,
    hint: "MTN MoMo · Airtel Money · Promo",
  },
  {
    number: "03",
    title: "Tangira ikizamini cy'iminota 20",
    description:
      "Ibibazo 20 bizagaragara kimwe kimwe. Ufite amasegonda 60 kuri buri kibazo kandi nta gusubira inyuma.",
    icon: Timer,
    hint: "Ibibazo 20 · Iminota 20",
  },
  {
    number: "04",
    title: "Menya ibisubizo ako kanya",
    description:
      "Nyuma y'ikizamini, amanota n'ibisubizo bizagaragara ako kanya ku rupapuro rwawe.",
    icon: Trophy,
    hint: "Ibisubizo by'ako kanya",
  },
];

export type ExamRule = {
  title: string;
  description: string;
  icon: LucideIcon;
  tone?: "default" | "warning";
};

export const EXAM_RULES: ExamRule[] = [
  {
    title: "Ibibazo 20 mu kizamini",
    description:
      "Buri kizamini kigizwe n'ibibazo 20 byatoranyijwe mu mategeko y'umuhanda.",
    icon: ListChecks,
  },
  {
    title: "Iminota 20 ntarengwa",
    description:
      "Ikizamini cyose kigomba kurangira mu minota 20. Igihe gikomeza guharurwa kuva utangiye.",
    icon: Clock3,
  },
  {
    title: "Amasegonda 60 ku kibazo",
    description:
      "Ku kibazo kimwe, ufite amasegonda 60 ntarengwa yo gusubiza.",
    icon: Timer,
  },
  {
    title: "Ikibazo kimwe ku rupapuro",
    description:
      "Ikibazo kimwe kigaragara ku rupapuro mu gihe kimwe, n'amahitamo ajyanye na cyo.",
    icon: FileCheck2,
  },
  {
    title: "Nta gusubira inyuma",
    description:
      "Iyo umaze gusubiza ukajya ku kibazo gikurikira, ntushobora gusubira ku kibazo cyabanje.",
    icon: Ban,
  },
  {
    title: "Kwimuka ubwako",
    description:
      "Igihe cy'ikibazo kirangiye, sisitemu ihita yimuka ku kibazo gikurikira nta gutegereza.",
    icon: MoveRight,
  },
  {
    title: "Kurangira ku gihe rusange",
    description:
      "Igihe cyose cy'iminota 20 kirangiye, ikizamini kirangira ubwako nubwo hari ibibazo bisigaye.",
    icon: TimerOff,
  },
  {
    title: "Iburira ritukura ku minota 18",
    description:
      "Iminota 18 nimara kwita, ingaruka y'igihe ihinduka umutuku kugeza ikizamini kirangiye.",
    icon: ShieldAlert,
    tone: "warning",
  },
];

export const EXAM_SUMMARY = [
  { label: "Ibibazo", value: "20", icon: ListChecks },
  { label: "Igihe cyose", value: "20 min", icon: Clock3 },
  { label: "Ku kibazo", value: "60 s", icon: Timer },
] as const;

export type PaymentMethod = {
  name: string;
  description: string;
  icon: LucideIcon;
  accent: "amber" | "red" | "gold";
  label: string;
};

export const PAYMENT_METHODS: PaymentMethod[] = [
  {
    name: "MTN Mobile Money",
    description:
      "Ishyura ukoresheje konti yawe ya MTN Mobile Money. Uzahitamo ubu buryo mu ntambwe yo kwiyandikisha.",
    icon: Smartphone,
    accent: "amber",
    label: "MTN MoMo",
  },
  {
    name: "Airtel Money",
    description:
      "Ishyura ukoresheje konti yawe ya Airtel Money. Uzahitamo ubu buryo mu ntambwe yo kwiyandikisha.",
    icon: Wallet,
    accent: "red",
    label: "Airtel Money",
  },
  {
    name: "Kode y'ubusonerwe",
    description:
      "Niba ufite kode yemewe, uzayishyira mu ntambwe yo kwiyandikisha aho kwishyura.",
    icon: Ticket,
    accent: "gold",
    label: "Promo code",
  },
];

export const PAYMENT_STEPS = [
  {
    title: "Hitamo uburyo bwo kwishyura",
    description: "MTN MoMo, Airtel Money cyangwa kode y'ubusonerwe yemewe.",
  },
  {
    title: "Emeza kuri telefoni yawe",
    description:
      "Ubutumwa buzakugera kuri telefoni yawe. Emeza ukoresheje PIN yawe kuri telefoni gusa.",
  },
  {
    title: "Injira mu kizamini",
    description:
      "Iyo kwemezwa kurangiye, uzabona uruhushya rwo gutangira ikizamini cyawe.",
  },
] as const;

export const FOOTER_LINKS = [
  { label: "Ahabanza", href: "/#ahabanza" },
  { label: "Uko Bikora", href: ROUTES.howItWorks },
  { label: "Amategeko y'ikizamini", href: ROUTES.rules },
  { label: "Kwishyura", href: ROUTES.payment },
  { label: "Tangira Ikizamini", href: ROUTES.start },
] as const;

export const FOOTER_CONTACT = [
  { label: "Telefoni", value: SITE.contact.phone, icon: Phone },
  { label: "Email", value: SITE.contact.email, icon: Mail },
  { label: "Aderesi", value: SITE.contact.location, icon: MapPin },
] as const;

export const TRUST_POINTS = [
  { label: "Nta konti isabwa", icon: BadgeCheck },
  { label: "Iminota 20 gusa", icon: Clock3 },
  { label: "Ibisubizo ako kanya", icon: CheckCircle2 },
  { label: "Nta PIN isabwa", icon: LockKeyhole },
] as const;

export const COMING_SOON_POINTS = [
  {
    title: "Ifishi y'amakuru y'ibanze",
    description: "Amazina yombi n'umubare wa telefoni, nta konti cyangwa email.",
    icon: UserRound,
  },
  {
    title: "Kwishyura kuri telefoni",
    description: "MTN MoMo, Airtel Money cyangwa kode y'ubusonerwe yemewe.",
    icon: Smartphone,
  },
  {
    title: "Ikizamini cy'iminota 20",
    description: "Ibibazo 20, amasegonda 60 ku kibazo, nta gusubira inyuma.",
    icon: Timer,
  },
  {
    title: "Ibisubizo bidahishe",
    description: "Amanota n'ibisubizo bigaragara ako kanya nyuma y'ikizamini.",
    icon: Trophy,
  },
] as const;
