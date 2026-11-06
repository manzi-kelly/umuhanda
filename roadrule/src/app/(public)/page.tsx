import ExamRules from "@/components/home/ExamRules";
import FinalCTA from "@/components/home/FinalCTA";
import HeroSection from "@/components/home/HeroSection";
import HowItWorks from "@/components/home/HowItWorks";
import PaymentInformation from "@/components/home/PaymentInformation";

export default function HomePage() {
  return (
    <>
      <HeroSection />
      <HowItWorks />
      <ExamRules />
      <PaymentInformation />
      <FinalCTA />
    </>
  );
}
