import Results from "@/components/Results";

export const metadata = { title: "Results · EquiFlow" };

export default function Page() {
  return (
    <main className="shell">
      <header className="pagehead">
        <div>
          <h1>Results</h1>
          <p className="lede">
            How long vehicles wait at signals under each controller, measured in SUMO on Islamabad-style junctions with a
            motorcycle-heavy mix and 6 to 14 ambulances per hour.
          </p>
        </div>
      </header>
      <Results />
    </main>
  );
}
