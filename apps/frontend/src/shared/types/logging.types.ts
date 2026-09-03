export type LogLevel = "debug" | "info" | "warning" | "error";

export interface LogEvent {
  level: LogLevel;
  event: string;
  request_id: string | null;
  session_id: string;
  client_timestamp: string;
  fields: Record<string, unknown>;
}
