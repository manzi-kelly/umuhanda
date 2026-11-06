import type { StudentInformation } from "../onboarding/types";
export type PaymentProvider = "MTN" | "AIRTEL";
export type PaymentStatus = "IDLE" | "INITIATING" | "PENDING" | "SUCCESS" | "FAILED" | "CANCELLED" | "EXPIRED" | "VERIFICATION_UNAVAILABLE";
export interface PaymentInitiationRequest {
  student: StudentInformation;
  sessionReference?: string;
  provider: PaymentProvider;
  phoneNumber: string;
}
export interface PaymentInitiationResponse {
  paymentReference: string;
  status: Exclude<PaymentStatus, "IDLE" | "VERIFICATION_UNAVAILABLE">;
  message?: string;
}
export interface PaymentVerificationResponse {
  paymentReference: string;
  status: PaymentInitiationResponse["status"];
  verified: boolean;
  accessGranted: boolean;
}
export interface ServiceUnavailable {
  status: "VERIFICATION_UNAVAILABLE";
  accessGranted: false;
}
