"use client";

import Results from "../Results";
import { PageHeader } from "../ui";

export default function Reports() {
  return (
    <div className="page">
      <PageHeader
        title="Analytics & reports"
        description="How long vehicles wait at signals under each controller, measured in batch SUMO runs on Islamabad-style junctions with a motorcycle-heavy mix and 6 to 14 ambulances per hour. These are the saved evaluation results (sumo/results), not live data."
      />
      <Results />
    </div>
  );
}
