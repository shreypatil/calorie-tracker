/** Query and mutation hooks. One place that knows which URL serves what. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, query } from "./api";
import type {
  ChatMessage,
  ChatTurn,
  DailySummary,
  ImportBatch,
  PdfImportPreview,
  FoodEntry,
  Goal,
  GoalVsActual,
  Granularity,
  MacroBreakdown,
  DateFormat,
  MealType,
  MicroSummary,
  Page,
  TrendResponse,
  WeightLog,
} from "./types";

export interface EntryFilters {
  date_from?: string;
  date_to?: string;
  meal_type?: MealType | "";
  q?: string;
  page?: number;
  page_size?: number;
}

export interface ReportRange {
  date_from: string;
  date_to: string;
  granularity: Granularity;
}

/** Anything that changes entries invalidates these — reports read the same rows. */
const ENTRY_DEPENDENT = ["entries", "summary", "trend", "macros", "micros", "goal-vs-actual"];

function useInvalidateOnEntryChange() {
  const queryClient = useQueryClient();
  return () => {
    for (const key of ENTRY_DEPENDENT) {
      queryClient.invalidateQueries({ queryKey: [key] });
    }
  };
}

export function useEntries(filters: EntryFilters) {
  return useQuery({
    queryKey: ["entries", filters],
    queryFn: () => api.get<Page<FoodEntry>>(`/entries${query({ ...filters })}`),
  });
}

export function useCreateEntry() {
  const invalidate = useInvalidateOnEntryChange();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post<FoodEntry>("/entries", body),
    onSuccess: invalidate,
  });
}

export function useDeleteEntry() {
  const invalidate = useInvalidateOnEntryChange();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/entries/${id}`),
    onSuccess: invalidate,
  });
}

export function useDailySummary(on: string) {
  return useQuery({
    queryKey: ["summary", on],
    queryFn: () => api.get<DailySummary>(`/reports/daily-summary${query({ on })}`),
  });
}

export function useTrend(range: ReportRange) {
  return useQuery({
    queryKey: ["trend", range],
    queryFn: () => api.get<TrendResponse>(`/reports/trend${query({ ...range })}`),
  });
}

export function useMacros(range: ReportRange) {
  return useQuery({
    queryKey: ["macros", range],
    queryFn: () => api.get<MacroBreakdown>(`/reports/macros${query({ ...range })}`),
  });
}

export function useMicros(range: Omit<ReportRange, "granularity">) {
  return useQuery({
    queryKey: ["micros", range],
    queryFn: () => api.get<MicroSummary>(`/reports/micros${query({ ...range })}`),
  });
}

export function useGoalVsActual(range: ReportRange) {
  return useQuery({
    queryKey: ["goal-vs-actual", range],
    queryFn: () => api.get<GoalVsActual>(`/reports/goal-vs-actual${query({ ...range })}`),
  });
}

export function useGoals(page = 1) {
  return useQuery({
    queryKey: ["goals", page],
    queryFn: () => api.get<Page<Goal>>(`/goals${query({ page, page_size: 25 })}`),
  });
}

export function useCurrentGoal() {
  return useQuery({
    queryKey: ["goals", "current"],
    queryFn: async () => {
      try {
        return await api.get<Goal>("/goals/current");
      } catch {
        // No goal set yet is a normal state, not an error to surface.
        return null;
      }
    },
  });
}

export function useSaveGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post<Goal>("/goals", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      queryClient.invalidateQueries({ queryKey: ["summary"] });
      queryClient.invalidateQueries({ queryKey: ["goal-vs-actual"] });
      queryClient.invalidateQueries({ queryKey: ["micros"] });
    },
  });
}

export function useDeleteGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/goals/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      queryClient.invalidateQueries({ queryKey: ["summary"] });
      queryClient.invalidateQueries({ queryKey: ["goal-vs-actual"] });
    },
  });
}

export function useWeights() {
  return useQuery({
    queryKey: ["weights"],
    queryFn: () => api.get<Page<WeightLog>>(`/weights${query({ page_size: 30 })}`),
  });
}

export function useRecordWeight() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { logged_on: string; weight_kg: number }) =>
      api.post<WeightLog>("/weights", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["weights"] }),
  });
}

// --- Import (FR-8) --------------------------------------------------------

export interface PreviewRequest {
  file: File;
  date_format?: DateFormat;
  default_meal_type?: MealType | "";
}

/** Upload a PDF and get draft rows back. Nothing is saved by this call. */
export function usePreviewImport() {
  return useMutation({
    mutationFn: ({ file, date_format, default_meal_type }: PreviewRequest) =>
      api.upload<PdfImportPreview>(
        `/imports/pdf${query({ date_format, default_meal_type })}`,
        file,
      ),
  });
}

/** Commit reviewed rows. Reuses the same bulk endpoint manual entry uses. */
export function useCommitImport() {
  const invalidate = useInvalidateOnEntryChange();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entries, filename }: { entries: unknown[]; filename: string }) =>
      api.post<FoodEntry[]>("/entries/bulk", {
        entries,
        import_filename: filename,
      }),
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["imports"] });
    },
  });
}

export function useImportHistory() {
  return useQuery({
    queryKey: ["imports"],
    queryFn: () => api.get<Page<ImportBatch>>(`/imports${query({ page_size: 10 })}`),
  });
}

export function useUndoImport() {
  const invalidate = useInvalidateOnEntryChange();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/imports/${id}`),
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["imports"] });
    },
  });
}

// --- Chat (FR-6) ----------------------------------------------------------

/**
 * The transcript. The API pages newest-first like every other list endpoint;
 * a conversation reads the other way, so it is reversed here rather than in the
 * component.
 */
export function useChatMessages() {
  return useQuery({
    queryKey: ["chat"],
    queryFn: async () => {
      const page = await api.get<Page<ChatMessage>>(`/chat/messages${query({ page_size: 100 })}`);
      return [...page.items].reverse();
    },
  });
}

export function useSendMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (message: string) => api.post<ChatTurn>("/chat/messages", { message }),
    // The turn is appended to the cache by the caller; this keeps the canonical
    // copy in step for the next mount.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat"] }),
  });
}

/**
 * Confirming is the only way chat changes data, so it is the only chat mutation
 * that has to invalidate the rest of the app. Goals and weights are included
 * because `set_goal` and `log_weight` are confirmable too.
 */
function useInvalidateAfterChatWrite() {
  const invalidateEntries = useInvalidateOnEntryChange();
  const queryClient = useQueryClient();
  return () => {
    invalidateEntries();
    for (const key of ["goals", "weights", "chat"]) {
      queryClient.invalidateQueries({ queryKey: [key] });
    }
  };
}

export function useConfirmAction() {
  const invalidate = useInvalidateAfterChatWrite();
  return useMutation({
    mutationFn: ({ id, args }: { id: string; args?: Record<string, unknown> }) =>
      api.post<ChatMessage>(
        `/chat/actions/${id}/confirm`,
        args ? { arguments: args } : {},
      ),
    onSuccess: invalidate,
  });
}

export function useDiscardAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<ChatMessage>(`/chat/actions/${id}/discard`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat"] }),
  });
}

export function useClearChat() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<void>("/chat/messages"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat"] }),
  });
}
