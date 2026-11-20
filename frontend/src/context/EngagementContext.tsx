import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  createEngagement as apiCreateEngagement,
  deleteEngagement as apiDeleteEngagement,
  fetchEngagements,
  type Engagement,
  type EngagementCreateInput,
} from "../lib/api";

export const ACTIVE_ENGAGEMENT_STORAGE_KEY = "groundwork.activeEngagementId";

export interface EngagementContextValue {
  engagements: Engagement[];
  loading: boolean;
  error: string | null;
  activeEngagementId: number | null;
  activeEngagement: Engagement | null;
  selectEngagement: (id: number) => void;
  refreshEngagements: () => Promise<void>;
  createEngagement: (input: EngagementCreateInput) => Promise<Engagement>;
  deleteEngagement: (id: number) => Promise<void>;
}

export const EngagementContext = createContext<EngagementContextValue | undefined>(
  undefined
);

function readStoredId(): number | null {
  try {
    const raw = window.localStorage.getItem(ACTIVE_ENGAGEMENT_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = Number.parseInt(raw, 10);
    return Number.isFinite(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function writeStoredId(id: number | null): void {
  try {
    if (id === null) {
      window.localStorage.removeItem(ACTIVE_ENGAGEMENT_STORAGE_KEY);
    } else {
      window.localStorage.setItem(ACTIVE_ENGAGEMENT_STORAGE_KEY, String(id));
    }
  } catch {
    // Ignore storage errors in restricted browser environments.
  }
}

function resolveActiveId(
  items: Engagement[],
  preferredId: number | null
): number | null {
  if (items.length === 0) {
    return null;
  }
  if (preferredId !== null && items.some((item) => item.id === preferredId)) {
    return preferredId;
  }
  return items[0].id;
}

export function EngagementProvider({ children }: { children: ReactNode }) {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeEngagementId, setActiveEngagementId] = useState<number | null>(
    () => readStoredId()
  );

  const loadEngagements = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const items = await fetchEngagements(signal);
      setEngagements(items);
      setActiveEngagementId((current) => {
        const stored = current ?? readStoredId();
        const nextId = resolveActiveId(items, stored);
        writeStoredId(nextId);
        return nextId;
      });
    } catch (err) {
      if (signal?.aborted) {
        return;
      }
      const message =
        err instanceof Error && err.message
          ? err.message
          : "Unable to load engagements from the API.";
      setError(message);
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadEngagements(controller.signal);
    return () => controller.abort();
  }, [loadEngagements]);

  const selectEngagement = useCallback((id: number) => {
    setActiveEngagementId(id);
    writeStoredId(id);
  }, []);

  const createEngagement = useCallback(
    async (input: EngagementCreateInput): Promise<Engagement> => {
      const created = await apiCreateEngagement(input);
      setEngagements((prev) => [...prev, created]);
      setActiveEngagementId((current) => {
        const nextId = current ?? created.id;
        writeStoredId(nextId);
        return nextId;
      });
      return created;
    },
    []
  );

  const deleteEngagement = useCallback(async (id: number): Promise<void> => {
    await apiDeleteEngagement(id);
    setEngagements((prev) => {
      const remaining = prev.filter((item) => item.id !== id);
      setActiveEngagementId((current) => {
        const nextId =
          current === id ? resolveActiveId(remaining, null) : resolveActiveId(remaining, current);
        writeStoredId(nextId);
        return nextId;
      });
      return remaining;
    });
  }, []);

  const activeEngagement = useMemo(
    () => engagements.find((item) => item.id === activeEngagementId) ?? null,
    [engagements, activeEngagementId]
  );

  const value = useMemo<EngagementContextValue>(
    () => ({
      engagements,
      loading,
      error,
      activeEngagementId,
      activeEngagement,
      selectEngagement,
      refreshEngagements: () => loadEngagements(),
      createEngagement,
      deleteEngagement,
    }),
    [
      engagements,
      loading,
      error,
      activeEngagementId,
      activeEngagement,
      selectEngagement,
      loadEngagements,
      createEngagement,
      deleteEngagement,
    ]
  );

  return (
    <EngagementContext.Provider value={value}>
      {children}
    </EngagementContext.Provider>
  );
}

export function useEngagement(): EngagementContextValue {
  const ctx = useContext(EngagementContext);
  if (!ctx) {
    throw new Error("useEngagement must be used inside an EngagementProvider");
  }
  return ctx;
}
