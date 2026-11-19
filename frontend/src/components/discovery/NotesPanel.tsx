import { useMemo, useState } from "react";
import {
  Plus,
  Trash2,
  Edit2,
  Sparkles,
  AlertTriangle,
  Loader2,
  CheckSquare,
  Square,
} from "lucide-react";
import { Button, Card, Eyebrow } from "../ui";
import type { InterviewNote } from "../../lib/api";

export interface NotesPanelProps {
  notes: InterviewNote[];
  selectedNoteIds: number[];
  onToggleSelectNote: (noteId: number) => void;
  onSelectAllNotes: () => void;
  onDeselectAllNotes: () => void;
  onCreateNote: (input: { title: string; content: string }) => Promise<void>;
  onUpdateNote: (noteId: number, input: { title: string; content: string }) => Promise<void>;
  onDeleteNote: (noteId: number) => Promise<void>;
  onAnalyse: () => void;
  isAnalysing: boolean;
  llmConfigured?: boolean;
}

const MAX_COMBINED_CHARS = 30000;

export function NotesPanel({
  notes,
  selectedNoteIds,
  onToggleSelectNote,
  onSelectAllNotes,
  onDeselectAllNotes,
  onCreateNote,
  onUpdateNote,
  onDeleteNote,
  onAnalyse,
  isAnalysing,
  llmConfigured = true,
}: NotesPanelProps) {
  const [isCreating, setIsCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");

  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);

  const selectedNotes = useMemo(() => {
    const set = new Set(selectedNoteIds);
    return notes.filter((n) => set.has(n.id));
  }, [notes, selectedNoteIds]);

  const selectedChars = useMemo(() => {
    return selectedNotes.reduce(
      (sum, n) => sum + (n.title?.length || 0) + (n.content?.length || 0),
      0
    );
  }, [selectedNotes]);

  const isOverCharLimit = selectedChars > MAX_COMBINED_CHARS;

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newTitle.trim() || !newContent.trim()) return;
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await onCreateNote({ title: newTitle.trim(), content: newContent.trim() });
      setNewTitle("");
      setNewContent("");
      setIsCreating(false);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to create note");
    } finally {
      setIsSubmitting(false);
    }
  }

  function startEdit(note: InterviewNote) {
    setEditingNoteId(note.id);
    setEditTitle(note.title);
    setEditContent(note.content);
  }

  async function handleSaveEdit(noteId: number) {
    if (!editTitle.trim() || !editContent.trim()) return;
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await onUpdateNote(noteId, { title: editTitle.trim(), content: editContent.trim() });
      setEditingNoteId(null);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to update note");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete(noteId: number) {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await onDeleteNote(noteId);
      setConfirmDeleteId(null);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to delete note");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card className="p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <Eyebrow>Source Evidence</Eyebrow>
          <h3 className="font-serif text-lg font-medium text-stone-900">
            Interview Notes
          </h3>
        </div>
        <Button
          variant="secondary"
          onClick={() => {
            setIsCreating(!isCreating);
            setErrorMsg(null);
          }}
          disabled={isAnalysing}
        >
          <Plus className="w-3.5 h-3.5 mr-1" />
          Add note
        </Button>
      </div>

      {errorMsg && (
        <div className="p-2.5 text-xs text-red-700 bg-red-50 border border-red-200 rounded">
          {errorMsg}
        </div>
      )}

      {/* Creation form */}
      {isCreating && (
        <form onSubmit={handleCreate} className="p-3 bg-stone-50 border border-stone-200 rounded flex flex-col gap-2.5">
          <input
            type="text"
            className="w-full text-xs px-2.5 py-1.5 border border-stone-300 rounded bg-white focus:outline-none focus:border-stone-900"
            placeholder="Interview title (e.g., Head of Support Interview)"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            disabled={isSubmitting}
            required
          />
          <textarea
            className="w-full text-xs px-2.5 py-1.5 border border-stone-300 rounded bg-white h-24 focus:outline-none focus:border-stone-900 resize-y"
            placeholder="Paste verbatim interview notes, client quotes, and qualitative observations..."
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            disabled={isSubmitting}
            required
          />
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="tertiary"
              onClick={() => setIsCreating(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || !newTitle.trim() || !newContent.trim()}
            >
              {isSubmitting ? "Saving..." : "Save note"}
            </Button>
          </div>
        </form>
      )}

      {/* Selection controls */}
      {notes.length > 0 && (
        <div className="flex items-center justify-between text-xs text-stone-600 border-b border-stone-100 pb-2">
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="text-stone-700 hover:text-stone-900 underline text-xs"
              onClick={selectedNotes.length === notes.length ? onDeselectAllNotes : onSelectAllNotes}
            >
              {selectedNotes.length === notes.length ? "Deselect all" : "Select all"}
            </button>
            <span>•</span>
            <span>
              {selectedNotes.length} of {notes.length} selected
            </span>
          </div>
          <span className={isOverCharLimit ? "text-red-600 font-medium" : "text-stone-500"}>
            {selectedChars.toLocaleString()} / {MAX_COMBINED_CHARS.toLocaleString()} chars
          </span>
        </div>
      )}

      {isOverCharLimit && (
        <div className="flex items-center gap-1.5 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          <span>Selected notes exceed the 30,000 character limit. Deselect notes to continue.</span>
        </div>
      )}

      {/* Notes list */}
      <div className="flex flex-col gap-2 max-h-[380px] overflow-y-auto pr-1">
        {notes.length === 0 ? (
          <div className="text-center py-6 text-stone-400 text-xs">
            No interview notes yet. Add notes to begin qualitative discovery.
          </div>
        ) : (
          notes.map((note) => {
            const isSelected = selectedNoteIds.includes(note.id);
            const wordCount = note.content
              ? note.content.trim().split(/\s+/).filter(Boolean).length
              : 0;
            const isEditing = editingNoteId === note.id;

            if (isEditing) {
              return (
                <div key={note.id} className="p-3 bg-stone-50 border border-stone-300 rounded flex flex-col gap-2">
                  <input
                    type="text"
                    className="text-xs px-2 py-1 border border-stone-300 rounded bg-white"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    disabled={isSubmitting}
                  />
                  <textarea
                    aria-label="Edit note content"
                    placeholder="Edit note content..."
                    className="text-xs px-2 py-1 border border-stone-300 rounded bg-white h-24 resize-y"
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    disabled={isSubmitting}
                  />
                  <div className="flex justify-end gap-1.5">
                    <Button
                      type="button"
                      variant="tertiary"
                      onClick={() => setEditingNoteId(null)}
                      disabled={isSubmitting}
                    >
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      onClick={() => handleSaveEdit(note.id)}
                      disabled={isSubmitting}
                    >
                      Save
                    </Button>
                  </div>
                </div>
              );
            }

            return (
              <div
                key={note.id}
                className={`p-3 rounded border transition-colors ${
                  isSelected
                    ? "border-stone-400 bg-stone-50/70"
                    : "border-stone-200 bg-white hover:border-stone-300"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => onToggleSelectNote(note.id)}
                    className="flex items-start gap-2 text-left flex-1"
                  >
                    <span className="mt-0.5 text-stone-700">
                      {isSelected ? (
                        <CheckSquare className="w-4 h-4 text-stone-900" />
                      ) : (
                        <Square className="w-4 h-4 text-stone-400" />
                      )}
                    </span>
                    <div>
                      <div className="font-medium text-xs text-stone-900">{note.title}</div>
                      <div className="text-[11px] text-stone-500 mt-0.5 line-clamp-2">
                        {note.content}
                      </div>
                    </div>
                  </button>
                  <div className="flex items-center gap-1 opacity-70 hover:opacity-100">
                    <button
                      type="button"
                      title="Edit note"
                      className="p-1 text-stone-500 hover:text-stone-900 rounded"
                      onClick={() => startEdit(note)}
                    >
                      <Edit2 className="w-3 h-3" />
                    </button>
                    <button
                      type="button"
                      title="Delete note"
                      className="p-1 text-stone-500 hover:text-red-700 rounded"
                      onClick={() => setConfirmDeleteId(note.id)}
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[10px] text-stone-400 mt-2 pt-1 border-t border-stone-100">
                  <span>{wordCount} words • {note.content.length} chars</span>
                  <span>{new Date(note.created_at).toLocaleDateString()}</span>
                </div>

                {/* Confirm Delete prompt */}
                {confirmDeleteId === note.id && (
                  <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs flex items-center justify-between">
                    <span className="text-red-800">Delete this note?</span>
                    <div className="flex gap-1.5">
                      <Button
                        variant="tertiary"
                        onClick={() => setConfirmDeleteId(null)}
                        disabled={isSubmitting}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="destructive"
                        onClick={() => handleDelete(note.id)}
                        disabled={isSubmitting}
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* AI Analysis action button */}
      <div className="pt-2 border-t border-stone-100">
        <Button
          variant="primary"
          className="w-full flex items-center justify-center gap-2"
          onClick={onAnalyse}
          disabled={
            selectedNotes.length === 0 ||
            isOverCharLimit ||
            isAnalysing ||
            !llmConfigured
          }
        >
          {isAnalysing ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Analyzing interview notes...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span>Analyse {selectedNotes.length} selected note{selectedNotes.length === 1 ? "" : "s"}</span>
            </>
          )}
        </Button>
        {!llmConfigured && (
          <p className="text-[11px] text-stone-500 text-center mt-1.5">
            Configure LLM_API_KEY in .env to enable AI discovery analysis.
          </p>
        )}
      </div>
    </Card>
  );
}
