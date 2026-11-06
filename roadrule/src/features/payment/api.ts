import type { PaymentInitiationRequest, ServiceUnavailable } from "./types";
/** Offline boundary. Never synthesize transactions, references or success. */
export async function initiatePayment(request: PaymentInitiationRequest): Promise<ServiceUnavailable> {
  void request;
  return { status: "VERIFICATION_UNAVAILABLE", accessGranted: false };
}
