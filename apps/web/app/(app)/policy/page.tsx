"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Download, FileText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { createPolicy, getPolicyDownloadUrl, listPolicies, type PolicyListItem } from "@/lib/api";

export default function PolicyListPage() {
  const router = useRouter();
  const [policies, setPolicies] = useState<PolicyListItem[] | "loading">("loading");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    listPolicies()
      .then(setPolicies)
      .catch(() => setPolicies([]));
  }, []);

  const startNewPolicy = async () => {
    setCreating(true);
    try {
      const policy = await createPolicy();
      router.push(`/policy/new?id=${policy.id}`);
    } finally {
      setCreating(false);
    }
  };

  const download = async (id: string) => {
    const url = await getPolicyDownloadUrl(id);
    window.location.assign(url);
  };

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">AI Policy</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Build and manage your organization&apos;s AI governance policy.
          </p>
        </div>
        <Button onClick={startNewPolicy} disabled={creating}>
          <Plus /> New Policy
        </Button>
      </div>

      {policies === "loading" && <p className="text-sm text-muted-foreground">Loading...</p>}

      {policies !== "loading" && policies.length === 0 && (
        <div className="rounded-2xl border border-dashed border-border p-10 text-center">
          <FileText className="mx-auto mb-3 size-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No AI policy has been created yet. Start the guided builder to generate one from your
            organization&apos;s enterprise policy template.
          </p>
        </div>
      )}

      {policies !== "loading" && policies.length > 0 && (
        <div className="space-y-3">
          {policies.map((policy) => (
            <div
              key={policy.id}
              className="flex items-center justify-between rounded-2xl border border-border bg-card p-4"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">
                    {policy.policy_owner_name ? `Policy owned by ${policy.policy_owner_name}` : "Untitled policy"}
                  </span>
                  <span className="rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground">
                    {policy.status === "generated" ? `Version: ${policy.version}` : "Draft"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {policy.status === "generated" && policy.generated_at
                    ? `Generated ${new Date(policy.generated_at).toLocaleDateString()}`
                    : `Last updated ${new Date(policy.updated_at).toLocaleDateString()}`}
                </p>
              </div>
              {policy.status === "generated" ? (
                <Button variant="outline" size="sm" onClick={() => download(policy.id)}>
                  <Download /> Download
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => router.push(`/policy/new?id=${policy.id}`)}
                >
                  Continue
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
