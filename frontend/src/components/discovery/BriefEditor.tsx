import { useEffect, useState } from "react";
import {
  Check,
  CheckCircle2,
  Plus,
  Quote,
  Save,
  Trash2,
} from "lucide-react";
import { Button, Card, Eyebrow, StatusPill } from "../ui";
import type {
  BriefItem,
  BriefSections,
  KnownFactItem,
  KpiCandidate,
} from "../../lib/api";

export interface BriefEditorProps {
  sections: BriefSections;
  source?: string;
  updatedAt?: string;
  onSave: (sections: BriefSections) => Promise<void>;
  isSaving: boolean;
}

const SECTION_CAPS: Record<string, number> = {
  themes: 8,
  stakeholders: 8,
  workflow_steps: 8,
  symptoms: 8,
  impact: 8,
  known_facts: 12,
  hypotheses: 8,
  assumptions: 8,
  unknowns: 8,
  candidate_kpis: 5,
};

function renderItemStatus(item: { origin?: string; status?: string }) {
  if (item.status === "confirmed") {
    return <StatusPill variant="success" label="Confirmed" />;
  }
  if (item.status === "user_edited" || item.origin === "user") {
    return <StatusPill variant="neutral" label="Edited by you" />;
  }
  return <StatusPill variant="warning" label="AI draft" />;
}

export function BriefEditor({
  sections: initialSections,
  source = "edited",
  updatedAt,
  onSave,
  isSaving,
}: BriefEditorProps) {
  const [sections, setSections] = useState<BriefSections>(initialSections);
  const [isDirty, setIsDirty] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Sync with initialSections when updated from outside
  useEffect(() => {
    setSections(initialSections);
    setIsDirty(false);
  }, [initialSections]);

  // Guard beforeunload when dirty
  useEffect(() => {
    function handleBeforeUnload(e: BeforeUnloadEvent) {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  function updateContext(val: string) {
    setSections((prev) => ({ ...prev, context: val }));
    setIsDirty(true);
    setSaveSuccess(false);
  }

  function updateProblemStatement(val: string) {
    setSections((prev) => ({
      ...prev,
      problem_statement: {
        ...prev.problem_statement,
        text: val,
        status: "user_edited",
      },
    }));
    setIsDirty(true);
    setSaveSuccess(false);
  }

  function updateItem<T extends BriefItem>(
    section: keyof BriefSections,
    idx: number,
    patch: Partial<T>
  ) {
    setSections((prev) => {
      const list = [...(prev[section] as unknown as T[])];
      list[idx] = { ...list[idx], ...patch, status: patch.status ?? "user_edited" };
      return { ...prev, [section]: list };
    });
    setIsDirty(true);
    setSaveSuccess(false);
  }

  function toggleConfirmItem(section: keyof BriefSections, idx: number) {
    setSections((prev) => {
      const list = [...(prev[section] as unknown as BriefItem[])];
      const cur = list[idx];
      const nextStatus = cur.status === "confirmed" ? "user_edited" : "confirmed";
      list[idx] = { ...cur, status: nextStatus };
      return { ...prev, [section]: list };
    });
    setIsDirty(true);
    setSaveSuccess(false);
  }

  function removeItem(section: keyof BriefSections, idx: number) {
    setSections((prev) => {
      const list = (prev[section] as unknown as unknown[]).filter((_, i) => i !== idx);
      return { ...prev, [section]: list };
    });
    setIsDirty(true);
    setSaveSuccess(false);
  }

  function addItem(section: keyof BriefSections, newItem: unknown) {
    setSections((prev) => {
      const list = [...(prev[section] as unknown as unknown[]), newItem];
      return { ...prev, [section]: list };
    });
    setIsDirty(true);
    setSaveSuccess(false);
  }

  async function handleSave() {
    setErrorMsg(null);
    try {
      await onSave(sections);
      setIsDirty(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to save brief");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Top action header */}
      <div className="flex items-center justify-between border-b border-stone-200 pb-3">
        <div className="flex items-center gap-3">
          <Eyebrow>Editable Document</Eyebrow>
          <StatusPill
            variant={source === "ai_draft" ? "warning" : "neutral"}
            label={source === "ai_draft" ? "AI draft" : "Edited by you"}
          />
          {isDirty && (
            <StatusPill variant="warning" label="Unsaved changes" />
          )}
          {saveSuccess && (
            <span className="flex items-center gap-1 text-xs text-emerald-700 font-medium">
              <Check className="w-3.5 h-3.5" /> Saved
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {updatedAt && (
            <span className="text-[11px] text-stone-400">
              Updated {new Date(updatedAt).toLocaleTimeString()}
            </span>
          )}
          <Button
            variant="primary"
            onClick={handleSave}
            disabled={!isDirty || isSaving}
          >
            <Save className="w-3.5 h-3.5 mr-1.5" />
            {isSaving ? "Saving..." : "Save changes"}
          </Button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 text-xs bg-red-50 border border-red-200 text-red-700 rounded">
          {errorMsg}
        </div>
      )}

      {/* Problem Statement Card */}
      <Card className="p-5 border-stone-300 bg-white flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div>
            <Eyebrow>Focus</Eyebrow>
            <h3 className="font-serif text-lg font-medium text-stone-900">
              Problem Statement
            </h3>
          </div>
          {renderItemStatus(sections.problem_statement || {})}
        </div>
        <p className="text-[11px] text-stone-500 font-mono bg-stone-50 p-2 rounded border border-stone-200">
          Template: [Who] experience [problem] in [context], affecting [outcome]; improvement will be judged by [candidate measure(s)]
        </p>
        <textarea
          className="w-full text-sm font-serif p-2.5 border border-stone-300 rounded bg-white focus:outline-none focus:border-stone-900 resize-y min-h-[70px]"
          placeholder="State the testable problem statement without causal language..."
          value={sections.problem_statement?.text || ""}
          onChange={(e) => updateProblemStatement(e.target.value)}
        />
      </Card>

      {/* Context Card */}
      <Card className="p-5 border-stone-200 bg-white flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h4 className="font-serif text-base font-medium text-stone-900">
            Context Summary
          </h4>
          <span className="text-[11px] text-stone-400">
            {(sections.context || "").length} / 1500 chars
          </span>
        </div>
        <textarea
          className="w-full text-xs p-2.5 border border-stone-300 rounded bg-white focus:outline-none focus:border-stone-900 resize-y min-h-[80px]"
          placeholder="Summarize client background, operations scale, and initial situation..."
          value={sections.context || ""}
          onChange={(e) => updateContext(e.target.value)}
          maxLength={1500}
        />
      </Card>

      {/* Themes Section */}
      <GenericItemSection
        title="Key Themes"
        section="themes"
        items={sections.themes || []}
        cap={SECTION_CAPS.themes}
        onUpdateItem={(idx, patch) => updateItem("themes", idx, patch)}
        onToggleConfirm={(idx) => toggleConfirmItem("themes", idx)}
        onRemoveItem={(idx) => removeItem("themes", idx)}
        onAddItem={(text, quote) =>
          addItem("themes", {
            id: Math.random().toString(36).substring(2, 10),
            text,
            source_quote: quote || null,
            origin: "user",
            status: "user_edited",
          })
        }
      />

      {/* Symptoms & Impact */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <GenericItemSection
          title="Symptoms"
          section="symptoms"
          items={sections.symptoms || []}
          cap={SECTION_CAPS.symptoms}
          onUpdateItem={(idx, patch) => updateItem("symptoms", idx, patch)}
          onToggleConfirm={(idx) => toggleConfirmItem("symptoms", idx)}
          onRemoveItem={(idx) => removeItem("symptoms", idx)}
          onAddItem={(text, quote) =>
            addItem("symptoms", {
              id: Math.random().toString(36).substring(2, 10),
              text,
              source_quote: quote || null,
              origin: "user",
              status: "user_edited",
            })
          }
        />

        <GenericItemSection
          title="Business Impact"
          section="impact"
          items={sections.impact || []}
          cap={SECTION_CAPS.impact}
          onUpdateItem={(idx, patch) => updateItem("impact", idx, patch)}
          onToggleConfirm={(idx) => toggleConfirmItem("impact", idx)}
          onRemoveItem={(idx) => removeItem("impact", idx)}
          onAddItem={(text, quote) =>
            addItem("impact", {
              id: Math.random().toString(36).substring(2, 10),
              text,
              source_quote: quote || null,
              origin: "user",
              status: "user_edited",
            })
          }
        />
      </div>

      {/* Stakeholders & Workflow Steps */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <GenericItemSection
          title="Stakeholders"
          section="stakeholders"
          items={sections.stakeholders || []}
          cap={SECTION_CAPS.stakeholders}
          onUpdateItem={(idx, patch) => updateItem("stakeholders", idx, patch)}
          onToggleConfirm={(idx) => toggleConfirmItem("stakeholders", idx)}
          onRemoveItem={(idx) => removeItem("stakeholders", idx)}
          onAddItem={(text, quote) =>
            addItem("stakeholders", {
              id: Math.random().toString(36).substring(2, 10),
              text,
              source_quote: quote || null,
              origin: "user",
              status: "user_edited",
            })
          }
        />

        <GenericItemSection
          title="Workflow Steps"
          section="workflow_steps"
          items={sections.workflow_steps || []}
          cap={SECTION_CAPS.workflow_steps}
          onUpdateItem={(idx, patch) => updateItem("workflow_steps", idx, patch)}
          onToggleConfirm={(idx) => toggleConfirmItem("workflow_steps", idx)}
          onRemoveItem={(idx) => removeItem("workflow_steps", idx)}
          onAddItem={(text, quote) =>
            addItem("workflow_steps", {
              id: Math.random().toString(36).substring(2, 10),
              text,
              source_quote: quote || null,
              origin: "user",
              status: "user_edited",
            })
          }
        />
      </div>

      {/* Known Facts (with type selector and source requirement for observed_fact) */}
      <KnownFactsSection
        items={sections.known_facts || []}
        cap={SECTION_CAPS.known_facts}
        onUpdateItem={(idx, patch) => updateItem("known_facts", idx, patch)}
        onToggleConfirm={(idx) => toggleConfirmItem("known_facts", idx)}
        onRemoveItem={(idx) => removeItem("known_facts", idx)}
        onAddItem={(item) => addItem("known_facts", item)}
      />

      {/* Hypotheses (carries Needs validation pill) */}
      <GenericItemSection
        title="Hypotheses"
        section="hypotheses"
        items={sections.hypotheses || []}
        cap={SECTION_CAPS.hypotheses}
        badge={<StatusPill variant="warning" label="Needs validation" />}
        onUpdateItem={(idx, patch) => updateItem("hypotheses", idx, patch)}
        onToggleConfirm={(idx) => toggleConfirmItem("hypotheses", idx)}
        onRemoveItem={(idx) => removeItem("hypotheses", idx)}
        onAddItem={(text, quote) =>
          addItem("hypotheses", {
            id: Math.random().toString(36).substring(2, 10),
            text,
            source_quote: quote || null,
            origin: "user",
            status: "user_edited",
          })
        }
      />

      {/* Assumptions & Unknowns */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <GenericItemSection
          title="Assumptions"
          section="assumptions"
          items={sections.assumptions || []}
          cap={SECTION_CAPS.assumptions}
          onUpdateItem={(idx, patch) => updateItem("assumptions", idx, patch)}
          onToggleConfirm={(idx) => toggleConfirmItem("assumptions", idx)}
          onRemoveItem={(idx) => removeItem("assumptions", idx)}
          onAddItem={(text) =>
            addItem("assumptions", {
              id: Math.random().toString(36).substring(2, 10),
              text,
              origin: "user",
              status: "user_edited",
            })
          }
        />

        <GenericItemSection
          title="Unknowns"
          section="unknowns"
          items={sections.unknowns || []}
          cap={SECTION_CAPS.unknowns}
          onUpdateItem={(idx, patch) => updateItem("unknowns", idx, patch)}
          onToggleConfirm={(idx) => toggleConfirmItem("unknowns", idx)}
          onRemoveItem={(idx) => removeItem("unknowns", idx)}
          onAddItem={(text) =>
            addItem("unknowns", {
              id: Math.random().toString(36).substring(2, 10),
              text,
              origin: "user",
              status: "user_edited",
            })
          }
        />
      </div>

      {/* Candidate KPIs */}
      <CandidateKpisSection
        items={sections.candidate_kpis || []}
        cap={SECTION_CAPS.candidate_kpis}
        onRemoveItem={(idx) => removeItem("candidate_kpis", idx)}
        onAddItem={(kpi) => addItem("candidate_kpis", kpi)}
      />
    </div>
  );
}

// ----------------- Subsections -----------------

interface GenericItemSectionProps {
  title: string;
  section: string;
  items: BriefItem[];
  cap: number;
  badge?: React.ReactNode;
  onUpdateItem: (idx: number, patch: Partial<BriefItem>) => void;
  onToggleConfirm: (idx: number) => void;
  onRemoveItem: (idx: number) => void;
  onAddItem: (text: string, quote?: string) => void;
}

function GenericItemSection({
  title,
  items,
  cap,
  badge,
  onUpdateItem,
  onToggleConfirm,
  onRemoveItem,
  onAddItem,
}: GenericItemSectionProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [newText, setNewText] = useState("");
  const [newQuote, setNewQuote] = useState("");

  function handleAdd() {
    if (!newText.trim()) return;
    onAddItem(newText.trim(), newQuote.trim() || undefined);
    setNewText("");
    setNewQuote("");
    setIsAdding(false);
  }

  return (
    <Card className="p-5 border-stone-200 bg-white flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h4 className="font-serif text-base font-medium text-stone-900">{title}</h4>
          {badge}
          <span className="text-[11px] text-stone-400">
            {items.length} / {cap}
          </span>
        </div>
        <Button
          variant="secondary"
          className="h-6 px-2 text-[11px]"
          onClick={() => setIsAdding(!isAdding)}
          disabled={items.length >= cap}
        >
          <Plus className="w-3 h-3 mr-1" /> Add
        </Button>
      </div>

      {isAdding && (
        <div className="p-2.5 bg-stone-50 border border-stone-200 rounded flex flex-col gap-2">
          <input
            type="text"
            className="w-full text-xs px-2 py-1 border border-stone-300 rounded bg-white"
            placeholder="Item text..."
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            autoFocus
          />
          <input
            type="text"
            className="w-full text-xs px-2 py-1 border border-stone-300 rounded bg-white"
            placeholder="Verbatim source quote (optional)..."
            value={newQuote}
            onChange={(e) => setNewQuote(e.target.value)}
          />
          <div className="flex justify-end gap-1.5">
            <Button
              variant="tertiary"
              className="h-6 px-2 text-[11px]"
              onClick={() => setIsAdding(false)}
            >
              Cancel
            </Button>
            <Button
              className="h-6 px-2 text-[11px]"
              onClick={handleAdd}
              disabled={!newText.trim()}
            >
              Add
            </Button>
          </div>
        </div>
      )}

      {items.length === 0 ? (
        <span className="text-xs text-stone-400 italic">None recorded.</span>
      ) : (
        <div className="flex flex-col gap-2">
          {items.map((it, idx) => (
            <div
              key={it.id || idx}
              className="p-2.5 bg-white border border-stone-200 rounded flex flex-col gap-1.5 text-xs"
            >
              <div className="flex items-start justify-between gap-2">
                <input
                  type="text"
                  className="flex-1 font-medium text-stone-900 bg-transparent border-b border-transparent hover:border-stone-300 focus:border-stone-900 focus:outline-none px-1 py-0.5"
                  value={it.text}
                  onChange={(e) => onUpdateItem(idx, { text: e.target.value })}
                />
                <div className="flex items-center gap-1 flex-shrink-0">
                  {renderItemStatus(it)}
                  <button
                    type="button"
                    title={it.status === "confirmed" ? "Unconfirm" : "Confirm this item"}
                    className={`p-1 rounded ${
                      it.status === "confirmed"
                        ? "text-emerald-700 bg-emerald-50"
                        : "text-stone-400 hover:text-stone-900"
                    }`}
                    onClick={() => onToggleConfirm(idx)}
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    title="Remove item"
                    className="p-1 text-stone-400 hover:text-red-700"
                    onClick={() => onRemoveItem(idx)}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {it.source_quote !== undefined && (
                <div className="flex items-center gap-1.5 text-[11px] text-stone-500 pl-1">
                  <Quote className="w-3 h-3 text-stone-400 flex-shrink-0" />
                  <input
                    type="text"
                    className="flex-1 italic bg-transparent border-b border-transparent hover:border-stone-200 focus:border-stone-400 focus:outline-none"
                    placeholder="Verbatim quote..."
                    value={it.source_quote || ""}
                    onChange={(e) => onUpdateItem(idx, { source_quote: e.target.value })}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ----------------- Known Facts Section -----------------

interface KnownFactsSectionProps {
  items: KnownFactItem[];
  cap: number;
  onUpdateItem: (idx: number, patch: Partial<KnownFactItem>) => void;
  onToggleConfirm: (idx: number) => void;
  onRemoveItem: (idx: number) => void;
  onAddItem: (item: KnownFactItem) => void;
}

function KnownFactsSection({
  items,
  cap,
  onUpdateItem,
  onToggleConfirm,
  onRemoveItem,
  onAddItem,
}: KnownFactsSectionProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [newText, setNewText] = useState("");
  const [newType, setNewType] = useState<"client_statement" | "observed_fact">("client_statement");
  const [newSource, setNewSource] = useState("");
  const [newQuote, setNewQuote] = useState("");

  function handleAdd() {
    if (!newText.trim()) return;
    if (newType === "observed_fact" && !newSource.trim()) return;

    onAddItem({
      id: Math.random().toString(36).substring(2, 10),
      text: newText.trim(),
      type: newType,
      source: newType === "observed_fact" ? newSource.trim() : undefined,
      source_quote: newQuote.trim() || null,
      origin: "user",
      status: "user_edited",
    });
    setNewText("");
    setNewSource("");
    setNewQuote("");
    setIsAdding(false);
  }

  return (
    <Card className="p-5 border-stone-200 bg-white flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h4 className="font-serif text-base font-medium text-stone-900">Known Facts</h4>
          <span className="text-[11px] text-stone-400">
            {items.length} / {cap}
          </span>
        </div>
        <Button
          variant="secondary"
          className="h-6 px-2 text-[11px]"
          onClick={() => setIsAdding(!isAdding)}
          disabled={items.length >= cap}
        >
          <Plus className="w-3 h-3 mr-1" /> Add
        </Button>
      </div>

      {isAdding && (
        <div className="p-3 bg-stone-50 border border-stone-200 rounded flex flex-col gap-2 text-xs">
          <input
            type="text"
            className="w-full text-xs px-2 py-1 border border-stone-300 rounded bg-white"
            placeholder="Fact statement..."
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            autoFocus
          />
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="radio"
                name="newFactType"
                value="client_statement"
                checked={newType === "client_statement"}
                onChange={() => setNewType("client_statement")}
              />
              <span>Client statement</span>
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="radio"
                name="newFactType"
                value="observed_fact"
                checked={newType === "observed_fact"}
                onChange={() => setNewType("observed_fact")}
              />
              <span>Observed fact (requires verified source)</span>
            </label>
          </div>
          {newType === "observed_fact" && (
            <input
              type="text"
              className="w-full text-xs px-2 py-1 border border-stone-300 rounded bg-white"
              placeholder="Verified source dataset or audit report..."
              value={newSource}
              onChange={(e) => setNewSource(e.target.value)}
              required
            />
          )}
          <input
            type="text"
            className="w-full text-xs px-2 py-1 border border-stone-300 rounded bg-white"
            placeholder="Verbatim quote (optional)..."
            value={newQuote}
            onChange={(e) => setNewQuote(e.target.value)}
          />
          <div className="flex justify-end gap-1.5">
            <Button
              variant="tertiary"
              className="h-6 px-2 text-[11px]"
              onClick={() => setIsAdding(false)}
            >
              Cancel
            </Button>
            <Button
              className="h-6 px-2 text-[11px]"
              onClick={handleAdd}
              disabled={!newText.trim() || (newType === "observed_fact" && !newSource.trim())}
            >
              Add
            </Button>
          </div>
        </div>
      )}

      {items.length === 0 ? (
        <span className="text-xs text-stone-400 italic">None recorded.</span>
      ) : (
        <div className="flex flex-col gap-2">
          {items.map((it, idx) => {
            const isObserved = it.type === "observed_fact";
            return (
              <div
                key={it.id || idx}
                className="p-2.5 bg-white border border-stone-200 rounded flex flex-col gap-1.5 text-xs"
              >
                <div className="flex items-start justify-between gap-2">
                  <input
                    type="text"
                    className="flex-1 font-medium text-stone-900 bg-transparent border-b border-transparent hover:border-stone-300 focus:border-stone-900 focus:outline-none px-1 py-0.5"
                    value={it.text}
                    onChange={(e) => onUpdateItem(idx, { text: e.target.value })}
                  />
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <select
                      className="border border-stone-300 rounded px-1.5 py-0.5 bg-stone-50 text-[11px]"
                      value={it.type}
                      onChange={(e) =>
                        onUpdateItem(idx, {
                          type: e.target.value as "client_statement" | "observed_fact",
                          source: e.target.value === "observed_fact" ? (it.source || "Quantitative data") : undefined,
                        })
                      }
                    >
                      <option value="client_statement">Client statement</option>
                      <option value="observed_fact">Observed fact</option>
                    </select>
                    {renderItemStatus(it)}
                    <button
                      type="button"
                      title={it.status === "confirmed" ? "Unconfirm" : "Confirm this fact"}
                      className={`p-1 rounded ${
                        it.status === "confirmed"
                          ? "text-emerald-700 bg-emerald-50"
                          : "text-stone-400 hover:text-stone-900"
                      }`}
                      onClick={() => onToggleConfirm(idx)}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      title="Remove fact"
                      className="p-1 text-stone-400 hover:text-red-700"
                      onClick={() => onRemoveItem(idx)}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {isObserved && (
                  <div className="flex items-center gap-1.5 text-[11px] text-stone-600 pl-1">
                    <span className="font-medium text-stone-500">Source:</span>
                    <input
                      type="text"
                      className="flex-1 bg-stone-50 px-1.5 py-0.5 rounded border border-stone-200 text-[11px]"
                      placeholder="Required source dataset or artifact..."
                      value={it.source || ""}
                      onChange={(e) => onUpdateItem(idx, { source: e.target.value })}
                      required
                    />
                  </div>
                )}

                {it.source_quote && (
                  <div className="text-[11px] text-stone-500 italic pl-1">
                    &ldquo;{it.source_quote}&rdquo;
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

// ----------------- Candidate KPIs Section -----------------

interface CandidateKpisSectionProps {
  items: KpiCandidate[];
  cap: number;
  onRemoveItem: (idx: number) => void;
  onAddItem: (kpi: KpiCandidate) => void;
}

const APPROVED_METRICS = [
  "first_response_time",
  "triage_time",
  "agent_response_time",
  "triage_share_of_first_response",
  "first_response_by_band",
  "resolution_time",
  "sla_attainment",
  "backlog_ageing",
  "reassignment_rate",
  "agent_workload",
  "volume_by_category",
  "volume_by_channel",
  "volume_by_day",
  "volume_by_hour",
  "volume_by_band",
  "factor_comparison",
];

function CandidateKpisSection({
  items,
  cap,
  onRemoveItem,
  onAddItem,
}: CandidateKpisSectionProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState(APPROVED_METRICS[0]);
  const [rationale, setRationale] = useState("");

  function handleAdd() {
    if (!selectedMetric) return;
    onAddItem({
      id: Math.random().toString(36).substring(2, 10),
      metric_id: selectedMetric,
      rationale: rationale.trim(),
      status: "user_edited",
    });
    setRationale("");
    setIsAdding(false);
  }

  return (
    <Card className="p-5 border-stone-200 bg-white flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h4 className="font-serif text-base font-medium text-stone-900">
            Candidate KPIs
          </h4>
          <span className="text-[11px] text-stone-400">
            {items.length} / {cap}
          </span>
        </div>
        <Button
          variant="secondary"
          className="h-6 px-2 text-[11px]"
          onClick={() => setIsAdding(!isAdding)}
          disabled={items.length >= cap}
        >
          <Plus className="w-3 h-3 mr-1" /> Add
        </Button>
      </div>

      {isAdding && (
        <div className="p-2.5 bg-stone-50 border border-stone-200 rounded flex flex-col gap-2 text-xs">
          <select
            className="w-full text-xs px-2 py-1 border border-stone-300 rounded bg-white font-mono"
            value={selectedMetric}
            onChange={(e) => setSelectedMetric(e.target.value)}
          >
            {APPROVED_METRICS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <input
            type="text"
            className="w-full text-xs px-2 py-1 border border-stone-300 rounded bg-white"
            placeholder="Rationale for tracking this metric..."
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
          />
          <div className="flex justify-end gap-1.5">
            <Button
              variant="tertiary"
              className="h-6 px-2 text-[11px]"
              onClick={() => setIsAdding(false)}
            >
              Cancel
            </Button>
            <Button
              className="h-6 px-2 text-[11px]"
              onClick={handleAdd}
            >
              Add KPI
            </Button>
          </div>
        </div>
      )}

      {items.length === 0 ? (
        <span className="text-xs text-stone-400 italic">None selected.</span>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {items.map((kpi, idx) => (
            <div
              key={kpi.id || idx}
              className="p-2.5 bg-white border border-stone-200 rounded flex items-start justify-between gap-2"
            >
              <div>
                <div className="font-mono text-xs font-semibold text-stone-900">
                  {kpi.metric_id}
                </div>
                {kpi.rationale && (
                  <div className="text-[11px] text-stone-600 mt-0.5">
                    {kpi.rationale}
                  </div>
                )}
              </div>
              <button
                type="button"
                title="Remove KPI"
                className="text-stone-400 hover:text-red-700 p-0.5"
                onClick={() => onRemoveItem(idx)}
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
