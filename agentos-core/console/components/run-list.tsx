"use client";

import { Filter } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { RunSummary } from "@/lib/types";
import { cn, formatScore, formatWhen, scoreTone } from "@/lib/utils";

type RunListProps = {
  runs: RunSummary[];
  selectedRunId: string | null;
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  onSelect: (runId: string) => void;
};

export function RunList({
  runs,
  selectedRunId,
  search,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  onSelect
}: RunListProps) {
  return (
    <Card className="p-6">
      <CardHeader>
        <div>
          <CardTitle>Runs</CardTitle>
          <CardDescription>
            Filter recent runs and jump directly into traces, transitions, and feedback.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <div className="mb-4 flex flex-col gap-3">
          <Input
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search prompts"
          />
          <label className="flex items-center gap-2 rounded-full border border-line bg-white/5 px-4 py-2 text-sm text-muted">
            <Filter className="h-4 w-4" />
            <select
              value={statusFilter}
              onChange={(event) => onStatusFilterChange(event.target.value)}
              className="w-full bg-transparent outline-none"
            >
              <option value="all">All statuses</option>
              <option value="ok">Ok</option>
              <option value="rejected">Rejected</option>
              <option value="error">Error</option>
              <option value="running">Running</option>
            </select>
          </label>
        </div>
        <div className="grid max-h-[760px] gap-3 overflow-y-auto pr-1">
          {runs.map((run) => (
            <button
              key={run.run_id}
              type="button"
              onClick={() => onSelect(run.run_id)}
              className={cn(
                "rounded-[24px] border border-line bg-white/5 p-4 text-left transition hover:border-accent/50 hover:bg-white/10",
                selectedRunId === run.run_id && "border-accent/80 bg-accent/10"
              )}
            >
              <p className="text-sm font-medium text-white">{run.user_input || "(empty prompt)"}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge>{run.status}</Badge>
                <Badge className={scoreTone(run.score)}>score {formatScore(run.score)}</Badge>
                <Badge>{run.total_latency_ms ?? 0} ms</Badge>
              </div>
              <div className="mt-3 flex items-center justify-between text-xs text-muted">
                <span>{formatWhen(run.started_at)}</span>
                <span>{run.prompt_version}</span>
              </div>
            </button>
          ))}
          {!runs.length ? (
            <div className="rounded-[24px] border border-dashed border-line px-4 py-12 text-center text-sm text-muted">
              No runs match the current filter.
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
