export type AdminIdentity = { id: string; fullName: string; email: string; role: "ADMIN"; expiresAt: string };
export type AdminSummary = { totalStudents: number; totalExamAttempts: null; passedExams: null; failedExams: null; totalVerifiedRevenue: null; activePromoCodes: null };
export type AuthState = { error?: string; fields?: { email?: string; password?: string } };
