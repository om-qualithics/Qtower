// Same tier vocabulary as apps/api/modules/tools/constants.py::TIER_KEYS -
// shared here so the Tools catalog, the new Tools/Project request wizards
// don't each keep their own local copy (Milestone 18).
export const TIER_KEYS = ["restricted", "confidential", "internal", "public"] as const;

export const TIER_LABELS: Record<string, string> = {
  restricted: "Restricted (Tier 1)",
  confidential: "Confidential (Tier 2)",
  internal: "Internal (Tier 3)",
  public: "Public (Tier 4)",
};
