import { redirect } from "next/navigation";

// AI Tools moved under the AI Center tab shell (Milestone 15) - kept as a
// redirect rather than deleted outright, cheap insurance against any
// saved bookmark/link.
export default function ToolsRedirectPage() {
  redirect("/ai-center/tools");
}
