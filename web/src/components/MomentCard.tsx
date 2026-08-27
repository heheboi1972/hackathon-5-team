// 역할: 특이 순간 카드 (참조: API_SPEC §4.2 moments) — 시여 담당
// 스캐폴딩 스텁: 디자인은 TODO(시여)
import type { Moment } from "../api/types";

export default function MomentCard({ moment }: { moment: Moment }) {
  return (
    <div className="rounded-lg border p-4 text-sm">
      {moment.snippet ? <blockquote>“{moment.snippet}”</blockquote> : <p>{moment.text}</p>}
    </div>
  );
}
