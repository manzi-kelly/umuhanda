export interface StudentInformation {
  fullName: string;
  phoneNumber: string;
}
export type StudentSessionRequest = StudentInformation;
export interface StudentSessionResponse {
  sessionReference: string;
  expiresAt: string;
}
