import { normalizeRwandaPhone } from "../../lib/phone";
import type { StudentInformation } from "./types";
export type StudentErrors = Partial<Record<keyof StudentInformation, string>>;
export function validateStudent(input: StudentInformation): { student: StudentInformation | null; errors: StudentErrors } {
  const fullName = input.fullName.trim().replace(/\s+/g, " ");
  const phoneNumber = normalizeRwandaPhone(input.phoneNumber);
  const errors: StudentErrors = {};
  if (!fullName) errors.fullName = "Andika amazina yawe yose.";
  else if (fullName.length > 120 || !/^[\p{L}\p{M}]+(?:[ ’'‐-][\p{L}\p{M}]+)*$/u.test(fullName))
    errors.fullName = "Andika amazina akoresheje inyuguti, atarenze 120.";
  if (!phoneNumber) errors.phoneNumber = "Andika nimero igendanwa yo mu Rwanda, nka 0781234567 cyangwa +250781234567.";
  return { student: Object.keys(errors).length ? null : { fullName, phoneNumber: phoneNumber! }, errors };
}
