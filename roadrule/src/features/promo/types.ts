import type { StudentInformation } from "../onboarding/types";
export interface PromoValidationRequest {
  code: string;
  student: StudentInformation;
  sessionReference?: string;
}
export interface PromoValidationResponse {
  valid: boolean;
  redeemed: boolean;
  accessGranted: boolean;
  expiresAt?: string;
  message?: string;
}
