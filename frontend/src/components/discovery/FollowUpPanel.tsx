import { useState } from "react";
import { HelpCircle, Plus, Trash2 } from "lucide-react";
import { Button, Card, Eyebrow } from "../ui";
import type { QuestionItem } from "../../lib/api";

export interface FollowUpPanelProps {
  questions: QuestionItem[];
  onChange: (questions: QuestionItem[]) => void;
  disabled?: boolean;
}

export function FollowUpPanel({
  questions,
  onChange,
  disabled = false,
}: FollowUpPanelProps) {
  const [newQuestionText, setNewQuestionText] = useState("");
  const [isAdding, setIsAdding] = useState(false);

  function handleStatusChange(idx: number, status: "open" | "asked" | "answered") {
    const updated = [...questions];
    updated[idx] = {
      ...updated[idx],
      status,
      status_reason: status === "answered" ? "Answer recorded" : undefined,
    };
    onChange(updated);
  }

  function handleAnswerChange(idx: number, answer: string) {
    const updated = [...questions];
    updated[idx] = {
      ...updated[idx],
      answer,
    };
    onChange(updated);
  }

  function handleDelete(idx: number) {
    const updated = questions.filter((_, i) => i !== idx);
    onChange(updated);
  }

  function handleAdd() {
    if (!newQuestionText.trim()) return;
    const item: QuestionItem = {
      id: Math.random().toString(36).substring(2, 10),
      question: newQuestionText.trim(),
      status: "open",
    };
    onChange([...questions, item]);
    setNewQuestionText("");
    setIsAdding(false);
  }

  return (
    <Card className="p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <HelpCircle className="w-4 h-4 text-stone-700" />
          <Eyebrow>Follow-up Questions</Eyebrow>
        </div>
        <Button
          variant="secondary"
          className="h-6 px-2 text-[11px]"
          onClick={() => setIsAdding(!isAdding)}
          disabled={disabled || questions.length >= 12}
        >
          <Plus className="w-3 h-3 mr-1" />
          Add
        </Button>
      </div>

      {isAdding && (
        <div className="p-2.5 bg-stone-50 border border-stone-200 rounded flex flex-col gap-2">
          <input
            type="text"
            className="w-full text-xs px-2 py-1 border border-stone-300 rounded bg-white"
            placeholder="Type a follow-up interview question..."
            value={newQuestionText}
            onChange={(e) => setNewQuestionText(e.target.value)}
            disabled={disabled}
            autoFocus
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
              disabled={!newQuestionText.trim()}
            >
              Add question
            </Button>
          </div>
        </div>
      )}

      {questions.length === 0 ? (
        <div className="text-center py-4 text-stone-400 text-xs">
          No follow-up questions recorded.
        </div>
      ) : (
        <div className="flex flex-col gap-2 max-h-[300px] overflow-y-auto pr-1">
          {questions.map((q, idx) => {
            const isAnswered = q.status === "answered";
            return (
              <div
                key={q.id || idx}
                className="p-2.5 bg-white border border-stone-200 rounded text-xs flex flex-col gap-1.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium text-stone-900 flex-1">{q.question}</span>
                  <button
                    type="button"
                    title="Remove question"
                    className="text-stone-400 hover:text-red-700 p-0.5"
                    onClick={() => handleDelete(idx)}
                    disabled={disabled}
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>

                <div className="flex items-center gap-2 text-[11px]">
                  <span className="text-stone-500">Status:</span>
                  <select
                    className="border border-stone-300 rounded px-1.5 py-0.5 bg-stone-50 text-[11px]"
                    value={q.status}
                    onChange={(e) =>
                      handleStatusChange(
                        idx,
                        e.target.value as "open" | "asked" | "answered"
                      )
                    }
                    disabled={disabled}
                  >
                    <option value="open">Open</option>
                    <option value="asked">Asked</option>
                    <option value="answered">Answered</option>
                  </select>
                </div>

                {isAnswered && (
                  <div className="mt-1 flex flex-col gap-1">
                    <span className="text-[10px] uppercase tracking-wider text-stone-400 font-medium">
                      Answer
                    </span>
                    <textarea
                      className="w-full text-xs px-2 py-1 border border-stone-300 rounded bg-stone-50 h-16 resize-y focus:bg-white"
                      placeholder="Record the client's answer or notes..."
                      value={q.answer || ""}
                      onChange={(e) => handleAnswerChange(idx, e.target.value)}
                      disabled={disabled}
                    />
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
