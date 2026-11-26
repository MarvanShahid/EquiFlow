import { redirect } from "next/navigation";

// The results page moved to Analytics & Reports; keep old links working.
export default function Page() {
  redirect("/reports");
}
