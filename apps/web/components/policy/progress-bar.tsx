import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

export function PolicyProgressBar({
  steps,
  currentStep,
}: {
  steps: { id: number; title: string }[];
  currentStep: number;
}) {
  const percent = ((currentStep - 1) / (steps.length - 1)) * 100;

  return (
    <div className="space-y-3">
      <Progress value={percent} />
      <div className="flex flex-wrap justify-between gap-x-4 gap-y-1 text-xs">
        {steps.map((step) => (
          <span
            key={step.id}
            className={cn(
              "font-medium",
              step.id === currentStep ? "text-primary" : step.id < currentStep ? "text-foreground" : "text-muted-foreground"
            )}
          >
            {step.id}. {step.title}
          </span>
        ))}
      </div>
    </div>
  );
}
