import type { ServiceUnavailable } from "../payment/types";
import type { PromoValidationRequest } from "./types";
export async function redeemPromo(request: PromoValidationRequest): Promise<ServiceUnavailable> {
  void request;
  return { status: "VERIFICATION_UNAVAILABLE", accessGranted: false };
}
