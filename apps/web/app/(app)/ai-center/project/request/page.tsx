"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, CheckCircle2, ChevronLeft, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { WizardProgressBar } from "@/components/ui/wizard-progress-bar";
import { TIER_KEYS, TIER_LABELS } from "@/lib/tiers";
import {
  createProjectRequest,
  fetchApprovedTools,
  fetchVendors,
  type ApprovedTool,
  type ProjectLinkIn,
  type Vendor,
} from "@/lib/api";

const STEPS = [
  { id: 1, title: "Basics" },
  { id: 2, title: "Justification & data" },
  { id: 3, title: "Oversight & links" },
];

// Shared by the Tools and Vendors pickers on the submission form - a
// Select of real catalog entries plus a literal "Other..." option that
// reveals a free-text name field, addable multiple times. Picking
// "Other" tags the resulting link as "not registered in inventory"
// (structural, set at submission - not an LLM inference).
function LinkPicker({
  label,
  idKey,
  options,
  links,
  onChange,
}: {
  label: string;
  idKey: "tool_id" | "vendor_id";
  options: { id: string; name: string }[];
  links: ProjectLinkIn[];
  onChange: (links: ProjectLinkIn[]) => void;
}) {
  const [selection, setSelection] = useState<string>(options[0]?.id ?? "__other__");
  const [otherName, setOtherName] = useState("");

  const add = () => {
    if (selection === "__other__") {
      if (!otherName.trim()) return;
      onChange([...links, { other_name: otherName.trim() }]);
      setOtherName("");
    } else {
      const option = options.find((o) => o.id === selection);
      if (!option) return;
      onChange([...links, { [idKey]: selection }]);
    }
  };

  return (
    <div>
      <Label className="mb-1.5 block text-xs">{label}</Label>
      <div className="flex gap-2">
        <Select className="flex-1" value={selection} onChange={(e) => setSelection(e.target.value)}>
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
          <option value="__other__">Other...</option>
        </Select>
        {selection === "__other__" && (
          <Input
            className="flex-1"
            placeholder="Name (not in inventory)"
            value={otherName}
            onChange={(e) => setOtherName(e.target.value)}
          />
        )}
        <Button type="button" variant="outline" onClick={add}>
          Add
        </Button>
      </div>
      {links.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {links.map((link, i) => {
            const option = options.find((o) => o.id === link.tool_id || o.id === link.vendor_id);
            const name = option?.name ?? link.other_name ?? "";
            return (
              <span
                key={i}
                className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-xs text-foreground"
              >
                {name}
                {!option && <span className="text-muted-foreground">(other)</span>}
                <button type="button" onClick={() => onChange(links.filter((_, j) => j !== i))}>
                  <X className="size-3" />
                </button>
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function ProjectRequestPage() {
  const router = useRouter();
  const [tools, setTools] = useState<ApprovedTool[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);

  const [currentStep, setCurrentStep] = useState(1);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [justification, setJustification] = useState("");
  const [dataFlow, setDataFlow] = useState("");
  const [dataTiers, setDataTiers] = useState<string[]>([]);
  const [humanInLoop, setHumanInLoop] = useState(true);
  const [toolLinks, setToolLinks] = useState<ProjectLinkIn[]>([]);
  const [vendorLinks, setVendorLinks] = useState<ProjectLinkIn[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    fetchApprovedTools()
      .then(setTools)
      .catch(() => setTools([]));
    fetchVendors()
      .then(setVendors)
      .catch(() => setVendors([]));
  }, []);

  const stepValid: Record<number, boolean> = {
    1: name.trim().length > 0 && description.trim().length > 0,
    2: justification.trim().length > 0 && dataFlow.trim().length > 0 && dataTiers.length > 0,
    3: true,
  };
  const isLastStep = currentStep === STEPS.length;

  const goBack = () => setCurrentStep((s) => Math.max(1, s - 1));

  const goNext = async () => {
    if (!stepValid[currentStep]) return;
    setError(null);
    if (!isLastStep) {
      setCurrentStep((s) => s + 1);
      return;
    }
    setSubmitting(true);
    try {
      await createProjectRequest(
        name, description, justification, dataFlow, humanInLoop, toolLinks, vendorLinks, dataTiers
      );
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="mx-auto max-w-xl text-center">
        <CheckCircle2 className="mx-auto mb-4 size-12 text-primary" />
        <h1 className="text-xl font-semibold">Project submitted for review</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          An AI precheck runs automatically if your org has an active policy - a govern/assure reviewer will make
          the final call.
        </p>
        <div className="mt-6 flex justify-center">
          <Button onClick={() => router.push("/ai-center/project")}>Back to AI Project</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-fit max-w-full">
      <div className="w-full max-w-[clamp(32rem,28rem+17vw,56rem)]">
        <button
          type="button"
          onClick={() => router.push("/ai-center/project")}
          className="mb-2 flex items-center gap-1 text-sm text-muted-foreground transition hover:text-foreground"
        >
          <ChevronLeft className="size-4" /> Back to AI Project
        </button>

        <h1 className="mb-1 text-2xl font-semibold">New Project</h1>
        <p className="mb-4 text-sm text-muted-foreground">
          Describe the AI use-case or workflow. Linking Tools/Vendors is optional — anything not already in the
          catalog can be added by name and gets tagged as not registered in inventory.
        </p>

        <div className="mb-6">
          <WizardProgressBar
            steps={STEPS}
            currentStep={currentStep}
            onPrev={goBack}
            onNext={goNext}
            nextDisabled={!stepValid[currentStep] || submitting}
          />
        </div>

        <div className="rounded-2xl border border-border bg-card p-5">
          {error && (
            <div className="mb-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {currentStep === 1 && (
            <div className="space-y-5">
              <div>
                <Label className="mb-1.5 block text-sm font-medium">Name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Support Ticket Triage" />
              </div>
              <div>
                <Label className="mb-1.5 block text-sm font-medium">Description</Label>
                <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} />
              </div>
            </div>
          )}

          {currentStep === 2 && (
            <div className="space-y-5">
              <div>
                <Label className="mb-1.5 block text-sm font-medium">Business justification</Label>
                <Textarea value={justification} onChange={(e) => setJustification(e.target.value)} rows={3} />
              </div>
              <div>
                <Label className="mb-1.5 block text-sm font-medium">Data flow description</Label>
                <Textarea
                  value={dataFlow}
                  onChange={(e) => setDataFlow(e.target.value)}
                  rows={3}
                  placeholder="What data goes in, where it comes from, where it ends up"
                />
              </div>
              <div>
                <Label className="mb-1.5 block text-sm font-medium">What class of data tier will be used?</Label>
                <div className="space-y-2">
                  {TIER_KEYS.map((tier) => (
                    <label key={tier} className="flex items-center gap-2 text-sm">
                      <Checkbox
                        checked={dataTiers.includes(tier)}
                        onCheckedChange={(checked) =>
                          setDataTiers((prev) => (checked ? [...prev, tier] : prev.filter((t) => t !== tier)))
                        }
                      />
                      {TIER_LABELS[tier]}
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          {currentStep === 3 && (
            <div className="space-y-5">
              <div className="flex items-center gap-2">
                <Checkbox checked={humanInLoop} onCheckedChange={(checked) => setHumanInLoop(checked === true)} />
                <Label className="text-sm">A human stays in the loop</Label>
              </div>
              <LinkPicker
                label="Linked tools (optional)"
                idKey="tool_id"
                options={tools.map((t) => ({ id: t.id, name: t.name }))}
                links={toolLinks}
                onChange={setToolLinks}
              />
              <LinkPicker
                label="Linked vendors (optional)"
                idKey="vendor_id"
                options={vendors.map((v) => ({ id: v.id, name: v.name }))}
                links={vendorLinks}
                onChange={setVendorLinks}
              />
            </div>
          )}
        </div>

        <div className="mt-5 flex justify-between">
          <Button variant="outline" onClick={goBack} disabled={currentStep === 1 || submitting}>
            <ArrowLeft /> Back
          </Button>
          <Button onClick={goNext} disabled={!stepValid[currentStep] || submitting}>
            {isLastStep ? (submitting ? "Submitting..." : "Send for Approval") : "Next"}
            {!isLastStep && <ArrowRight />}
          </Button>
        </div>
      </div>
    </div>
  );
}
