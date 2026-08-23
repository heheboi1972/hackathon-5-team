# build_lexicon — 커플 단어 분류 프롬프트 (ISSUE A1, Phase 3)  TODO: 윤아
입력: 단어 + 최초 등장 3건의 앞뒤 2~3토큰 예시. 100단어씩.
출력(JSON): [{"term", "canonical", "polarity": "pos|neg|neutral|exclude"}]
규칙: canonical 은 철자 변형만 묶는다(조아→좋아). 동의어는 분리. exclude = 욕설·이름·식별정보. 모든 출력은 한국어.
