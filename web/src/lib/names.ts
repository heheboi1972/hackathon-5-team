// 역할: "a"/"b" → display_name 치환 (참조: TRD §6.3, API_SPEC 공통 규칙)
import type { CoupleMeResponse, Who } from "../api/types";

/** me면 "나", 아니면 상대 display_name */
export function who(x: Who, me: CoupleMeResponse): string {
  if (x === me.me) return "나";
  return me.members?.[x]?.display_name ?? x.toUpperCase();
}

/** 리포트·챗봇 본문의 "A"/"B" 문자열을 렌더 직전에 치환 */
export function replaceNames(text: string, me: CoupleMeResponse): string {
  return text
    .replace(/\bA\b/g, who("a", me))
    .replace(/\bB\b/g, who("b", me));
}
