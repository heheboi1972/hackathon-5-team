export type MemberKey = "a" | "b";

export interface ReadyResponse {
  postgres: boolean;
  qdrant: boolean;
  watsonx: boolean | "mock";
}

export interface TimelineResponse {
  weeks: Array<Record<string, unknown>>;
}

