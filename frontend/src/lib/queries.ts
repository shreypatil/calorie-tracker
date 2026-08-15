/** Query and mutation hooks. One place that knows which URL serves what. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, query } from "./api";
import type {
  DailySummary,
  FoodEntry,
  Goal,
  GoalVsActual,
  Granularity,
  MacroBreakdown,
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
