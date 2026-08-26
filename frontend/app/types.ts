export type Metrics = {
  requested_interviews: number;
  scheduled_interviews: number;
  unscheduled_interviews: number;
  coverage: number;
  weighted_coverage: number;
  overall_room_utilisation: number;
  average_student_wait_minutes: number;
  replan_churn: number;
  schedule_stability: number;
  maximum_shifted_minutes: number;
  unscheduled_by_reason: Record<string, number>;
  validation: { valid: boolean; violation_count: number; violations: Array<{ code: string; message: string }> };
};

export type DatasetSummary = {
  seed: number;
  students: number;
  companies: number;
  rooms: number;
  panels: number;
  interviews: number;
  current_time: number;
};

export type Interview = {
  id: string;
  student_id: string;
  company_id: string;
  duration: number;
  priority: number;
  status: string;
  scheduled_start: number | null;
  scheduled_end: number | null;
  room_id: string | null;
  panel_id: string | null;
  unscheduled_reason: string | null;
  unscheduled_reason_code: string | null;
};

export type Company = {
  id: string;
  name: string;
  priority_tier: number;
  company_type: string;
  day_preference: number;
  shortlist_size: number;
  status: string;
  panel_count: number;
};

export type Student = {
  id: string;
  name: string;
  roll_number: string;
  branch: string;
  cgpa: number;
  placement_status: string;
  shortlisted_company_ids: string[];
  withdrawn: boolean;
};

export type Room = {
  id: string;
  name: string;
  building: string;
  floor: number;
  available: boolean;
  outage_windows: Array<[number, number]>;
};

export type Replan = {
  id?: number;
  summary: Record<string, number | string>;
  changes: Array<Record<string, number | string | null>>;
  validation: Metrics["validation"];
};

