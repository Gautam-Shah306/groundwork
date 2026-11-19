import { useState } from "react";
import { Send, Sparkles, AlertCircle, Info, Copy } from "lucide-react";
import { Button } from "../ui/Button";
import {
  createTriageProposal,
  type AllowedChannel,
  type CreateProposalPayload,
  type TriageProposalResponse,
} from "../../lib/api";

export interface SubmitTicketFormProps {
  engagementId: number;
  llmConfigured: boolean;
  onProposalCreated: (proposal: TriageProposalResponse, isDuplicate: boolean) => void;
}

const EXAMPLE_TICKETS = [
  {
    label: "Damaged Lamp (Chat)",
    subject: "Damaged lamp arrived broken",
    body: "My order KL-5544 lamp arrived broken into pieces upon delivery. The outer box was crushed and the glass base is completely shattered. Can I please get an urgent replacement sent?",
    channel: "chat" as AllowedChannel,
  },
  {
    label: "Duplicate Charge (Email)",
    subject: "Billed twice for coffee table",
    body: "I noticed on my bank statement that I was charged twice for order KL-8921 on November 12th. Both charges are for $340.00. Please reverse the duplicate charge immediately.",
    channel: "email" as AllowedChannel,
  },
  {
    label: "Delayed Tracking (Web Form)",
    subject: "No update on tracking for 5 days",
    body: "Order KL-4412 tracking has been stuck at the regional distribution center for 5 days with no scans or movement. When will my package be delivered?",
    channel: "web_form" as AllowedChannel,
  },
];

export function SubmitTicketForm({
  engagementId,
  llmConfigured,
  onProposalCreated,
}: SubmitTicketFormProps) {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [channel, setChannel] = useState<AllowedChannel>("web_form");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [duplicateNotice, setDuplicateNotice] = useState<string | null>(null);

  const charCount = body.length;
  const isValidLength = charCount >= 5 && charCount <= 4000;

  const handleLoadExample = (ex: (typeof EXAMPLE_TICKETS)[0]) => {
    setSubject(ex.subject);
    setBody(ex.body);
    setChannel(ex.channel);
    setErrorMessage(null);
    setDuplicateNotice(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidLength || isSubmitting || !llmConfigured) return;

    setIsSubmitting(true);
    setErrorMessage(null);
    setDuplicateNotice(null);

    try {
      const payload: CreateProposalPayload = {
        subject: subject.trim() || undefined,
        body: body.trim(),
        channel,
      };

      const res = await createTriageProposal(engagementId, payload);
      if (res.duplicate) {
        setDuplicateNotice("This ticket already has an existing proposal. Loaded existing record.");
      }
      onProposalCreated(res.proposal, res.duplicate);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate triage proposal.";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="rounded border border-neutral-200 bg-white p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-neutral-900">Submit Inbound Ticket</h2>
          <p className="text-[11px] text-neutral-500">
            Submit a raw customer inquiry to run the deterministic + AI triage pipeline.
          </p>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-neutral-400 font-medium mr-1 hidden sm:inline">Examples:</span>
          {EXAMPLE_TICKETS.map((ex, i) => (
            <Button
              key={i}
              type="button"
              variant="secondary"
              disabled={!llmConfigured || isSubmitting}
              onClick={() => handleLoadExample(ex)}
              className="text-[10px] px-2 py-0.5"
            >
              <Copy size={10} className="mr-1" aria-hidden="true" />
              {ex.label.split(" ")[0]}
            </Button>
          ))}
        </div>
      </div>

      {!llmConfigured && (
        <div className="rounded border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-800 flex items-start gap-2">
          <AlertCircle size={15} className="text-amber-600 shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <span className="font-semibold block">Assistant not configured</span>
            <p className="text-[11px] text-amber-700">
              Set <code className="font-mono bg-amber-100 px-1 rounded">LLM_API_KEY</code> and{" "}
              <code className="font-mono bg-amber-100 px-1 rounded">LLM_MODEL</code> in your local .env
              file and restart the backend to generate proposals.
            </p>
          </div>
        </div>
      )}

      {errorMessage && (
        <div className="rounded border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-800 flex items-center gap-2">
          <AlertCircle size={14} className="text-rose-600 shrink-0" aria-hidden="true" />
          <span>{errorMessage}</span>
        </div>
      )}

      {duplicateNotice && (
        <div className="rounded border border-sky-200 bg-sky-50 p-2.5 text-xs text-sky-800 flex items-center gap-2">
          <Info size={14} className="text-sky-600 shrink-0" aria-hidden="true" />
          <span>{duplicateNotice}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
        <div className="md:col-span-2">
          <label htmlFor="ticket-subject" className="block text-[11px] font-medium text-neutral-700 mb-1">
            Subject <span className="text-neutral-400 font-normal">(Optional, max 200 chars)</span>
          </label>
          <input
            id="ticket-subject"
            type="text"
            maxLength={200}
            disabled={!llmConfigured || isSubmitting}
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="e.g. Order KL-5544 damaged upon delivery"
            className="w-full rounded border border-neutral-300 bg-white p-2 text-xs text-neutral-800 focus:outline-none focus:ring-1 focus:ring-neutral-400 disabled:bg-neutral-50 disabled:cursor-not-allowed"
          />
        </div>

        <div>
          <label htmlFor="ticket-channel" className="block text-[11px] font-medium text-neutral-700 mb-1">
            Channel
          </label>
          <select
            id="ticket-channel"
            disabled={!llmConfigured || isSubmitting}
            value={channel}
            onChange={(e) => setChannel(e.target.value as AllowedChannel)}
            className="w-full rounded border border-neutral-300 bg-white p-2 text-xs text-neutral-800 focus:outline-none focus:ring-1 focus:ring-neutral-400 disabled:bg-neutral-50 disabled:cursor-not-allowed"
          >
            <option value="web_form">web_form</option>
            <option value="email">email</option>
            <option value="chat">chat</option>
            <option value="whatsapp">whatsapp</option>
          </select>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between text-[11px] font-medium text-neutral-700 mb-1">
          <label htmlFor="ticket-body">
            Ticket Body <span className="text-rose-500">*</span>
          </label>
          <span
            className={`font-mono text-[10px] ${
              charCount > 4000 ? "text-rose-600 font-semibold" : "text-neutral-400"
            }`}
          >
            {charCount} / 4000 chars {charCount < 5 && charCount > 0 ? "(min 5)" : ""}
          </span>
        </div>
        <textarea
          id="ticket-body"
          rows={4}
          required
          disabled={!llmConfigured || isSubmitting}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Paste or write customer inquiry text here (English or Hinglish)..."
          className="w-full rounded border border-neutral-300 bg-white p-2 text-xs text-neutral-800 leading-relaxed font-sans focus:outline-none focus:ring-1 focus:ring-neutral-400 disabled:bg-neutral-50 disabled:cursor-not-allowed"
        />
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 border-t border-neutral-100">
        <p className="text-[11px] text-neutral-400 italic">
          The ticket text is sent to the configured AI provider.
        </p>
        <Button
          type="submit"
          variant="primary"
          disabled={!llmConfigured || isSubmitting || !isValidLength}
        >
          {isSubmitting ? (
            <>
              <Sparkles size={13} className="mr-1.5 animate-spin" aria-hidden="true" />
              Generating proposal...
            </>
          ) : (
            <>
              <Send size={13} className="mr-1.5" aria-hidden="true" />
              Generate Proposal
            </>
          )}
        </Button>
      </div>
    </form>
  );
}
