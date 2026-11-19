import { useState } from "react";
import { CheckCircle2, XCircle, ChevronDown, ChevronRight, Activity } from "lucide-react";
import type { PipelineTraceStep } from "../../lib/api";

export interface PipelineTraceProps {
  steps: PipelineTraceStep[];
}

export function PipelineTrace({ steps }: PipelineTraceProps) {
  const [expandedCalls, setExpandedCalls] = useState<Record<string, boolean>>({});

  const toggleCall = (callId: string) => {
    setExpandedCalls((prev) => ({ ...prev, [callId]: !prev[callId] }));
  };

  if (!steps || steps.length === 0) {
    return (
      <p className="text-xs text-neutral-500 italic">No pipeline trace records available.</p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-neutral-500">
        <Activity size={13} aria-hidden="true" />
        <span>Pipeline Execution Trace ({steps.length} steps)</span>
      </div>
      <div className="rounded border border-neutral-200 bg-white divide-y divide-neutral-100 text-xs">
        {steps.map((step) => {
          const isExpanded = !!expandedCalls[step.call_id];
          return (
            <div key={step.call_id} className="p-2.5">
              <button
                type="button"
                onClick={() => toggleCall(step.call_id)}
                className="w-full flex items-center justify-between text-left hover:text-neutral-900 focus:outline-none focus-visible:ring-1 focus-visible:ring-neutral-400 rounded"
                aria-expanded={isExpanded}
              >
                <div className="flex items-center gap-2">
                  {step.ok ? (
                    <CheckCircle2 size={14} className="text-emerald-600 shrink-0" aria-hidden="true" />
                  ) : (
                    <XCircle size={14} className="text-rose-600 shrink-0" aria-hidden="true" />
                  )}
                  <span className="font-mono font-medium text-neutral-800">{step.tool}</span>
                  <span className="text-[11px] text-neutral-400 font-mono">({step.call_id})</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-neutral-500 font-mono">{step.duration_ms}ms</span>
                  <span
                    className={`inline-block px-1.5 py-0.2 rounded text-[10px] font-semibold uppercase ${
                      step.ok
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : "bg-rose-50 text-rose-700 border border-rose-200"
                    }`}
                  >
                    {step.ok ? "Success" : "Failed"}
                  </span>
                  {isExpanded ? (
                    <ChevronDown size={14} className="text-neutral-400" aria-hidden="true" />
                  ) : (
                    <ChevronRight size={14} className="text-neutral-400" aria-hidden="true" />
                  )}
                </div>
              </button>

              {isExpanded && (
                <div className="mt-2.5 pt-2 border-t border-neutral-100 space-y-2 text-[11px] font-mono bg-neutral-50 p-2 rounded">
                  <div>
                    <span className="font-sans font-semibold text-neutral-500 uppercase tracking-wider text-[10px] block mb-1">
                      Arguments Summary (Redacted)
                    </span>
                    <pre className="overflow-x-auto text-neutral-700 whitespace-pre-wrap break-all">
                      {JSON.stringify(step.args, null, 2)}
                    </pre>
                  </div>
                  {step.data && (
                    <div>
                      <span className="font-sans font-semibold text-neutral-500 uppercase tracking-wider text-[10px] block mb-1">
                        Result Data
                      </span>
                      <pre className="overflow-x-auto text-neutral-700 whitespace-pre-wrap break-all">
                        {JSON.stringify(step.data, null, 2)}
                      </pre>
                    </div>
                  )}
                  {step.error && (
                    <div>
                      <span className="font-sans font-semibold text-rose-600 uppercase tracking-wider text-[10px] block mb-1">
                        Step Error
                      </span>
                      <pre className="overflow-x-auto text-rose-700 whitespace-pre-wrap break-all">
                        {JSON.stringify(step.error, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
