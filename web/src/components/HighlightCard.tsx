// 역할: 리포트 하이라이트 카드 — 관찰 + 해석 + 제안 3문장 (참조: API_SPEC §4.2) — 시여 담당
// 스캐폴딩 스텁: 디자인은 TODO(시여). 병합 규칙은 계약이므로 여기 고정.
import type { Highlight, Suggestion } from "../api/types";

/**
 * interpretations[] 는 종결어미 없는 **절**이다 ("바쁜 시기였을 수도").
 * 한 문장으로 이어 붙여 카드가 관찰·해석·제안 3문장이 되게 한다 (API_SPEC §4.2 렌더 규칙).
 * 계약이 ≥2 를 강제하는 건 원인을 단정하지 않기 위해서고(P-1), 화면에서는 한 문장으로 보인다.
 */
export function joinInterpretations(clauses: string[]): string {
  return `${clauses.join(", ")} 있어요.`;
}

export default function HighlightCard({
  highlight,
  suggestion,
}: {
  highlight: Highlight;
  suggestion?: Suggestion;
}) {
  return (
    <section className="space-y-1 rounded-lg border p-4">
      <p className="font-semibold">{highlight.observation}</p>
      <p className="text-sm text-gray-700">{joinInterpretations(highlight.interpretations)}</p>
      {suggestion && <p className="text-sm text-rose-700">Tip: {suggestion.text}</p>}
    </section>
  );
}
