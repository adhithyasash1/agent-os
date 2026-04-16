"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { MessageSquareWarning, Workflow } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { RunDetail as RunDetailType } from "@/lib/types";
import { formatScore, formatWhen, scoreTone } from "@/lib/utils";

type RunDetailProps = {
  run: RunDetailType | undefined;
  isPending: boolean;
  feedbackPending: boolean;
  onSubmitFeedback: (payload: { rating?: number; notes?: string }) => void;
};

export function RunDetail({
  run,
  isPending,
  feedbackPending,
  onSubmitFeedback
}: RunDetailProps) {
  const [notes, setNotes] = useState("");

  if (isPending && !run) {
    return (
      <Card className="p-6">
        <div className="rounded-[28px] border border-dashed border-line px-4 py-24 text-center text-sm text-muted">
          Loading run details...
        </div>
      </Card>
    );
  }

  if (!run) {
    return (
      <Card className="p-6">
        <div className="rounded-[28px] border border-dashed border-line px-4 py-24 text-center text-sm text-muted">
          Select a run to inspect events, transitions, and verifier output.
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <CardHeader>
        <div>
          <CardTitle>Trace Breakdown</CardTitle>
          <CardDescription>
            Run {run.run_id} • {formatWhen(run.started_at)} • {run.prompt_version}
          </CardDescription>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge>{run.status}</Badge>
          <Badge className={scoreTone(run.score)}>score {formatScore(run.score)}</Badge>
          <Badge>{run.events.length} events</Badge>
          <Badge>{run.transitions.length} transitions</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-[24px] border border-line bg-white/5 p-5"
        >
          <div className="text-xs uppercase tracking-[0.2em] text-muted">Final Answer</div>
          <p className="mt-3 whitespace-pre-wrap text-sm text-white">{run.final_output || "(no final answer recorded)"}</p>
        </motion.section>

        <section className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[24px] border border-line bg-white/5 p-5">
            <div className="mb-3 flex items-center gap-2 text-sm text-white">
              <Workflow className="h-4 w-4 text-accent" />
              RL transitions
            </div>
            <div className="grid max-h-[520px] gap-3 overflow-y-auto pr-1">
              {run.transitions.map((transition) => (
                <details
                  key={`${transition.step}-${transition.stage}`}
                  className="rounded-[20px] border border-white/10 bg-[#09111d] p-4"
                >
                  <summary className="cursor-pointer list-none text-sm text-white">
                    {transition.step}. {transition.stage} • status {transition.status ?? "n/a"} • reward{" "}
                    {transition.reward ?? "n/a"}
                  </summary>
                  <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs text-muted">
                    {JSON.stringify(
                      {
                        state: transition.state,
                        action: transition.action,
                        observation: transition.observation,
                        attributes: transition.attributes
                      },
                      null,
                      2
                    )}
                  </pre>
                </details>
              ))}
            </div>
          </div>

          <div className="rounded-[24px] border border-line bg-white/5 p-5">
            <div className="mb-3 flex items-center gap-2 text-sm text-white">
              <MessageSquareWarning className="h-4 w-4 text-gold" />
              Feedback
            </div>
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  onClick={() => onSubmitFeedback({ rating: 5, notes })}
                  disabled={feedbackPending}
                >
                  Useful
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => onSubmitFeedback({ rating: 2, notes })}
                  disabled={feedbackPending}
                >
                  Needs work
                </Button>
              </div>
              <Textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Optional notes for this run"
                className="min-h-28"
              />
              {run.user_feedback ? (
                <div className="rounded-[20px] border border-white/10 bg-[#09111d] p-4 text-sm text-muted">
                  Stored feedback: rating {run.user_feedback.rating ?? "n/a"}
                  {run.user_feedback.notes ? ` • ${run.user_feedback.notes}` : ""}
                </div>
              ) : null}
            </div>
          </div>
        </section>

        <section className="rounded-[24px] border border-line bg-white/5 p-5">
          <div className="mb-3 text-sm text-white">Trace events</div>
          <div className="grid max-h-[520px] gap-3 overflow-y-auto pr-1">
            {run.events.map((event) => (
              <details
                key={`${event.step}-${event.kind}-${event.name}`}
                className="rounded-[20px] border border-white/10 bg-[#09111d] p-4"
              >
                <summary className="cursor-pointer list-none text-sm text-white">
                  {event.step}. {event.kind} • {event.name ?? "event"} • {event.latency_ms ?? 0} ms
                </summary>
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs text-muted">
                  {JSON.stringify(
                    {
                      input: event.input,
                      output: event.output,
                      attributes: event.attributes,
                      error: event.error
                    },
                    null,
                    2
                  )}
                </pre>
              </details>
            ))}
          </div>
        </section>
      </CardContent>
    </Card>
  );
}
