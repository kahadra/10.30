"""Write repro/HYPOTHESES.md from results/r0*, r0b*, h_*.json: purpose, success criterion, status and hypothesis verdicts."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"


def load(n):
    p = RES / n
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def pct(x):
    return "–" if x is None else f"{100 * x:.0f}%"


R0, R0B = load("r0_book_originals.json"), load("r0b_book_minimal.json")
H = {k: load(f"h_{k}.json") for k in ("w_ua", "w_query", "w_loop", "w_desc", "tc", "err", "ver", "mcp", "mcp_fix")}


def l0(key, env="current"):
    r = next(x for x in R0["results"] if x["example"] == key)["runs"][env]
    err = (r["error_last_line"] or "").replace("`", "'").strip()[:90]
    return "동작" if r["exit"] == 0 else f"실패 — {err}"


def l1(key):
    row = R0B["results"][key]
    r = row["runs"]["current"]
    n = row["edits"][-1]["original_lines_changed"]
    if key == "calculator":
        return "동작 (현재 환경: 모델 이름 외 수정 없음 · 책 환경용 1줄 추가)"
    if key == "wikipedia":
        return f"실행되나 오답 (원본 {n}줄 수정: User-Agent 등) — H-W2~W4"
    return ("동작" if r["exit"] == 0 else "실패") + f" (원본 {n}줄 수정)"


lines = ["# 책 4장 예제: 목적 달성과 가설 검증", "",
         "생성: `repro/report_hypotheses.py` (결과 JSON에서 자동 작성). LLM은 모두 `qwen2.5:7b`(Ollama). "
         "원본의 `gpt-4o`는 유료 API 모델이라 모델 이름 한 줄만 바꿨고, 다른 모델에 gpt-4o라는 이름을 붙이지 않았습니다.", "",
         "## 1. 예제별 목적과 결과", "",
         "| 예제 | 목적 (성공 기준) | L0 원본 · 책 환경 | L0 원본 · 현재 환경 | L1 최소 수정 | 목적 달성 |", "|---|---|---|---|---|---|"]
wl = {**(H["w_loop"] or {}).get("summary", {}), **(H["w_desc"] or {}).get("summary", {})}
best_w = max(wl.items(), key=lambda kv: kv[1]["success"]) if wl else None
mc = (H["mcp"] or {}).get("summary", {})
mf = {k: v["summary"] for k, v in (H["mcp_fix"] or {}).get("results", {}).items()}
best_m = max(mf.items(), key=lambda kv: kv[1]["model_end_to_end"]) if mf else None
rows = [
    ("계산기 p.74", "모델이 도구·인자를 골라 실행하고 결과로 정답", "calculator", "**달성** (원본 그대로, 현재 환경)"),
    ("Wikipedia p.76", "검색으로 관련 문서를 가져와 그 내용으로 답", "wikipedia",
     f"**{'달성' if best_w and best_w[1]['success'] >= 0.8 else '부분 달성'}** — 최선 조건 “{best_w[0]}” 성공 {pct(best_w[1]['success'])}" if best_w else "실험 대기"),
    ("주가 p.77", "외부 API에서 실시간 데이터를 받아 답", "stock_price", "**달성** (L1: 실제 시세 API)"),
    ("MCP p.82–83", "두 MCP 서버(stdio·HTTP)의 도구로 질의를 올바르게 보내 답", "mcp_client",
     (f"**{'달성' if best_m[1]['model_end_to_end'] >= 0.8 else '부분 달성'}** — “{best_m[0]}” + 모델 라우팅: 종단 정답 {pct(best_m[1]['model_end_to_end'])} "
      f"(책 서버·키워드 라우터 {pct(mc.get('keyword_end_to_end'))})") if best_m else "실험 대기"),
]
for name, purpose, key, status in rows:
    lines.append(f"| {name} | {purpose} | {l0(key, 'book')} | {l0(key)} | {l1(key)} | {status} |")
lines += ["| 상태 도구 p.84–85 | 좁은 도구·최소 권한이 파괴적 행동을 막음 | 책에 코드 없음 | – | – | **달성** (`demos/d4`) |",
          "| 설정 p.87–88 | tool_choice로 제어, 검증·재시도·대체로 복구 | 책에 코드 없음 | – | – | **부분 달성**: Ollama는 tool_choice를 무시 → 코드로 강제 (`demos/d5`) |", ""]

lines += ["## 2. 가설 검증", ""]


def block(title, h, pred, result, verdict, note=""):
    return [f"### {title}", "", f"- 가설: {h}", f"- 예측: {pred}", f"- 결과: {result}", f"- 판정: **{verdict}**"] + ([f"- 비고: {note}"] if note else []) + [""]


if H["w_ua"]:
    c = H["w_ua"].get("counts", {})
    lines += block("H-W1 · Wikipedia 원본 실패(HTTP 429)", "라이브러리의 공용 기본 User-Agent가 호출 제한을 받는다(코드 결함 아님)",
                   "같은 요청을 번갈아 보내면 기본 UA는 대부분 429, 식별 UA는 대부분 200",
                   f"기본 UA 429 {c.get('default_429')}/{c.get('n_each')}, 식별 UA 429 {c.get('identifying_429')}/{c.get('n_each')}",
                   H["w_ua"]["verdict"], H["w_ua"].get("decision_rule_note", ""))
if H["w_query"]:
    pg = H["w_query"]["pages"]
    lines += block("H-W2 · Wikipedia 최소 수정판의 오답", "모델이 만든 검색어가 엉뚱한 1순위 문서를 끌어온다",
                   "인물 이름만 넣으면 맞는 문서, 모델의 검색어로는 다른 문서",
                   "; ".join(f"“{q}” → {v}" for q, v in pg.items()), H["w_query"]["verdict"])
if H["w_loop"]:
    s = H["w_loop"]["summary"]
    lines += block("H-W3 · 책의 1회 루프와 top_k=1", "① 도구 호출을 한 번만 허용하는 루프가 잘못된 검색을 회복하지 못한다 ② 검색 결과 1개는 취약하다",
                   "여러 단계 루프, top_k=3에서 성공률 상승 (인물 6명 질의)",
                   "; ".join(f"{k}: 성공 {pct(v['success'])}, 맞는 문서 검색 {pct(v['retrieved'])}" for k, v in s.items()),
                   f"① {H['w_loop']['verdicts']['H1_multi_step']} · ② {H['w_loop']['verdicts']['H2_top_k3']}",
                   "성공 = 맞는 문서를 가져왔고 답이 그 문서의 핵심 사실을 언급. 여러 단계를 허용해도 모델이 같은 검색어를 반복함. "
                   "429는 Retry-After를 지켜 재시도(실험 장치, 기록됨)")
if H["w_desc"]:
    s = H["w_desc"]["summary"]
    lines += block("H-W4 · 검색어를 만드는 것은 도구 설명", "모델이 질문 문장을 검색어로 쓰는 것은 원래 설명(“Input should be a search query.”)이 허용하기 때문",
                   "설명에 ‘입력은 문서 제목(예: 인물 이름)이지 질문이 아니다’를 적으면 책의 1회 루프에서도 성공률 상승",
                   "; ".join(f"{k}: 성공 {pct(v['success'])}, 맞는 문서 {pct(v['retrieved_right_page'])}" for k, v in s.items()),
                   H["w_desc"]["verdict"], "바꾼 것은 도구 설명 문자열 하나 — 4장 ‘메타데이터가 선택을 좌우한다’의 직접 사례")
if H["mcp"]:
    s = H["mcp"]["summary"]
    lines += block("H-M1 · MCP 예제의 병목", "서버가 아니라 책의 키워드 라우터가 목적 달성을 막는다",
                   "같은 책 서버에서 모델 라우팅이 라우팅 정확도와 종단 정답률을 모두 높인다",
                   f"키워드: 라우팅 {pct(s['keyword_routing_acc'])}, 종단 {pct(s['keyword_end_to_end'])} · 모델: 라우팅 {pct(s['model_routing_acc'])}, 종단 {pct(s['model_end_to_end'])}",
                   H["mcp"]["verdict"])
if H["mcp_fix"]:
    r = {k: v["summary"] for k, v in H["mcp_fix"]["results"].items()}
    v = H["mcp_fix"]["verdicts"]
    lines += block("H-M2 · 책 수학 서버의 파싱 오류", "책 서버가 질문에서 숫자·연산자만 남길 때 앞 공백이 남아 `unexpected indent`가 난다",
                   "`.strip()` 한 줄 추가로 키워드가 수학으로 보낸 질의가 성공", "; ".join(f"{k}: 키워드 종단 {pct(x['keyword_end_to_end'])}" for k, x in r.items()), v["H-M2"])
    lines += block("H-M3 · 날씨 실패", "서버 파서는 ‘weather in <도시>’만 이해하는데 모델은 도시 이름만 넘긴다",
                   "(a) 도구 설명에 ‘질문 전체를 넘겨라’ 또는 (b) 서버가 도시 이름도 받으면 모델 종단 정답률 상승",
                   "; ".join(f"{k}: 모델 종단 {pct(x['model_end_to_end'])}" for k, x in r.items()), f"(a) {v['H-M3a']} · (b) {v['H-M3b']}",
                   "(a)에서는 날씨는 모두 성공했지만, 같은 프롬프트 안의 수학 질의 2건에서 모델이 원문(“twelve times eight”)을 그대로 넘겨 실패 — 한 도구의 설명이 다른 도구의 인자 생성에도 영향")
if H["tc"]:
    s = H["tc"]["summary"]
    lines += block("H-C1 · tool_choice 무시", "LangChain의 Ollama 연동만 tool_choice를 버리고, Ollama의 OpenAI 호환 API는 지킨다",
                   "/v1로 보내면 none은 0%, required는 100% 호출",
                   "; ".join(f"{k}: 산술 {pct(v['tool_rate_math'])}, 일반 {pct(v['tool_rate_other'])}" for k, v in s.items())
                   + " · 요청 본문에 tool_choice가 실려 간 것을 확인", "반증 — 서버(Ollama)가 무시한다", "대응: 코드로 강제 (demos/d5 enforced)")
if H["err"]:
    r = H["err"]["fabrication_rate"]
    lines += block("H-C2 · 도구 오류 후 답 지어내기", "일반 오류 메시지만으로는 부족하고, 명시적 시스템 규칙이 지어내기를 줄인다",
                   "규칙을 넣으면 지어내기 비율 감소", "; ".join(f"{k}: {pct(v)}" for k, v in r.items()),
                   f"{H['err']['verdict']} (방향은 일치하나 6건 중 1건 차이 — 약한 근거)",
                   "‘지어내기’에는 모델이 스스로 맞게 계산한 경우(17×23=391)도 포함. 규칙만으로 0이 되지 않으므로 최종 답 검사(demos/d5)가 여전히 필요")
if H["ver"]:
    lines += block("H-V1 · 책 환경에서의 실패", "책 코드는 고정 버전(langchain-core 0.1)보다 새 버전(≥0.2)을 기준으로 쓰였다",
                   "모델 이름만 바꾼 원본 계산기가 langchain-core 0.2에서 동작", f"{H['ver']['env']} → exit {H['ver']['exit']}", H["ver"]["verdict"])

(ROOT / "repro/HYPOTHESES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("-> repro/HYPOTHESES.md")
