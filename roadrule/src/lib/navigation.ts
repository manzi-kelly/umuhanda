export const SITE = {
  name: "Umuhanda",
  tagline: "Ikizamini cy'amategeko y'umuhanda",
  description:
    "Witegure ikizamini cy'amategeko y'umuhanda mu Rwanda. Nta konti isabwa: tanga amazina yawe na telefoni, ishyura ukoresheje MTN MoMo cyangwa Airtel Money, hanyuma utangire ikizamini cy'iminota 20.",
  contact: {
    phone: "+250 7XX XXX XXX",
    email: "hello@umuhanda.rw",
    location: "Kigali, U Rwanda",
  },
  copyrightYear: 2026,
} as const;

export const ROUTES = {
  home: "/",
  start: "/tangira",
  howItWorks: "/#uko-bikora",
  rules: "/#amategeko",
  payment: "/#ishyura",
} as const;

export const NAV_LINKS = [
  { label: "Ahabanza", href: "/#ahabanza" },
  { label: "Uko Bikora", href: ROUTES.howItWorks },
  { label: "Amategeko", href: ROUTES.rules },
] as const;
