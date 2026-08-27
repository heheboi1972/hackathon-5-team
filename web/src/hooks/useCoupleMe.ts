import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { CoupleMeResponse } from "../api/types";

export function useCoupleMe() {
  return useQuery({
    queryKey: ["couple-me"],
    queryFn: () => api.get<CoupleMeResponse>("/api/couples/me"),
    staleTime: 30_000,
  });
}
