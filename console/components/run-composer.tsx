"use client";

import { WandSparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

const SAMPLE_PROMPTS = [
  "Calculate 19 * 17 and tell me whether the tool call was necessary.",
  "Using stored notes, what database powers agentos-core by default?",
  "Is 37 a prime number? Answer carefully.",
  "Tell me what the trace_events table captures in this runtime."
];

type RunComposerProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  isPending: boolean;
  statusText: string;
};

export function RunComposer({
  value,
  onChange,
  onSubmit,
  isPending,
  statusText
}: RunComposerProps) {
  return (
    <Card className="p-6">
      <CardHeader>
        <div>
          <CardTitle>Launch A Run</CardTitle>
          <CardDescription>
            Send a prompt through the planner, tools, verifier, reflection loop, and memory stack.
          </CardDescription>
        </div>
        <div className="rounded-full border border-white/10 bg-white/5 p-3 text-accent">
          <WandSparkles className="h-5 w-5" />
        </div>
      </CardHeader>
      <CardContent>
        <Textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Ask something that exercises planning, memory, or tools."
        />
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button onClick={onSubmit} disabled={isPending}>
            {isPending ? "Running..." : "Run Agent"}
          </Button>
          <span className="text-sm text-muted">{statusText}</span>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {SAMPLE_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => onChange(prompt)}
              className="rounded-3xl border border-line bg-white/5 px-4 py-4 text-left text-sm text-muted transition hover:border-accent/60 hover:bg-white/10"
            >
              {prompt}
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
