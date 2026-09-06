// Typed fetch client against the Code Council FastAPI backend.
// Contract: docs/API_CONTRACT.md (FROZEN 2026-09-05). Every shape in that file
// has a type here. Every call swallows network/HTTP failures and returns null
// so pages can render an EmptyState instead of crashing when the API is down.

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...init });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

// ---- shared enums -----------------------------------------------------

export type TaskStatus = "new" | "in_progress" | "approved" | "dismissed";
export type Severity = "high" | "medium" | "low";
export type ProposalStatus = "pending" | "approved" | "rejected";
export type ReviewState = "pending" | "reviewed";
export type DiffOp = "equal" | "insert" | "delete";

// ---- shared objects -----------------------------------------------------

export interface Assignee {
  id: number;
  name: string;
  initials: string;
  role: string;
}

export interface ParliamentItemSummary {
  id: number;
  title: string;
  sitting_date: string;
  item_type: string;
  legislation_type: string; // "Amendment" | "New Legislation"
  speaker: string;
  url: string;
  summary: string;
}

export interface Task {
  id: number;
  reference: string;
  status: TaskStatus;
  severity: Severity;
  document_count: number;
  proposal_count: number;
  created_at: string;
  assignee: Assignee | null;
  is_demo: boolean;
  sectors: string[];
  item: ParliamentItemSummary;
}

export interface AffectedDocumentPreview {
  clause_ref: string;
  heading: string;
  before: string;
  after: string;
}

export interface AffectedDocument {
  id: number;
  document_id: number;
  slug: string;
  title: string;
  sector: string;
  severity: Severity;
  review_state: ReviewState;
  proposal_count: number;
  version: number;
  preview: AffectedDocumentPreview;
}

export interface TaskDetail extends Task {
  documents: AffectedDocument[];
}

export interface Clause {
  anchor: string;
  number: string;
  heading: string;
  text: string;
}

export type DiffPair = [DiffOp, string];

export interface Proposal {
  id: number;
  clause_ref: string;
  status: ProposalStatus;
  severity: Severity;
  rationale: string;
  suggested_text: string;
  clause: Clause;
  diff: DiffPair[];
}

export interface TaskDocumentDetail {
  task: Task;
  document: AffectedDocument;
  proposals: Proposal[];
}

export interface DocumentSummary {
  id: number;
  slug: string;
  title: string;
  file_type: string;
  version: number;
  clause_count: number;
  updated_at: string;
  parse_error: string | null;
  open_task_count: number;
}

export interface SectorGroup {
  sector: string;
  count: number;
  documents: DocumentSummary[];
}

export interface DocumentsResponse {
  sectors: SectorGroup[];
}

export interface ClauseWithConcepts {
  anchor: string;
  number: string;
  heading: string;
  text: string;
  concepts: string[];
}

export interface HistoryEntry {
  clause_ref: string;
  before_text: string;
  after_text: string;
  user: { id: number; name: string; initials: string } | null;
  created_at: string;
  version_after: number;
}

export interface DocumentDetail extends DocumentSummary {
  clauses: ClauseWithConcepts[];
  history: HistoryEntry[];
}

export interface NotificationActor {
  name: string;
  initials: string;
}

export interface Notification {
  id: number;
  message: string;
  read: boolean;
  created_at: string;
  actor: NotificationActor;
  task_id: number | null;
  task_reference: string;
  document_slug: string;
}

export interface NotificationsResponse {
  unread: number;
  notifications: Notification[];
}

export interface ParliamentItemWithMeta extends ParliamentItemSummary {
  vault_path: string;
  task_id: number | null;
  task_reference: string | null;
}

export interface SittingInfo {
  parliament_no: number;
  session_no: number;
  volume_no: number;
  sitting_no: number;
}

export interface ParliamentResponse {
  items: ParliamentItemWithMeta[];
  sitting: SittingInfo;
}

export interface User {
  id: number;
  name: string;
  email: string;
  role: string;
  initials: string;
}

// ---- calls -----------------------------------------------------

export async function getTasks(params?: {
  status?: TaskStatus;
  severity?: Severity;
  sector?: string;
}): Promise<Task[] | null> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.severity) qs.set("severity", params.severity);
  if (params?.sector) qs.set("sector", params.sector);
  const query = qs.toString();
  const data = await fetchJSON<{ tasks: Task[] }>(`/tasks${query ? `?${query}` : ""}`);
  return data ? data.tasks : null;
}

export async function getTask(taskId: number): Promise<TaskDetail | null> {
  return fetchJSON<TaskDetail>(`/tasks/${taskId}`);
}

export async function getTaskDocument(
  taskId: number,
  docSlug: string
): Promise<TaskDocumentDetail | null> {
  return fetchJSON<TaskDocumentDetail>(`/tasks/${taskId}/documents/${docSlug}`);
}

export async function approveProposal(id: number, userId: number): Promise<Proposal | null> {
  return fetchJSON<Proposal>(`/proposals/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
}

export async function rejectProposal(id: number, userId: number): Promise<Proposal | null> {
  return fetchJSON<Proposal>(`/proposals/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
}

export async function getDocuments(sector?: string): Promise<DocumentsResponse | null> {
  const query = sector ? `?sector=${encodeURIComponent(sector)}` : "";
  return fetchJSON<DocumentsResponse>(`/documents${query}`);
}

export async function getDocument(slug: string): Promise<DocumentDetail | null> {
  return fetchJSON<DocumentDetail>(`/documents/${slug}`);
}

export async function getNotifications(userId: number): Promise<NotificationsResponse | null> {
  return fetchJSON<NotificationsResponse>(`/notifications?user_id=${userId}`);
}

export async function markNotificationRead(id: number): Promise<boolean> {
  const res = await fetchJSON<Record<string, never>>(`/notifications/${id}/read`, {
    method: "POST",
  });
  return res !== null;
}

export async function getParliament(date?: string): Promise<ParliamentResponse | null> {
  const query = date ? `?date=${encodeURIComponent(date)}` : "";
  return fetchJSON<ParliamentResponse>(`/parliament${query}`);
}

export async function getUsers(): Promise<User[] | null> {
  const data = await fetchJSON<{ users: User[] }>(`/users`);
  return data ? data.users : null;
}
