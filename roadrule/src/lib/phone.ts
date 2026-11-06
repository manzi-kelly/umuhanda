/** RURA June 2023 mobile ranges. This does not establish ownership or wallet provider. */
export function normalizeRwandaPhone(input: string): string | null {
  if (!/^[+\d\s()-]+$/.test(input)) return null;
  const compact = input.replace(/[\s()-]/g, "");
  const national = compact.startsWith("+250") ? compact.slice(4)
    : compact.startsWith("250") ? compact.slice(3)
    : compact.startsWith("0") ? compact.slice(1) : compact;
  return /^7[23789]\d{7}$/.test(national) ? `+250${national}` : null;
}
