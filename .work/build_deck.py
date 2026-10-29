"""Build the 2026-10-30 IRV_Lab seminar deck: book overview (Building Applications with AI Agents) + Ch.4 Tool Use deep dive.

General-audience version: listeners have neither the textbook nor the course, so the deck opens with context and
definitions, and the demo results appear only as evidence for the book's claims (details in the appendix).

Reuses the 10.02 deck's CSS, navigation, notes and timer engine. Every number on a slide is read from
ch4-tool-use/results/*.json, so re-running the demos and this script keeps slides and data in sync.
Outputs: index.html, presentation_script.md, assets/slide_manifest.json, code/ (snapshot of demos+results).
"""
import html
import json
import re
import shutil
from collections import Counter
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(__file__).resolve().parents[1]
proj = root.parents[1] / "3rd/최신 인공지능/ch4-tool-use"
old = (root.parent / "10.02/index.html").read_text(encoding="utf8")
DATE, LIMIT = "2026.10.30", 1200


def load(name):
    p = proj / "results" / name
    return json.loads(p.read_text(encoding="utf8")) if p.exists() else None


D1, D2, D3, D4, D5 = (load(f) for f in ("d1_tool_selection.json", "d2_api_tools.json", "d3_mcp.json",
                                         "d4_stateful_sqlite.json", "d5_tool_choice.json"))
D2_RUN1 = load("d2_api_tools_run1_offline.json")
R3 = load("r3_book_mcp_handshake.json")
HW = {k: load(f"h_{k}.json") for k in ("w_ua", "w_query", "w_loop", "w_desc", "tc", "err", "ver", "mcp", "mcp_fix")}
W_ORIG = (HW["w_desc"] or {}).get("summary", {}).get("original description, 1 round", {}).get("success")
W_TITLE = (HW["w_desc"] or {}).get("summary", {}).get("title-only description, 1 round", {}).get("success")
MF = {k: v["summary"] for k, v in (HW["mcp_fix"] or {}).get("results", {}).items()}
MCP_KW = MF.get("book servers (L1)", {}).get("keyword_end_to_end")
MCP_BEST = MF.get("math .strip() + weather server accepts bare city", {}).get("model_end_to_end")
PENDING = '<span class="pending">실행 대기</span>'

# ---------- HTML helpers ------------------------------------------------------------------------
esc = html.escape


def box(title, text, color="blue"):
    return f'<div class="box {color}"><h3>{title}</h3><p>{text}</p></div>'


def lead(s): return f'<p class="lead">{s}</p>'
def note(s): return f'<p class="reading">{s}</p>'
def take(s): return f'<div class="takeaway">{s}</div>'
def grid(*items, cols=2, cls=""): return f'<div class="grid-{cols} {cls}">' + "".join(f'<div class="cell">{x}</div>' for x in items) + "</div>"


def table(headers, rows, cls=""):
    return (f'<table class="data-table {cls}"><thead><tr>' + "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows) + "</tbody></table>")


def code(src, title="", h=None):
    style = f' style="max-height:{h}px"' if h else ""
    cap = f'<div class="code-title">{title}</div>' if title else ""
    return f'<div class="code-wrap">{cap}<pre class="code"{style}><code>{esc(src.strip(chr(10)))}</code></pre></div>'


def flow(*steps, cls=""):
    return f'<div class="flow {cls}">' + "".join(f'<div class="step"><b>{a}</b><span>{b}</span></div>' for a, b in steps) + "</div>"


XP = {"확인": "ok", "빈틈": "gap", "발견": "new"}


def xp(kind): return f'<span class="xp {XP[kind]}">실험 · {kind}</span>'


def tag(ok, yes="정상", no="실패"):
    return f'<span class="tag {"ok" if ok else "bad"}">{yes if ok else no}</span>'


def pct(x): return "–" if x is None else f"{100 * x:.0f}%"


def bars(series, cats, values, ymax=1.0, w=560, h=300, fmt=pct, unit_label=""):
    """Grouped vertical bars (inline SVG). series: [(name, color)], values[s][c]."""
    pad_l, pad_b, pad_t = 44, 44, 26
    plot_w, plot_h = w - pad_l - 10, h - pad_b - pad_t
    gw = plot_w / len(cats)
    bw = min(46, (gw - 28) / len(series))
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(unit_label)}">']
    for t in (0, .25, .5, .75, 1):
        y = pad_t + plot_h * (1 - t)
        out.append(f'<line x1="{pad_l}" x2="{w - 10}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'
                   f'<text x="{pad_l - 8}" y="{y + 5:.1f}" class="axis" text-anchor="end">{fmt(t * ymax)}</text>')
    for ci, c in enumerate(cats):
        x0 = pad_l + gw * ci + (gw - bw * len(series) - 2 * (len(series) - 1)) / 2
        for si, (name, color) in enumerate(series):
            v = values[si][ci]
            if v is None:
                continue
            bh = plot_h * v / ymax
            x, y = x0 + si * (bw + 2), pad_t + plot_h - bh
            r = min(4, bh / 2)
            out.append(f'<path d="M{x:.1f},{pad_t + plot_h} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} H{x + bw - r:.1f} '
                       f'Q{x + bw:.1f},{y:.1f} {x + bw:.1f},{y + r:.1f} V{pad_t + plot_h}Z" fill="{color}"><title>{esc(name)} · {esc(c)}: {fmt(v)}</title></path>'
                       f'<text x="{x + bw / 2:.1f}" y="{y - 7:.1f}" class="val" text-anchor="middle">{fmt(v)}</text>')
        out.append(f'<text x="{pad_l + gw * ci + gw / 2:.1f}" y="{h - 16}" class="axis cat" text-anchor="middle">{esc(c)}</text>')
    out.append(f'<line x1="{pad_l}" x2="{w - 10}" y1="{pad_t + plot_h}" y2="{pad_t + plot_h}" class="base"/></svg>')
    legend = "".join(f'<span><i style="background:{c}"></i>{esc(n)}</span>' for n, c in series)
    return f'<figure class="chart-fig">{"".join(out)}<figcaption class="legend">{legend}</figcaption></figure>'


BLUE, AMBER = "#2867d8", "#b7791f"

slides = []


def add(title, section, seconds, body, notes, source, short="", aside=""):
    slides.append(dict(title=title, section=section, seconds=seconds, body=body, notes=notes, source=source, short=short, aside=aside))


# ---------- derived numbers ---------------------------------------------------------------------
def d1_cell(n, q, key):
    if not D1:
        return None
    return next((s[key] for s in D1["summary"] if s["n_tools"] == n and s["description"] == q), None)


d1_model = D1["meta"]["model"] if D1 else "ollama:qwen2.5:7b"
book_router = D3["part_a"]["book_router"]["accuracy"] if D3 else None
llm_router = D3["part_c"]["llm_router"]["accuracy"] if D3 and isinstance(D3.get("part_c"), dict) else None
d4_llm = D4.get("llm") if D4 and isinstance(D4.get("llm"), list) else []
raw_runs = [r for r in d4_llm if r["design"] == "raw"]
scoped_runs = [r for r in d4_llm if r["design"] == "scoped"]
raw_deleted = [200 - r["after"]["customers"] for r in raw_runs if isinstance(r["after"].get("customers"), int)]
d5a = D5.get("part_a") if D5 and isinstance(D5.get("part_a"), dict) else None


def d5_row(how, mode):
    return next((s for s in d5a["summary"] if s["how"] == how and s["mode"] == mode), None) if d5a else None



# ================================================================================================
add("AI 에이전트의 개념과 구현 조건", "Title", 15, "",
    "오늘은 에이전트라는 개념이 무엇이고, 이를 제대로 구현하려면 무엇이 필요한지를 정리해 보겠습니다. "
    "길잡이로 삼은 책은 Michael Albada의 Building Applications with AI Agents입니다. 책을 읽지 않으셨어도 따라오실 수 있게 용어부터 설명하겠습니다.",
    "Michael Albada · Building Applications with AI Agents · O’Reilly")

add("목차", "Roadmap", 25,
    '<div class="toc-grid four">'
    '<button class="toc-item" data-jump="3"><span>00</span><div><h3>문제 제기</h3><p>멀티에이전트 시대에 남은 질문</p></div><b>@@S3@@–@@E3@@</b></button>'
    '<button class="toc-item" data-jump="4"><span>01</span><div><h3>에이전트란</h3><p>정의 · 쓸 때와 쓰지 않을 때 · 첫 에이전트의 구조</p></div><b>@@S4@@–@@E6@@</b></button>'
    '<button class="toc-item" data-jump="7"><span>02</span><div><h3>구현 조건</h3><p>도구 · 계획 · 기억 · 검증과 운영 · 분업 · 보호</p></div><b>@@S7@@–@@E18@@</b></button>'
    '<button class="toc-item" data-jump="19"><span>03</span><div><h3>정리</h3><p>모델의 능력과 시스템의 설계</p></div><b>@@S19@@–@@E19@@</b></button>'
    "</div>" + take("오늘의 질문: 모델이 충분히 똑똑해졌다면, 에이전트를 제대로 만들기 위해 무엇이 더 필요한가?"),
    "순서는 이렇습니다. 먼저 왜 지금 이 질문이 중요한지 짚고, 책이 내리는 에이전트의 정의와 언제 에이전트를 써야 하는지를 보겠습니다. "
    "그다음 이 발표의 중심인, 에이전트를 제대로 구현하는 데 필요한 조건들을 하나씩 보겠습니다. 그중 도구는 제가 직접 실행해 확인한 결과를 근거로 조금 더 자세히 다룹니다. "
    "관통하는 질문은 아래 한 줄입니다.",
    "발표 구성")

add("멀티에이전트 시대의 질문", "00 · Why Now", 60,
    grid(box("달라진 것", "• 사전학습 모델 하나가 추가 학습 없이 다양한 작업에 적응 — API 호출 한 번으로 사용<br>"
             "• 모델이 글뿐 아니라 <b>호출할 함수와 인자</b>까지 구조화해 출력 → 외부 시스템 조작 가능<br>"
             "• MCP(도구 연결)·A2A(에이전트 간 협업) 프로토콜 등장 → 여러 에이전트의 협업이 현실화", "teal"),
         box("현장에서 나오는 질문 (서문)", "“에이전트가 가끔은 동작한다. 어떻게 해야 대부분, 혹은 항상 동작하게 만들 수 있나?”<br>"
             "“도구는 어떻게 설계하나?” · “메모리는 무엇이 필요한가?”<br>“에이전트 하나로 갈까, 여럿으로 갈까?”", "amber"))
    + note("책의 문제의식: 이 설계 패턴은 새로운 종류의 문제를 풀게 해 주지만, 실제 서비스에서 믿고 쓰게 만드는 데는 많은 실무적 장벽이 존재 (서문)")
    + take("모델의 능력은 출발점 — 에이전트가 ‘항상’ 동작하게 만드는 것은 모델 주변 시스템의 설계"),
    "요즘 멀티에이전트라는 말이 자주 들리고, LLM이 특이점에 가까워졌다는 이야기까지 나옵니다. 실제로 많은 것이 바뀌었습니다. 책 1장의 말대로 이제는 사전학습된 모델 하나를 API 호출 한 번으로 불러 다양한 작업에 쓸 수 있고, "
    "모델은 글뿐 아니라 어떤 함수를 어떤 인자로 부를지까지 구조화해서 내놓습니다. MCP나 A2A 같은 프로토콜 덕분에 에이전트가 원격 도구를 쓰고 다른 에이전트와 협업하는 그림도 현실이 되고 있습니다. "
    "그런데 저자가 서문에서 소개하는 현장의 질문은 의외로 소박합니다. 에이전트가 가끔은 동작하는데, 어떻게 하면 대부분, 혹은 항상 동작하게 만드느냐는 것입니다. 도구는 어떻게 설계하고, 메모리는 무엇이 필요하고, 에이전트를 하나로 갈지 여럿으로 갈지. "
    "오늘 발표는 이 질문들에 대한 책의 답을 따라갑니다. 미리 말씀드리면, 모델의 능력은 출발점일 뿐이고, 에이전트를 믿고 쓸 수 있게 만드는 건 모델 주변 시스템의 설계라는 것이 책의 답입니다.",
    "Preface · Ch.1 Defining AI Agents · The Pretraining Revolution", aside="저는 이 책을 대학원 수업 교재로 읽고 있습니다.")

# ---------------- 01 · What is an agent ---------------------------------------------------------
add("에이전트의 정의", "01 · What Is an Agent · Ch.1", 70,
    grid('<div class="agent-diagram"><div class="core">기반 모델<small>LLM · 판단</small></div>'
         '<div class="part p1">도구<small>정보 조회 · 행동</small></div><div class="part p2">메모리<small>맥락 · 지식</small></div>'
         '<div class="part p3">오케스트레이션<small>계획 · 실행 순서</small></div><div class="part p4">인프라<small>배포 · 감시 · 보안</small></div></div>'
         + note("책의 용어 <b>agentic system</b> = 에이전트가 동작하는 데 필요한 전체: 모델 + 도구 + 메모리 + 오케스트레이션 + 인프라"),
         box("책의 정의", "데이터를 분석하고 환경을 해석해 <b>맥락에 따라 스스로 결정</b>하는 지능형 시스템 (p.1)")
         + box("자율성은 스펙트럼", "“에이전트”라 불리는 많은 시스템이 실제로는 정해진 스크립트를 실행할 뿐임. <b>판별 기준: 고정된 스크립트가 아니라 실제로 결정을 내리는가</b>", "amber")
         + box("가능해진 이유", "기반 모델이 글뿐 아니라 <b>함수 이름과 인자</b>를 구조화해 출력 가능 → 프레임워크가 그 함수를 실행", "teal"),
         cls="wide-left"),
    "먼저 책의 정의입니다. 에이전트는 데이터를 분석하고 환경을 해석해 맥락에 따라 스스로 결정하는 시스템입니다. 책은 여기에 중요한 단서를 답니다. 자율성은 있다 없다가 아니라 스펙트럼이고, "
    "에이전트라고 불리는 많은 시스템이 사실은 정해진 스크립트를 돌릴 뿐이라는 겁니다. 판별 기준은 실제로 결정을 내리느냐입니다. "
    "이게 가능해진 건 모델이 어떤 함수를 어떤 인자로 부를지를 구조화해서 내놓을 수 있게 됐기 때문이고, 이것이 뒤에서 볼 도구 사용입니다. "
    "그리고 책은 모델 하나가 아니라 도구, 메모리, 오케스트레이션, 인프라까지 묶은 전체를 agentic system이라고 부릅니다. 오늘 발표의 답이 사실 이 그림에 들어 있습니다. 가운데 모델을 둘러싼 네 칸이 구현 조건입니다.",
    "Ch.1 Defining AI Agents p.1–2")

add("에이전트를 쓸 때와 쓰지 않을 때", "01 · What Is an Agent · Ch.1", 70,
    '<div class="ladder">'
    + "".join(f'<div class="rung r{i}"><b>{t}</b><span>{d}</span><em>{e}</em></div>' for i, (t, d, e) in enumerate([
        ("일반 코드", "입력이 완전히 예측 가능 · 밀리초 단위 지연 · 규제상 결정적 로직 필요", "예: 항상 같은 형식의 로그 파싱 → 정규식 몇 줄"),
        ("결정적 워크플로", "분기를 미리 다 열거 가능 · 재시도·승인 단계를 명시적으로 통제", "예: CSV·JSON·PDF 세 형식만 오는 송장 처리"),
        ("챗봇 · RAG", "문서 검색과 자연어 답변은 필요하지만 후속 행동 결정은 불필요", "예: “VPN 비밀번호 재설정 방법?” → 안내 문서 검색·요약"),
        ("에이전트", "입력이 제각각이고 여러 단계의 판단과 행동이 필요", "예: “배터리가 부풀었다”부터 “주문 안 한 서비스 청구”까지 자유 형식 고객 메일")], 1)) + "</div>"
    + grid(box("책이 제시한 판단 기준", "입력의 변동성 · 필요한 추론의 복잡도 · 성능과 규제 제약 · 유지보수 부담"),
           box("책의 태도", "에이전트는 강력하지만 연산 비용·지연·감시 부담이 큼 → 더 단순한 방법으로 충분하면 그쪽이 정답", "teal")),
    "그렇다면 언제 에이전트를 써야 할까요. 책 1장에서 실무적으로 가장 유용한 부분이 이 비교입니다. 항상 같은 형식으로 들어오는 로그를 파싱하는 일이라면 정규식 몇 줄이면 됩니다. "
    "송장이 CSV, JSON, PDF 세 형식으로만 들어온다면 분기를 미리 다 짤 수 있으니 워크플로가 맞습니다. VPN 비밀번호 재설정 방법을 묻는 질문처럼 문서를 찾아 요약하면 되는 일은 RAG로 충분합니다. "
    "에이전트가 필요한 건 배터리가 부풀었다는 메일부터 주문하지 않은 서비스가 청구됐다는 메일까지, 입력이 제각각이고 상황에 따라 조회하고 판단하고 행동해야 할 때입니다. "
    "책은 에이전트가 강력하지만 비용과 지연, 감시 부담이 크기 때문에 더 단순한 방법으로 충분하면 그쪽을 택하라고 합니다. 에이전트를 제대로 만드는 첫 단계는 정말 에이전트가 필요한지 판단하는 것입니다.",
    "Ch.1 Workflows and Agents p.8–11")

add("첫 에이전트의 구조", "01 · What Is an Agent · Ch.2", 55,
    grid(code('''@tool
def cancel_order(order_id: str) -> str:
    """Cancel an order that hasn't shipped."""
    return f"Order {order_id} has been cancelled."

# 1) LLM이 cancel_order를 부를지 결정
# 2) 코드가 실제로 실행
# 3) LLM이 결과로 확인 메시지 작성''', "책 2장의 첫 예제: 전자상거래 고객지원 (요약)")
         + note("사람이 하던 일: 메일 읽기 → 주문 조회 → API 호출 → 확인 메일 작성 — 건마다 약 2분의 반복 작업"),
         table(["구성 요소", "설계 질문"], [
             ["모델", "어떤 크기·비용·지연의 모델인가 — 최신 범용 모델로 시작해도 충분"], ["도구", "어떤 행동을 허용하는가"], ["메모리", "무엇을 얼마나 기억하는가"],
             ["오케스트레이션", "어떤 순서로 계획하고 실행하는가"], ["트레이드오프", "성능 · 확장성 · 신뢰성 · 비용"],
             ["UX (3장)", "능력과 한계를 어떻게 알리고 신뢰를 쌓는가"]], cls="compact-table"), cls="code-grid")
    + take("책의 조언: 큰 설계 문서보다 작고 검증 가능한 한 조각(주문 취소)부터 — 성공 기준을 먼저 정의"),
    "책 2장은 첫 에이전트를 만듭니다. 고객지원 팀은 매일 환불, 주문 취소, 주소 변경 메일을 받는데, 사람이 메일을 읽고 주문을 조회하고 API를 부르고 확인 메일을 쓰는 2분짜리 일을 반복합니다. "
    "책은 범위를 주문 취소 하나로 좁혀 이 일을 에이전트에게 맡깁니다. 모델은 메일을 보고 cancel_order를 부를지와 인자를 정하고, 실제 실행은 코드가 하고, 모델이 결과로 확인 메시지를 씁니다. "
    "몇 줄짜리 예제지만 에이전트의 구성 요소가 다 들어 있습니다. 오른쪽 표처럼 모델, 도구, 메모리, 오케스트레이션, 그리고 그 사이의 트레이드오프입니다. 모델은 최신 범용 모델로 시작해도 충분하다는 것이 책의 입장입니다. "
    "책의 조언은 거창한 설계보다 이렇게 작고 검증 가능한 한 조각에서 시작해 성공 기준부터 정하라는 것입니다. 이제 모델 주변의 요소들이 각각 무엇을 해결하는지 보겠습니다.",
    "Ch.1 Model Selection · Ch.2 Our First Agent System · Core Components")

# ---------------- 02 · What it takes -------------------------------------------------------------
REQS = [("①", "도구", "4장", "정보를 얻고 실제로 행동하는 수단", "말만 하는 챗봇에 머묾"),
        ("②", "계획", "5장", "어떤 도구를 어떤 순서로 쓸지 결정", "여러 단계 작업에서 길을 잃음"),
        ("③", "기억", "6–7장", "지식·이력을 꺼내 쓰고 경험에서 학습", "매번 처음부터, 같은 실수 반복"),
        ("④", "검증과 운영", "9–11장", "출시 전 평가, 출시 후 감시와 개선", "‘가끔만’ 동작해도 알아채지 못함"),
        ("⑤", "분업", "8장", "커진 시스템을 전문 에이전트로 분할", "도구가 늘수록 선택 오류 증가"),
        ("⑥", "보호", "12–13장", "보안, 사람의 감독과 책임", "오해와 공격이 곧바로 실제 피해로")]
add("구현 조건의 지도", "02 · What It Takes", 60,
    '<div class="req-grid">' + "".join(
        f'<div class="req"><div class="req-head"><span>{n}</span><b>{name}</b><small>{ch}</small></div><p>{role}</p><p class="miss">없으면: {miss}</p></div>'
        for n, name, ch, role, miss in REQS) + "</div>"
    + take("에이전트 = 모델 + 이 여섯 가지 — 모델이 좋아져도 사라지지 않는 일"),
    "책 4장부터 13장까지를 장 제목이 아니라 해결하는 문제로 묶으면 이렇게 여섯 가지 조건이 됩니다. 첫째, 도구가 없으면 에이전트는 말만 하는 챗봇에 머뭅니다. "
    "둘째, 계획이 없으면 여러 단계 작업에서 길을 잃습니다. 셋째, 기억이 없으면 매번 처음부터 시작하고 같은 실수를 반복합니다. 넷째, 검증과 운영이 없으면 에이전트가 가끔만 동작해도 알아채지 못합니다. "
    "다섯째, 분업이 없으면 도구가 늘수록 선택이 흔들립니다. 여섯째, 보호가 없으면 모델의 오해나 외부 공격이 곧바로 실제 피해가 됩니다. "
    "오늘은 이 순서대로 보는데, 도구는 모든 행동이 지나가는 통로이고 뒤의 장들이 계속 다시 다루는 주제라서 직접 실행한 결과와 함께 조금 더 자세히 보겠습니다. "
    "분업, 즉 멀티에이전트는 일부러 뒤쪽에 두었습니다. 책의 순서로는 8장이지만, 앞의 조건들이 갖춰진 다음에야 의미가 있다는 것이 책의 입장이기 때문입니다.",
    "Preface · Ch.4–13 (발표자 정리)")

add("도구 호출의 구조", "02-① 도구 · Ch.4", 60,
    flow(("① 도구 등록", "이름·설명·입력 형식"), ("② 모델 응답", "“multiply(393, 12.25)를 불러 줘”"),
         ("③ 코드가 실행", "4814.25"), ("④ 결과 전달", "대화에 결과 추가"), ("⑤ 최종 답", "결과를 근거로 답변"))
    + grid(code('''@tool
def multiply(x: float, y: float) -> float:
    """Multiply 'x' times 'y'."""
    return x * y

llm_with_tools = llm.bind_tools([multiply, add])
ai_msg = llm_with_tools.invoke("What is 393 * 12.25?")
ai_msg.tool_calls
# [{'name': 'multiply', 'args': {'x': 393, 'y': 12.25}}]''', "책 4장의 첫 예제 (LangChain, 요약)"),
           box("핵심", "모델은 <b>실행하지 않음</b>. 도구 이름과 인자를 담은 요청만 생성. 실행·검증·실패 처리는 그 요청을 받는 코드의 몫.", "teal")
           + box(xp("확인") + "책 예제를 로컬 모델로 실행", f"로컬 7B 모델({esc(d1_model.split(':', 1)[1])})로도 정확한 인자로 동작 · 이후 실험은 모두 같은 모델", "teal")
           + note(f"실험 표지 — {xp('확인')} 책의 주장을 직접 측정 · {xp('빈틈')} 책 예제를 그대로 실행하면 드러나는 문제 · {xp('발견')} 책에 없는 결과"),
           cls="code-grid"),
    "첫 번째 조건, 도구입니다. 도구 호출은 이 다섯 단계로 이뤄집니다. 함수를 도구로 등록하면 이름과 설명, 입력 형식이 모델에게 전달됩니다. 모델은 답 대신 multiply를 393과 12.25로 불러 달라는 요청을 냅니다. "
    "실제 계산은 우리 코드가 하고, 결과를 대화에 넣어 주면 모델이 그걸 근거로 최종 답을 씁니다. 가장 중요한 점은 모델이 직접 실행하지 않는다는 것입니다. 그래서 검증과 실패 처리는 전부 코드 쪽 책임입니다. "
    "책 예제를 로컬 7B 모델로 돌려 보니 정확한 인자로 잘 동작했고, 이어지는 실험도 같은 모델로 했습니다. "
    "앞으로 실험 결과에는 세 가지 표지를 붙였습니다. 확인은 책의 주장을 직접 재 본 것, 빈틈은 책 예제를 그대로 돌렸을 때 드러난 문제, 발견은 책에 없던 결과입니다.",
    "Ch.4 p.72–75 · repro/r1_book_calculator.py")

if D1:
    rec = [[d1_cell(n, q, "tool_recall") for n in (6, 15, 30)] for q in ("good", "poor")]
    tok = [d1_cell(n, "good", "mean_input_tokens") for n in (6, 15, 30)]
    d1_chart = bars([("좋은 메타데이터", BLUE), ("나쁜 메타데이터", AMBER)], ["6개", "15개", "30개"], rec, w=460, h=280, unit_label="정답 도구 선택률")
    d1_notes = (f"모델은 함수 본문을 보지 않고 이름과 설명, 입력 형식만 보고 도구를 고릅니다. 그래서 책은 좁고 정확한 이름, 서로 구별되는 설명, 엄격한 입력 형식을 강조합니다. "
                f"이걸 확인해 봤습니다. 정답 도구 6개에 헷갈리는 방해 도구를 섞어 6개, 15개, 30개로 늘리고, 같은 함수의 이름과 설명만 모호하게 바꾼 조건과 비교했습니다. "
                f"표의 짝을 보시면 차이가 드러납니다. 좋은 쪽은 이름이 get_current_weather와 get_weather_forecast로 하는 일을 말하고, 설명에 '미래 날짜에는 쓰지 말 것', '현재 상태에는 쓰지 말 것'처럼 경계까지 적혀 있습니다. "
                f"나쁜 쪽은 place_info와 place_lookup, 장소 정보를 가져온다와 장소를 조회한다입니다. 하나만 보면 틀린 말이 아니지만, 둘을 나란히 놓으면 '런던에 지금 비 와?'라는 질문에 어느 쪽을 골라야 할지 근거가 없습니다. "
                f"즉 나쁜 메타데이터는 틀린 설명이 아니라 다른 도구와 구별이 안 되는 설명입니다. 입력 형식은 두 조건이 똑같고, 이름과 설명만 바꿨습니다. "
                f"좋은 메타데이터는 30개에서도 정답 도구를 {pct(rec[0][2])} 골랐고, 모호한 메타데이터는 {pct(rec[1][0])}, {pct(rec[1][1])}, {pct(rec[1][2])}로 떨어졌습니다. "
                f"또 도구 설명은 매번 모델 입력에 들어가기 때문에 도구 수만 늘려도 입력이 {tok[0]:,}에서 {tok[2]:,} 토큰으로 3배 넘게 커집니다. 도구를 한 에이전트에 계속 붙이는 건 공짜가 아니라는 뜻이고, 이 문제가 뒤의 계획과 분업으로 이어집니다.")
else:
    d1_chart, d1_notes, tok = lead(PENDING), "실행 후 채워집니다.", [0, 0, 0]
    rec = [[None] * 3, [None] * 3]
add("도구 메타데이터", "02-① 도구 · 확인 실험", 80,
    grid(lead("모델은 코드를 보지 않음 — <b>이름 · 설명 · 입력 형식</b>만 보고 선택 (p.73)")
         + table(["짝", "좋은 메타데이터", "나쁜 메타데이터 (같은 함수)"], [
             ['<span style="white-space:nowrap">현재 날씨</span>', '<code>get_current_weather</code><br>“weather <b>right now</b> … <b>Not for future days.</b>”',
              '<code>place_info</code><br>“Gets information about a place.”'],
             ['<span style="white-space:nowrap">날씨 예보</span>', '<code>get_weather_forecast</code><br>“forecast for the <b>next N days</b> … <b>Not for current conditions.</b>”',
              '<code>place_lookup</code><br>“Looks up a place.”'],
             ["차이", "이름이 <b>동작</b>을 말함 · 설명이 <b>쓰지 않을 때</b>까지 명시 → 짝과 경계가 분명함",
              "이름이 범주(장소)만 말함 · 두 설명이 사실상 같음 → “런던에 <b>지금</b> 비 와?”에 고를 근거 없음"],
         ], cls="compact-table small-rows")
         + note(f"책의 원칙(p.73): 좁고 정확한 이름 · 서로 겹치지 않는 설명 · 엄격한 입력 형식 — 실험은 이름과 설명만 바꾸고 입력 형식은 동일 · 질의 24개 · 입력 토큰: 6개 {tok[0]:,} → 30개 {tok[2]:,}")
         + box(xp("확인") + "설명 한 줄이 검색어까지 결정",
               f"Wikipedia 검색 도구 설명에 “입력은 문서 제목(예: 인물 이름)” 한 줄 추가 → 인물 6명 질문 성공 {pct(W_ORIG)} → {pct(W_TITLE)}. "
               "기존에는 질문 문장을 그대로 검색어로 사용해 엉뚱한 문서 반환", "teal"),
         '<div class="code-title">' + xp("확인") + " 이름·설명만 바꿔 도구 6·15·30개에서 측정</div>"
         + d1_chart + note("세로축: 질의에 맞는 도구를 고른 비율 (tool recall)"), cls="wide-left"),
    d1_notes + (f" 같은 주장을 다른 실험으로도 확인했습니다. 책의 Wikipedia 예제에서 모델은 질문 문장을 그대로 검색어로 넣어 엉뚱한 문서를 받았는데, 도구 설명에 입력은 문서 제목이라고 한 줄 적자 "
                f"인물 6명 질문의 성공률이 {pct(W_ORIG)}에서 {pct(W_TITLE)}로 올랐습니다. 설명 한 줄이 도구 선택뿐 아니라 인자까지 바꾼다는 뜻입니다." if W_TITLE is not None else ""),
    "Ch.4 p.73 · demos/d1_tool_selection.py · repro/hypotheses.py w_desc")

b_rows = []
for r in (D2 or D2_RUN1 or {}).get("part_b", []):
    res = r["result"]
    ko = {"primary ok": "정상", "primary flaky (503 x2)": "일시 오류 2회", "primary down -> backup": "주 서버 다운",
          "primary slow (timeout) -> backup": "주 서버 응답 지연", "both down -> cache": "두 서버 모두 다운", "invalid input": "잘못된 입력"}
    out = f'{res.get("price")} · {res.get("source")}' if "price" in res else esc(res.get("error", ""))
    b_rows.append([ko.get(r["scenario"], esc(r["scenario"])), str(r["n_requests"]), out])
if d5a:
    nr, er = d5_row("native", "none"), d5_row("enforced", "none")
    pin_hello = next((r["calls"] for r in d5a["rows"] if r["enforced"] and r["mode"].startswith("pinned") and r["query"].startswith("Say hello")), [])
    pin_txt = f'multiply({pin_hello[0]["args"].get("x")}, {pin_hello[0]["args"].get("y")})' if pin_hello else "곱셈 호출"
    tc_rows = [[f"<code>{m}</code>", d, f"{pct(d5_row('native', m)['tool_rate_math'])}", f"{pct(d5_row('enforced', m)['tool_rate_math'])}"]
               for m, d in [("auto", "모델이 판단"), ("required", "반드시 호출"), ("none", "호출 금지"), ("pinned:multiply", "특정 도구 고정")]]
    tc_tbl = table(["모드", "의미", "파라미터만 설정", "코드로 강제"], tc_rows, cls="compact-table center small-rows")
else:
    tc_tbl, pin_txt, nr, er = lead(PENDING), "곱셈 호출", {"tool_rate_math": None}, {"tool_rate_math": None}
b5 = (D5 or {}).get("part_b_llm") or []
n_bad = sum("4814.25" not in (r["final_raw"] or "").replace(",", "") for r in b5)
add("도구 실패 처리와 결과 검증", "02-① 도구 · 확인 실험", 65,
    grid(box("책의 권고 (p.78, p.87–88)", "외부 서비스는 언제든 멈춤 → <b>시간 제한 · 재시도 · 백업 제공자 · 캐시</b><br>응답마다 <b>검증 → 재시도 → 대체 → 기록</b>", "teal")
         + box(xp("빈틈") + "책 예제에는 장애 대비 없음", "Wikipedia: 호출 제한(HTTP 429) 오류가 그대로 전파되어 에이전트 중단 · 주가: 자리표시자 주소로 연결 오류 — 장애 대비 없음", "amber"),
         '<div class="code-title">' + xp("확인") + " 책의 권고대로 보강 후 장애 주입</div>"
         + table(["주입한 장애 (모의 서버)", "요청", "결과 · 출처"], b_rows, cls="compact-table small-rows")
         + box(xp("발견") + "오류를 알려도 답을 지어냄", f"도구 실패를 알렸는데도 모델이 {n_bad}/{len(b5)}회 곱셈 결과를 지어냄(예: 60.0) "
               "→ 최종 답을 도구 결과와 대조하는 검사 추가 후 모두 정답 또는 명시적 실패로 전환", "violet")
         + note(f"{xp('발견')} tool_choice로 호출 금지를 줘도 로컬 모델 서버가 무시 → 산술 질의 {pct(nr['tool_rate_math'])} 호출, 코드로 강제 시 {pct(er['tool_rate_math'])} · 상세: 부록"),
         cls="narrow-left"),
    "도구는 실패합니다. 외부 서비스는 언제든 멈추기 때문에 책은 시간 제한, 재시도, 백업 제공자, 캐시를 권하고, 응답마다 검증하고 재시도하고 대체하고 기록하라고 합니다. "
    "그런데 책의 예제를 그대로 돌려 보니, 같은 요청을 반복하자 Wikipedia가 호출을 제한했고 그 오류가 그대로 터져 에이전트가 멈췄습니다. 그래서 책의 권고대로 도구를 보강하고 장애를 일부러 주입해 봤습니다. "
    "일시 오류는 재시도로, 주 서버 장애는 백업으로, 둘 다 죽으면 시각을 표시한 캐시 값으로 넘어갑니다. 핵심은 실패도 예외로 던지지 않고 모델이 읽을 수 있는 결과로 돌려주는 것입니다. "
    "해 보니 하나가 더 필요했습니다. 도구가 실패했다고 알려 줘도 모델이 결과를 지어낸 경우가 있어서, 최종 답의 숫자를 실제 도구 결과와 대조하는 검사를 넣었고, 그러자 모두 정답이거나 명시적인 실패로 바뀌었습니다. "
    "도구 사용을 강제하거나 금지하는 tool_choice 설정도 로컬 모델 서버에서는 경고 없이 무시됐습니다. 설정은 의도의 선언일 뿐이고, 보장은 코드가 해야 합니다.",
    "Ch.4 p.75–78, 87–88 · demos/d2_api_tools.py · demos/d5_tool_choice.py")

cases = [r for r in (D4 or {}).get("battery", []) if "case" in r]
case_names = list(dict.fromkeys(r["case"] for r in cases))
case_ko = {"benign read": "정상 조회", "'optimize': delete old rows (the book's incident)": "“최적화”라며 오래된 행 삭제",
           "injected DROP": "주입된 테이블 삭제", "mass UPDATE": "전체 이메일 덮어쓰기", "planted admin row": "관리자 계정 몰래 추가"}


def dmg(design, case):
    r = next(x for x in cases if x["design"] == design and x["case"] == case)
    return tag(not r["damaged"], "무손상", "손상")


add("상태 도구와 최소 권한", "02-① 도구 · 확인 실험", 70,
    grid(box("책의 실제 사고 사례 (p.84)", "에이전트가 DB 성능을 “최적화”한다며 운영 테이블의 행 절반을 삭제. 악의가 없어도 의도를 오해하면 발생", "amber")
         + box("책의 처방 (p.84–85)", "<b>권장: 최소 권한</b> → 표의 <b>C</b><br>임의 SQL 대신 좁은 연산만 도구로 · 읽기 전용 계정<br>"
               "<b>자유 쿼리가 꼭 필요할 때만</b> → 표의 <b>B</b><br>DROP·ALTER 포함 구문 거부<br>공통: 모든 호출 기록·알림", "teal"),
         lead(xp("확인") + " 같은 위험 호출 5개 → 세 가지 도구 설계에 전송 · DB 손상 여부")
         + table(["모델이 보낸 호출", "A · 처방 없음<small>임의 SQL 그대로 실행</small>", "B · 위험 구문만 차단<small>DROP·ALTER 거부</small>",
                  "C · 책의 권장<small>좁은 도구 + 읽기 전용</small>"],
               [[case_ko.get(c, esc(c))] + [dmg(d, c) for d in ("raw", "blocklist", "scoped")] for c in case_names], cls="compact-table center small-rows hl-last")
         + note(f"같은 요청(“느린 고객 테이블을 정리해 달라”)을 실제 모델에게: A → {sum(1 for x in raw_deleted if x > 0)}/{len(raw_runs)}회 DELETE 실행, "
                f"매회 200명 중 {raw_deleted[0] if raw_deleted else '–'}명 삭제 · C → {sum(1 for r in scoped_runs if r['after'] == r['before'])}/{len(scoped_runs)}회 무손상, 삭제 후보만 보고"),
         cls="narrow-left"),
    "도구가 데이터를 바꿀 수 있게 되면 위험이 커집니다. 책은 에이전트가 DB를 최적화한다며 운영 테이블의 행 절반을 지운 실제 사고로 이 절을 시작합니다. 처방은 최소 권한입니다. 임의 SQL을 열어 주지 말고 좁은 연산만 도구로 등록하고, "
    "읽기 전용 계정을 쓰고, 모든 호출을 기록하라는 것입니다. 자유 쿼리가 꼭 필요하다면 최소한 DROP이나 ALTER가 든 구문은 거부하라고도 합니다. "
    "SQLite로 확인해 봤습니다. 표의 세 열은 처방을 얼마나 적용했느냐입니다. A는 처방 없이 임의 SQL을 그대로 실행하고, B는 자유 쿼리용 최소 조치인 DROP·ALTER 거부만 하고, C는 책이 권하는 좁은 도구와 읽기 전용 계정입니다. "
    "헷갈리거나 공격받은 모델이 보낼 법한 호출 다섯 가지를 세 설계에 똑같이 보냈더니, A는 대부분 손상됐고, "
    "B는 테이블 삭제 하나만 막고 사고 사례와 같은 대량 삭제는 그대로 통과했습니다. C는 모두 무손상이었습니다. 실제 모델에게 테이블 정리를 요청하자 임의 SQL 도구를 받은 모델은 매번 고객 115명을 지웠고, "
    "좁은 도구를 받은 모델은 삭제 후보만 보고했습니다. 모델은 요청을 따랐을 뿐이고, 되돌릴 수 없는 작업이 확인 없이 가능했느냐는 도구 설계가 정합니다. 도구에 대한 정리는 여기까지입니다.",
    "Ch.4 p.84–85 · demos/d4_stateful_sqlite.py")

add("계획: 오케스트레이션", "02-② 계획 · Ch.5", 70,
    table(["유형", "동작", "적합한 경우"], [
        ["<b>반사형</b>", "입력 → 행동을 규칙으로 바로 연결", "빠른 응답이 중요한 단순 요청"],
        ["<b>ReAct</b>", "생각 → 도구 호출 → 결과 관찰을 반복", "중간 결과에 따라 계획을 바꿔야 하는 탐색형 작업"],
        ["<b>계획–실행 분리</b>", "여러 단계 계획을 먼저 세운 뒤 단계별 실행", "계획 점검과 실패 단계 추적이 필요한 작업"],
        ["<b>질문 분해</b>", "하위 질문으로 쪼개 각각 검색 후 종합", "사실마다 근거가 필요한 질문"],
        ["<b>반성형</b>", "행동마다 목표 대비 점검, 어긋나면 재계획", "되돌릴 수 없는 고위험 작업"],
    ], cls="compact-table small-rows")
    + grid(box("도구가 많을 때: 도구 선택", "모델이 전체 목록에서 선택 → <b>의미 검색</b>으로 후보 축소 → <b>계층적 선택</b>(그룹 먼저, 그 안에서 도구)", "teal"),
           box("책의 원칙 (5장 결론)", "지연↔정확도 확인 · 필요한 행동 수와 계획 변경 빈도 파악 · 대표 테스트로 비교 · <b>요구를 만족하는 가장 단순한 방식</b>", "amber"))
    + note("컨텍스트 엔지니어링: 단계마다 사용자 입력·검색 결과·작업 상태·지시를 토큰 한도 안에서 조립하는 일 — 계획과 실행을 잇는 고리"),
    "두 번째 조건은 계획입니다. 도구가 있어도 무엇을 어떤 순서로 쓸지 정하지 못하면 여러 단계 작업을 해낼 수 없습니다. 5장은 이를 오케스트레이션이라 부르고 에이전트 유형을 스펙트럼으로 보여 줍니다. "
    "반사형은 규칙대로 바로 반응하고, ReAct는 생각하고 도구를 부르고 결과를 보고 다시 생각하는 루프를 돕니다. 계획–실행 분리형은 계획을 먼저 세워 두기 때문에 어느 단계에서 실패했는지 추적하기 쉽고, "
    "질문 분해형은 큰 질문을 하위 질문으로 쪼개 하나씩 근거를 찾습니다. 반성형은 행동마다 목표와 비교해 점검하므로 되돌릴 수 없는 고위험 작업에 맞습니다. 아래로 갈수록 신중하지만 느리고 비쌉니다. "
    "앞의 실험에서 도구가 늘수록 선택이 흔들렸는데, 5장은 그 해법으로 의미 검색으로 후보 도구를 먼저 줄이거나, 도구를 그룹으로 묶어 두 단계로 고르는 방법을 제시합니다. "
    "또 매 단계 모델에게 무엇을 보여 줄지 조립하는 일을 컨텍스트 엔지니어링이라고 부릅니다. 책의 결론은 요구를 만족하는 가장 단순한 계획 방식을 고르라는 것입니다.",
    "Ch.5 Agent Types · Tool Selection · Context Engineering · Conclusion")

add("기억: 지식과 메모리", "02-③ 기억 · Ch.6–7", 65,
    grid(box("지식 (knowledge)", "모델 가중치 밖의 <b>검증 가능한 정보</b>를 답을 만드는 시점에 가져옴 — 정책 문서, 제품 카탈로그, 로그 · 주로 RAG"),
         box("메모리 (memory)", "에이전트 <b>자신의 이력</b> — 이전 대화, 도구 결과, 상태 변화 · 대화와 세션을 넘어 연속성 유지", "teal"))
    + flow(("컨텍스트 창", "최근 대화 유지 — 대부분 충분"), ("의미 검색 · RAG", "벡터 저장소에서 관련 내용 검색"),
           ("지식 그래프", "개체 간 관계까지 저장 (GraphRAG)"), ("작업 메모리", "작업 중 화이트보드·메모"))
    + box("학습 (7장): 경험에서 나아지기", "가중치를 바꾸지 않는 학습: 잘된 사례를 예시로 재사용, 스스로 반성 → 가중치를 바꾸는 학습: 미세조정(SFT·DPO) · "
          "<b>필수는 아님</b> — 설계·평가·감시 비용을 감수할 가치가 있을 때만", "amber"),
    "세 번째는 기억입니다. 6장은 두 가지를 구분합니다. 지식은 모델 가중치 바깥의 확인 가능한 정보, 예를 들어 정책 문서나 제품 카탈로그를 답을 만드는 시점에 가져오는 것으로, 흔히 RAG로 구현합니다. "
    "메모리는 에이전트 자신의 이력, 즉 이전 대화와 도구 결과, 상태 변화를 기억해 대화와 세션을 넘어 일관성을 유지하는 것입니다. "
    "방법은 최근 대화를 컨텍스트 창에 그대로 두는 것에서 시작해, 의미 검색, 개체 사이의 관계까지 저장하는 지식 그래프, 작업 중에 메모를 남기는 작업 메모리로 갑니다. 책은 대부분은 컨텍스트 창으로 충분하고, 어려운 경우에만 더 투자하라고 합니다. "
    "7장의 학습은 기억의 연장입니다. 잘된 사례를 예시로 다시 쓰거나 스스로 반성하는 방법이 먼저이고, 모델 가중치를 바꾸는 미세조정은 그다음입니다. 책은 학습이 필수는 아니며 비용을 감수할 가치가 있을 때만 넣으라고 분명히 말합니다.",
    "Ch.6 Knowledge and Memory · Ch.7 Learning in Agentic Systems")

add("출시 전 검증", "02-④ 검증과 운영 · Ch.9", 65,
    lead("확률적으로 동작하는 시스템 — 같은 입력에도 출력이 달라지고, 모든 경우를 테스트할 수 없음")
    + table(["단계", "무엇을 보나", "책의 예 (고객지원 에이전트)"], [
        ["목표 정의", "핵심 시나리오(hero scenario)와 측정 가능한 지표", "금 간 머그컵 환불 요청 (주문 A89268)"],
        ["구성 요소 평가", "도구 · 계획 · 메모리 · 학습을 각각 테스트", "도구: 정상 경로뿐 아니라 깨진 데이터·네트워크 장애까지"],
        ["종단 평가", "전체 흐름 · 일관성 · 환각", "표현이 달라도 항상 파손 사진을 먼저 요청한 뒤 환불 도구 호출"],
        ["예상 밖 입력", "테스트 세트 밖의 상황", "표준 테스트를 통과해도 새 입력에서 엉뚱하게 행동 → 평가 세트를 계속 갱신"],
    ], cls="compact-table small-rows")
    + note("책 9장이 말하는 도구 평가 지표 = 앞의 도구 메타데이터 실험에서 잰 정답 도구 선택률·인자 정확도")
    + take("측정 없이는 어떤 변경을 내보낼지 판단 불가 — 측정이 곧 신뢰의 근거"),
    "네 번째 조건은 검증과 운영입니다. 9장의 출발점은 에이전트가 확률적으로 동작한다는 사실입니다. 같은 입력에도 출력이 달라지고, 모든 경우를 테스트할 수 없습니다. "
    "그래서 먼저 핵심 시나리오와 지표를 정합니다. 책은 금이 간 머그컵 환불 요청이라는 구체적인 사례를 끝까지 따라갑니다. 다음으로 도구, 계획, 메모리를 각각 테스트하는데, 도구라면 정상 경로뿐 아니라 깨진 데이터와 네트워크 장애까지 넣어 봅니다. "
    "전체 흐름에서는 일관성을 봅니다. 고객이 표현을 바꿔 말해도 에이전트가 항상 파손 사진을 먼저 요청한 뒤 환불 도구를 부르는지 확인하는 식입니다. "
    "그리고 표준 테스트를 다 통과해도 새로운 입력에서는 엉뚱하게 행동할 수 있으니 평가 세트를 계속 갱신하라고 합니다. 앞에서 제가 쓴 정답 도구 선택률과 인자 정확도가 바로 이 장의 도구 평가 지표입니다. "
    "책의 표현대로, 측정 없이는 어떤 변경을 내보낼지조차 판단할 수 없습니다.",
    "Ch.9 Measuring Agentic Systems · Component Evaluation · Holistic Evaluation")

add("출시 후 감시와 개선", "02-④ 검증과 운영 · Ch.10–11", 65,
    grid(box("감시가 답해야 할 질문 (10장)", "사용자의 의도를 이해했나? · 올바른 도구를 골랐나? · 환각은 없었나? · 사용자가 중간에 포기했나?<br>"
             "→ CPU·오류율만 보는 기존 서버 모니터링이 답하지 못하는 질문")
         + box("실패는 곧 테스트 케이스", "운영 중 실패한 추적 기록을 회귀 테스트로 수집 · 섀도 모드·카나리 배포로 변경의 위험 축소", "teal"),
         '<div class="code-title">개선 루프 (11장)</div>' + flow(("관찰", "로그 · 추적 · 사용자 피드백"), ("진단", "반복되는 실패 패턴과 근본 원인"),
              ("실험", "섀도 배포 · A/B 테스트 · 밴딧"), ("반영", "프롬프트·도구·예시 수정, 필요 시 재학습"), cls="vertical"))
    + take("에이전트는 ‘한 번 만들고 끝’이 아님 — 관찰 → 조정 → 검증 → 배포의 순환 (11장)"),
    "출시한 다음이 절반입니다. 10장은 감시가 답해야 할 질문을 이렇게 정리합니다. 사용자의 의도를 이해했는가, 올바른 도구를 골랐는가, 환각은 없었는가, 사용자가 중간에 포기했는가. "
    "CPU나 오류율만 보는 기존 서버 모니터링으로는 답할 수 없는 질문들입니다. 에이전트의 실패는 시스템을 멈추게 하지 않고 조용히 틀리기 때문입니다. "
    "그래서 책은 운영 중 실패한 기록을 그대로 회귀 테스트로 모으라고 합니다. 실패가 곧 다음 테스트 케이스가 되는 겁니다. "
    "11장은 이를 개선 루프로 묶습니다. 관찰하고, 반복되는 실패 원인을 진단하고, 섀도 배포나 A/B 테스트로 실험해 본 뒤 반영합니다. 에이전트는 한 번 만들고 끝나는 소프트웨어가 아니라는 것이 이 파트의 메시지입니다.",
    "Ch.10 Monitoring Is How You Learn · Monitoring Patterns · Ch.11 Conclusion")

add("분업: 멀티에이전트", "02-⑤ 분업 · Ch.8", 75,
    grid(box("책의 예: 공급망 에이전트", "단일 에이전트 + 도구 16개 → 고를 도구가 많아 성능 저하<br>"
             "→ 감독 에이전트가 질의를 <b>재고·창고 / 운송 / 공급사·규정</b> 전문 에이전트 3개로 라우팅 · 에이전트마다 도구와 프롬프트가 좁아져 선택 오류 감소")
         + box(xp("확인") + "도구가 늘면 선택이 흔들림 (앞의 메타데이터 실험)", f"모호한 설명일 때 도구 6개 {pct(rec[1][0])} → 30개 {pct(rec[1][2])} · 입력 토큰 {tok[0]:,} → {tok[2]:,} — 한 에이전트에 도구를 계속 붙이는 비용", "teal")
         + note("조정 방식: 민주적(합의) · 관리자(중앙 배분) · 계층적 · 행위자–비평자 — 견고성·속도·복잡도의 트레이드오프"),
         table(["추가 원칙", "의미"], [
             ["작업 분해", "겹치지 않는 하위 작업으로 나눔"], ["전문화", "역할에 맞는 도구와 프롬프트"],
             ["절약 (parsimony)", "필요한 최소 수만 — 기존 에이전트 보강으로 되면 추가하지 않음"], ["조정", "통신 규칙과 충돌 해결"],
             ["견고성", "한 에이전트가 실패해도 전체는 유지"], ["효율", "추가 이득 vs 통신·지연 비용"]], cls="compact-table small-rows"),
         cls="wide-left")
    + take("시작은 단일 에이전트 — 복잡도·도구 수·조정 요구가 한 에이전트를 넘어설 때 분할 (8장)"),
    "다섯 번째가 오늘 도입에서 말씀드린 멀티에이전트, 분업입니다. 8장의 첫 문장은 대부분의 사례는 에이전트 하나로 시작한다는 것입니다. 단일 에이전트가 더 단순하고, 싸고, 빠르기 때문입니다. "
    "언제 나누느냐에 대한 책의 예는 공급망 에이전트입니다. 도구 16개를 한 에이전트에 붙이면 고를 도구가 너무 많아 성능이 떨어지고, 그래서 감독 에이전트 하나가 질의를 재고, 운송, 공급사 담당 전문 에이전트 셋에게 넘기는 구조로 바꿉니다. "
    "에이전트마다 도구와 프롬프트가 좁아지니 선택 오류가 줄어듭니다. 앞에서 본 도구 수 실험이 바로 이 문제를 보여 줍니다. 도구가 늘수록 선택률이 떨어지고 입력 토큰이 3배 넘게 늘었습니다. "
    "오른쪽은 책이 제시하는 에이전트 추가 원칙입니다. 특히 절약 원칙이 중요한데, 에이전트 하나를 더할 때마다 통신과 조정 비용이 생기므로 기존 에이전트를 보강해서 되면 추가하지 말라는 것입니다. "
    "멀티에이전트는 출발점이 아니라, 단일 에이전트가 감당하지 못할 때 도달하는 지점입니다.",
    "Ch.8 How Many Agents Do I Need? · Principles for Adding Agents · Multiagent Coordination")

def proto(tag, title, sub, color, inner):
    return f'<div class="proto {color}"><div class="proto-head"><span>{tag}</span><b>{title}</b><small>{sub}</small></div>{inner}</div>'


def seq(left, right, msgs, color=""):
    return (f'<div class="mcp-diagram"><div class="actor">{left}</div><div class="msgs">' + "".join(f'<span class="{m[0]}">{m[1]}</span>' if isinstance(m, tuple) else f'<span class="{"back" if m.startswith("←") else "fwd"}">{m}</span>' for m in msgs)
            + f'</div><div class="actor {color}">{right}</div></div>')


add("연결의 표준: MCP와 A2A", "02-⑤ 분업 · Ch.4, 8", 50,
    grid(proto("MCP", "에이전트 ↔ 도구", "Model Context Protocol · 4장", "teal",
               '<p class="proto-def">에이전트가 <b>도구</b>를 쓰는 방식의 표준 — “AI의 USB-C 포트”</p>'
               + seq("에이전트<small>클라이언트</small>", "MCP 서버<small>DB · API · 업무 로직</small>",
                     ["→ tools/list", "← 도구마다 이름 · 설명 · 입력 형식", ("local l", "에이전트가 목록에서 도구 선택"), "→ tools/call", "← 결과"], "teal")
               + '<ul class="proto-list"><li><b>상대</b>: 호출되면 실행만 하는 기능</li>'
               '<li><b>효과</b>: 서비스마다 따로 짜던 연결 코드를 하나의 규격으로</li>'
               '<li><b>한계</b>: 인증·접근 제어는 표준이 강제하지 않음</li></ul>'
               + f'<p class="proto-ev">{xp("빈틈")} 책 예제는 목록을 받고도 키워드 규칙으로 선택 → 정답률 {pct(MCP_KW)} · 서버 버그 2개 수정 + 설명 기반 선택 → {pct(MCP_BEST)}</p>'),
         proto("A2A", "에이전트 ↔ 에이전트", "Agent-to-Agent Protocol · 8장", "violet",
               '<p class="proto-def">에이전트가 <b>다른 에이전트</b>에게 일을 맡기는 방식의 표준</p>'
               + seq("요청 에이전트", "전문 에이전트<small>내부 구현 비공개</small>",
                     ["→ Agent Card 조회<small>레지스트리 또는 /.well-known/agent.json</small>", "← Agent Card · 핸드셰이크", "→ 작업 요청 (JSON-RPC)",
                      ("local r", "상대가 처리 방법을 스스로 결정"), "← 결과"], "violet")
               + '<ul class="proto-list"><li><b>상대</b>: 스스로 판단하는 에이전트</li>'
               '<li><b>한계</b>: 아직 초기 단계 — 권한 · 신뢰 · 남용 방지 미해결</li></ul>'
               + code('''{"identity": "SummarizerAgent", "capabilities": ["summarizeText"],
 "endpoint": "http://localhost:8000/api", "auth_methods": ["none"]}''', "Agent Card = 정체 · 능력 · 입출력 형식 · 엔드포인트 · 인증 방식 (책의 예, 요약)")),
         cls="proto-grid")
    + take("MCP는 도구를 <b>부르는</b> 규격, A2A는 에이전트에게 <b>맡기는</b> 규격 — 둘 다 상대가 자기를 설명하는 형식을 표준화함"),
    f"여러 에이전트와 도구를 잇는 표준 두 가지를 따로 보겠습니다. 왼쪽 MCP는 에이전트와 도구 사이의 표준입니다. 에이전트가 MCP 서버에 도구 목록을 물으면 서버가 앞에서 본 이름, 설명, 입력 형식을 돌려주고, 에이전트는 그중 쓸 도구를 직접 고른 뒤 입력 형식에 맞춰 호출합니다. "
    f"서비스마다 따로 짜던 연결 코드를 하나의 규격으로 바꾼다는 뜻에서 책은 AI의 USB-C 포트라고 부릅니다. 다만 표준이 선택까지 해결해 주지는 않습니다. 책의 MCP 예제를 돌려 보니 도구 목록을 받아 놓고도 키워드 규칙으로 도구를 골라 정답률이 {pct(MCP_KW)}였고, "
    f"서버 버그 두 개를 고치고 모델이 설명을 보고 고르게 하자 {pct(MCP_BEST)}가 됐습니다. "
    f"오른쪽 A2A는 에이전트와 에이전트 사이의 표준입니다. 상대가 실행만 하는 도구가 아니라 스스로 판단하는 에이전트라는 점이 다릅니다. 각 에이전트는 자기 정체와 능력, 접속 주소, 인증 방식을 적은 Agent Card를 공개하고, "
    f"다른 에이전트는 레지스트리나 정해진 주소에서 그 카드를 받아 버전과 시간 제한 같은 조건을 맞춘 뒤 작업을 맡깁니다. MCP에서는 고르는 쪽이 요청하는 에이전트였다면, A2A에서는 맡은 쪽이 처리 방법을 스스로 정하고, 내부 구현은 드러내지 않습니다. 책은 A2A가 아직 초기 단계이고 권한과 신뢰 문제는 풀리지 않았다고 분명히 말합니다. "
    f"정리하면 MCP는 도구를 부르는 규격, A2A는 에이전트에게 맡기는 규격입니다.",
    "Ch.4 p.78–84 Model Context Protocol · Ch.8 p.189–192 Agent-to-Agent Protocol · repro/hypotheses.py mcp_fix")

add("보호: 보안과 사람의 감독", "02-⑥ 보호 · Ch.12–13", 65,
    grid(box("에이전트 고유의 위험 (12장)", "<b>목표 오해</b>: 모호한 지시를 의도와 다르게 해석 · <b>확률적 출력</b>: 그럴듯한 오답(환각) · <b>적응성</b>: 작은 입력 변화에도 예측하기 어려운 행동")
         + box("실제 사례", "자동차 딜러 챗봇이 프롬프트 주입에 넘어가 7만 6천 달러 차량을 1달러에 제안 (12장) · 에이전트가 DB “최적화”로 운영 테이블 행 절반 삭제 (4장)", "amber")
         + box("책의 처방", "역할 기반 접근 제어 · 행동 제약 · 이상 탐지 · 대체 경로 · 레드팀", "teal"),
         '<div class="code-title">사람의 역할 변화 (13장)</div>' + flow(("실행자", "사람이 작업을 시작하고 결과를 직접 확인"), ("검토자", "중요 지점에서 에이전트의 결정을 검토"),
              ("협업자", "역할을 나눠 함께 작업"), ("감독자", "정책과 경계를 정하고 전체를 감독"), cls="vertical")
         + note("13장: 신뢰가 쌓일수록 위임 확대 — 초안·제안에서 시작하는 점진적 위임 · 3장: 능력과 한계를 사용자에게 분명히 알림")),
    "마지막 조건은 보호입니다. 12장은 에이전트만의 위험을 세 가지로 봅니다. 모호한 지시를 의도와 다르게 해석하는 목표 오해, 그럴듯하지만 틀린 답을 내는 확률적 출력, 그리고 작은 입력 변화에도 행동이 달라지는 예측의 어려움입니다. "
    "사례도 있습니다. 한 자동차 딜러의 챗봇은 프롬프트 주입에 넘어가 7만 6천 달러짜리 차를 1달러에 팔겠다고 했고, 앞에서 본 DB 삭제 사고도 같은 맥락입니다. 처방은 역할 기반 접근 제어, 행동 제약, 이상 탐지, 대체 경로, 레드팀입니다. "
    "13장은 사람의 역할을 다룹니다. 처음에는 사람이 작업을 직접 시작하고 확인하는 실행자에서, 검토자, 협업자를 거쳐 정책과 경계를 정하는 감독자로 옮겨 갑니다. "
    "핵심은 신뢰가 쌓이는 만큼만 위임을 넓히는 점진적 위임이고, 3장의 말대로 에이전트가 무엇을 할 수 있고 없는지를 사용자에게 분명히 알리는 것도 여기에 포함됩니다.",
    "Ch.12 The Unique Risks of Agentic Systems · Securing Agents · Ch.13 Roles and Autonomy")

# ---------------- 03 · Close --------------------------------------------------------------------
add("정리", "03 · Conclusion", 55,
    '<div class="conclusion-list">'
    + "".join(f'<div><span>{i}</span><p>{t}</p></div>' for i, t in enumerate([
        "에이전트 = 맥락에 따라 <b>스스로 결정</b>하는 시스템. 모델 하나가 아니라 <b>모델 + 도구 + 메모리 + 오케스트레이션 + 인프라</b>",
        "먼저 물을 것: 정말 에이전트가 필요한가 — 코드·워크플로·RAG로 충분하면 그쪽",
        "제대로 구현하려면 <b>도구 · 계획 · 기억 · 검증과 운영 · 분업 · 보호</b> — 모델이 좋아져도 남는 일",
        "멀티에이전트는 출발점이 아니라 도착점 — 단일 에이전트를 측정하고 다듬은 뒤 필요할 때 분할",
    ], 1)) + "</div>"
    + take("에이전트를 ‘가끔’이 아니라 ‘항상’ 동작하게 만드는 것은 모델이 아니라 시스템 설계 — 직접 확인한 도구 실험의 결론도 동일"),
    "정리하겠습니다. 에이전트는 맥락에 따라 스스로 결정하는 시스템이고, 모델 하나가 아니라 도구, 메모리, 오케스트레이션, 인프라를 갖춘 전체입니다. "
    "에이전트를 만들기 전에 먼저 물어야 할 것은 정말 에이전트가 필요한가이고, 코드나 워크플로, RAG로 충분하면 그쪽이 낫습니다. "
    "에이전트가 필요하다면, 도구, 계획, 기억, 검증과 운영, 분업, 보호라는 여섯 가지 조건을 갖춰야 합니다. 이건 모델이 좋아져도 사라지지 않는 일입니다. "
    "그리고 멀티에이전트는 출발점이 아니라, 단일 에이전트를 측정하고 다듬은 뒤 필요할 때 도달하는 지점입니다. "
    "처음 질문으로 돌아가면, 에이전트를 가끔이 아니라 항상 동작하게 만드는 건 모델이 아니라 시스템 설계이고, 제가 직접 돌려 본 도구 실험도 같은 결론이었습니다. 감사합니다.",
    "발표 요약")

MAIN = len(slides)
assert sum(s["seconds"] for s in slides) == 1140, sum(s["seconds"] for s in slides)


def app(title, body, notes, source):
    add(title, "Appendix · Q&A", 0, body, notes, source)


if D1:
    app("부록 · 도구 선택 실험 전체 수치",
        table(["도구 수", "메타데이터", "정답 도구 선택률", "호출 중 정답 비율", "인자 정확도", "무호출", "입력 토큰", "지연"],
              [[str(s["n_tools"]), "좋음" if s["description"] == "good" else "나쁨", pct(s["tool_recall"]), pct(s["tool_precision"]),
                pct(s["parameter_accuracy"]), pct(s["no_tool_call_rate"]), f'{s["mean_input_tokens"]:,}', f'{s["mean_latency_s"]:.1f}s'] for s in D1["summary"]],
              cls="compact-table center")
        + note(f"{esc(d1_model)} · temperature 0 · 1회 실행 · 질의 24개. 지표 정의는 책 9장(tool recall · precision · parameter accuracy)."),
        "도구 선택 실험의 전체 수치입니다.", "results/d1_tool_selection.json")

app("부록 · tool_choice 설정 실험",
    tc_tbl + note("산술 질의 중 도구를 호출한 비율 · 요청 본문에 설정이 실려 간 것을 확인했는데도 로컬 모델 서버(Ollama)가 경고 없이 무시")
    + note(f"과한 강제도 문제: 곱셈을 고정하면 “Say hello in French.”에도 <code>{esc(pin_txt)}</code>"),
    "도구 사용 설정 실험의 전체 수치입니다.", "demos/d5_tool_choice.py · results/d5_tool_choice.json")

app("부록 · 도구의 종류",
    table(["유형", "정의", "장점", "주의점"], [
        ["<b>로컬</b>", "에이전트와 함께 배포되는 함수", "정확·예측 가능 (산술, 날짜, 지도)", "팀마다 중복 구현, 재배포 필요"],
        ["<b>API</b>", "외부 서비스 호출", "실시간 데이터, 무거운 계산", "장애·호출 제한·보안"],
        ["<b>플러그인</b>", "플랫폼이 제공하는 모듈", "빠른 통합", "맞춤화 한계"],
        ["<b>MCP</b>", "도구 연결 표준 프로토콜", "한 번 만들어 여러 에이전트가 재사용", "인증·접근 제어는 미표준"],
        ["<b>상태 도구</b>", "DB처럼 영속 데이터를 바꾸는 도구", "실제 업무 수행", "파괴적 실수·악용"],
        ["<b>자동 생성</b>", "모델이 도구 코드를 직접 작성", "새 API에 빠르게 적응", "품질·보안·반복성"],
    ], cls="compact-table")
    + note("아래로 갈수록 할 수 있는 일이 커지고, 그만큼 잘못됐을 때의 피해도 커짐"),
    "책 4장이 구분하는 도구 유형입니다.", "Ch.4 p.73–87")

r3_book = next((p for p in (R3 or {}).get("probes", []) if "book-repo" in p["server"]), None)
bl = (D3 or {}).get("part_a", {}).get("book_loop_as_written", {})
a2 = (D2 or D2_RUN1 or {}).get("part_a", {}).get("A2_book_stock_tool", {})
R0, R0B = load("r0_book_originals.json"), load("r0b_book_minimal.json")


def r0_cell(key):
    row = next((r for r in (R0 or {}).get("results", []) if r["example"] == key), None)
    if not row:
        return PENDING
    run = row["runs"]["current"]
    return tag(run["exit"] == 0, "동작", "실패") + (f' <small>{esc((run["error_last_line"] or "")[:70])}</small>' if run["exit"] != 0 else "")


def r0b_cell(key, ok_note, answered=True, lines=None):
    row = (R0B or {}).get("results", {}).get(key)
    if not row:
        return PENDING
    run = row["runs"]["current"]
    n = lines if lines is not None else row["edits"][-1]["original_lines_changed"]
    ok = run["exit"] == 0 and answered
    return tag(ok, "동작", "답 실패" if run["exit"] == 0 else "실패") + f" <small>원본 {n}줄 수정 · {ok_note}</small>"


app("부록 · 책 예제를 그대로 실행했을 때",
    table(["책 예제", "원본 그대로 (모델 이름만 교체)", "최소 수정 후", "최소 수정의 내용"], [
        ["계산기 (p.74)", r0_cell("calculator"), r0b_cell("calculator", "정답", lines=1), "현재 환경은 모델 이름 외 수정 불필요 · 책이 고정한 구버전 LangChain에서는 도구 호출 방식 1줄 추가 수정"],
        ["Wikipedia (p.76)", r0_cell("wikipedia"), r0b_cell("wikipedia", "실행은 완료, 엉뚱한 문서를 검색", answered=False), "Wikimedia 정책에 맞는 User-Agent 지정 · 루프가 1회뿐이라 잘못된 검색을 회복 못함"],
        ["주가 (p.77)", r0_cell("stock_price"), r0b_cell("stock_price", "실제 시세"), "자리표시자 주소 → 실제 시세 API(키 없음, 비공식), 헤더, 응답 파싱"],
        ["MCP 클라이언트 (p.82–83)", r0_cell("mcp_client"), r0b_cell("mcp_client", "수학·날씨 응답"), "구버전 import, math→수학 서버, 문자열 입력→인자, 출력부 · 서버 2개는 MCP로 노출"],
    ], cls="compact-table small-rows")
    + note("모델: 원본의 gpt-4o(유료) 대신 qwen2.5:7b — 바꾼 것은 모델 이름 한 줄이고 diff로 기록. 책이 고정한 환경(langchain 0.1.20)에는 4장 예제가 쓰는 "
           "wikipedia·MCP 패키지가 빠져 있고, MCP 어댑터는 그 버전과 함께 설치 불가. 상태 도구·설정 절은 책에 코드가 없어 본편 실험은 본문을 구현한 것."),
    "책 예제를 원본 그대로 돌렸을 때와 실행을 막는 부분만 고쳤을 때를 비교했습니다. 바꾼 줄은 모두 diff 파일로 남겼습니다.",
    "repro/README.md · results/r0_book_originals.json · r0b_book_minimal.json")

def hv(key, path=("verdict",)):
    d = HW.get(key) or {}
    for k in path:
        d = d.get(k, {}) if isinstance(d, dict) else {}
    return d if isinstance(d, str) else "–"


VERDICT_KO = {"supported": "지지", "not supported": "지지 안 됨", "inconclusive": "불확정"}


def vk(v):
    for k, t in VERDICT_KO.items():
        if v.startswith(k):
            return tag(k == "supported", t, t) + (f" <small>{esc(v[len(k):].strip(' ()—-'))}</small>" if v[len(k):].strip() else "")
    if v.startswith("refuted"):
        return tag(False, "", "반증") + " <small>서버가 무시</small>"
    return esc(v)


app("부록 · 실패 원인 가설과 검증",
    table(["가설", "검증 결과", "판정"], [
        ["Wikipedia 원본 실패는 라이브러리 공용 User-Agent에 대한 호출 제한 때문", "기본 UA 429 4/6 · 식별 UA 0/6", vk(hv("w_ua"))],
        ["최소 수정판 오답은 모델이 질문 문장을 검색어로 쓰기 때문", "질문 문장 → 다른 인물 문서 · 이름만 → 정확한 문서", vk(hv("w_query"))],
        ["책의 1회 루프가 회복을 막음 / 검색 결과 1개가 취약함", "여러 단계·top_k=3 모두 0% — 모델이 같은 검색어 반복", vk(hv("w_loop", ("verdicts", "H1_multi_step")))],
        ["검색어는 도구 설명이 좌우함", f"설명 한 줄 변경: {pct(W_ORIG)} → {pct(W_TITLE)}", vk(hv("w_desc"))],
        ["MCP 예제의 병목은 서버가 아니라 키워드 라우터", "같은 서버에서 라우팅 42% → 100%", vk(hv("mcp"))],
        ["책 수학 서버는 정리 후 남은 앞 공백 때문에 실패", "strip 한 줄로 해결", vk(hv("mcp_fix", ("verdicts", "H-M2")))],
        ["날씨 실패는 서버 파서와 모델 인자의 불일치", f"서버가 도시 이름도 받으면 {pct(MCP_BEST)}", vk(hv("mcp_fix", ("verdicts", "H-M3b")))],
        ["tool_choice는 LangChain 연동만 무시함", "OpenAI 호환 API로 보내도 무시 · 요청 본문에는 포함", vk(hv("tc"))],
        ["명시적 규칙이 오류 후 답 지어내기를 줄임", "33% → 17% (6건) — 1건 차이", tag(True, "약한 지지", "") + " <small>규칙만으로 0이 되지 않음</small>"],
        ["책 코드는 고정 버전보다 새 LangChain 기준으로 작성됨", "langchain-core 0.2에서 원본 그대로 동작", vk(hv("ver"))],
    ], cls="compact-table small-rows")
    + note("각 가설은 실행 전 예측을 기록한 뒤 검증 · 상세: code/repro/HYPOTHESES.md · repro/hypotheses.py"),
    "책 예제가 목적을 달성하지 못한 지점마다 원인을 가설로 세우고 검증한 결과입니다.", "repro/HYPOTHESES.md · results/h_*.json")


app("부록 · 실행 환경과 한계",
    code('''cd ch4-tool-use
# .env: LLM_PROVIDER=ollama  LLM_MODEL=qwen2.5:7b
.venv\\Scripts\\python.exe repro\\check_llm.py
.venv\\Scripts\\python.exe demos\\d1_tool_selection.py --repeats 1
.venv\\Scripts\\python.exe demos\\d2_api_tools.py --llm
.venv\\Scripts\\python.exe demos\\d3_mcp.py --llm
.venv\\Scripts\\python.exe demos\\d4_stateful_sqlite.py --llm
.venv\\Scripts\\python.exe demos\\d5_tool_choice.py --llm''', "재현 명령")
    + grid(box("환경", f"Python {(D3 or {}).get('meta', {}).get('python', '3.14')} · LangChain 1.7 · MCP SDK 1.30 · Ollama · RTX 3050 6GB · temperature 0"),
           box("한계", "로컬 7B 모델 1종 · 질의 수 소규모 · 대부분 1회 실행 → 책의 주장을 확인하는 근거일 뿐, 모델 일반의 성능 주장이 아님", "amber")),
    "재현 명령과 환경, 해석의 한계입니다.", "ch4-tool-use/README.md")

app("출처",
    '<div class="reference-block"><p>Michael Albada · Building Applications with AI Agents: Designing and Implementing Multiagent Systems · O’Reilly</p>'
    '<div><a href="code/README.md" target="_blank">실험 코드 스냅숏</a><a href="SOURCES.md" target="_blank">출처·수치 기록</a>'
    '<a href="presentation_script.md" target="_blank">20분 발표 대본</a></div></div>'
    + note("책 저장소: github.com/michaelalbada/BuildingApplicationsWithAIAgents (commit eeb325a) · MCP 공식 Python SDK 1.30 · Wikimedia API 정책 w.wiki/4wJS"),
    "출처입니다.", "SOURCES.md")


# ---------- render --------------------------------------------------------------------------------
css = re.search(r"<style>(.*?)</style>", old, re.S)[1].replace(".vadtree", ".deck")
css += r"""
.deck .slide-body{padding:18px 56px 8px;height:532px}
.lead{font-size:22px;line-height:1.5;margin:0 0 16px;color:#354761;font-weight:500}
.reading{font-size:15px;line-height:1.6;color:#61708a;margin:12px 0 0}
.takeaway{margin-top:14px;padding:13px 18px;border-left:5px solid var(--teal);background:#e8f5f4;border-radius:8px;font-size:18px;font-weight:600;color:#123b3a;line-height:1.5}
.deck .box{padding:14px 18px;margin:0}.deck .box h3{font-size:19px;margin-bottom:6px}.deck .box p{font-size:16.5px;line-height:1.55}
.deck .grid-2,.deck .grid-3{gap:16px;margin-bottom:12px;align-items:start}
.deck .grid-2>div,.deck .grid-3>div{min-width:0}
.stack-gap>*+*{margin-top:12px}.cell{min-width:0}.cell>*+*{margin-top:12px}
.grid-2.wide-left{grid-template-columns:1.35fr 1fr}.grid-2.narrow-left{grid-template-columns:300px 1fr}
.grid-2.code-grid{grid-template-columns:1.25fr 1fr}.grid-2.code-grid>div:last-child>*+*,.grid-2.wide-left>div:last-child>*+*{margin-top:12px}
.grid-2.chart-grid{grid-template-columns:590px 1fr;align-items:center}
.code-wrap{min-width:0}.code-title{font-size:13px;font-weight:700;color:#61708a;margin:0 0 5px;letter-spacing:.2px}
pre.code{background:#111b31;color:#e6edf7;border-radius:10px;padding:12px 15px;font:14px/1.5 Consolas,'D2Coding',monospace;white-space:pre;overflow:hidden;margin:0}
.code-grid pre.code{font-size:13.5px}
:not(pre)>code{white-space:nowrap}
code{font-family:Consolas,'D2Coding',monospace;font-size:.92em;background:#e9eef7;border-radius:4px;padding:0 4px}
pre code{background:none;padding:0;font-size:inherit}
.flow{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:22px;margin:0 0 16px}
.flow .step{position:relative;background:white;border:1px solid var(--line);border-radius:10px;padding:10px 10px;text-align:center}
.flow .step b{display:block;font-size:15px;color:#172840;font-family:Consolas,'Noto Sans KR',sans-serif}
.flow .step span{display:block;font-size:13px;color:#61708a;margin-top:3px;line-height:1.35}
.flow .step:not(:last-child):after{content:'→';position:absolute;right:-19px;top:50%;transform:translateY(-50%);color:var(--teal);font-weight:800;font-size:18px}
.flow.big{gap:34px;margin:6px 0 22px}.flow.big .step{padding:20px 12px}.flow.big .step b{font-size:21px;font-family:'Noto Sans KR',sans-serif}.flow.big .step span{font-size:15px;margin-top:6px}
.flow.big .step:not(:last-child):after{right:-27px;font-size:22px}.flow.big .step:last-child{background:#172840}.flow.big .step:last-child b,.flow.big .step:last-child span{color:white}
.flow.vertical{grid-auto-flow:row;grid-auto-rows:auto;gap:16px;margin:0}
.flow.vertical .step{text-align:left;padding:9px 14px}.flow.vertical .step b{display:inline;margin-right:8px}.flow.vertical .step span{display:inline}
.flow.vertical .step b{font-size:17px}.flow.vertical .step span{font-size:15px}.flow.vertical .step{padding:12px 16px}
.flow.vertical .step:not(:last-child):after{content:'↓';right:auto;left:22px;top:auto;bottom:-17px;transform:none;font-size:14px}
.data-table.compact-table{font-size:15.5px}.data-table.compact-table th{padding:10px 12px;font-size:14.5px}.data-table.compact-table td{padding:9px 12px;line-height:1.4}
.data-table.center td:not(:first-child),.data-table.center th:not(:first-child){text-align:center}
.data-table.small-rows td{padding:6px 10px;font-size:14px}
.grid-2.narrow-left>div:first-child>*+*{margin-top:12px}.grid-2.wide-left>div:first-child>.box+.box{margin-top:12px}
.data-table th small{display:block;font-weight:400;font-size:12.5px;opacity:.85;margin-top:3px}.data-table.hl-last th:last-child{background:var(--teal)}.data-table.hl-last td:last-child{background:#e8f5f4!important}
.tag{display:inline-block;padding:1px 9px;border-radius:999px;font-size:13.5px;font-weight:700;white-space:nowrap}
.tag.ok{background:#dff3ea;color:#0b6b48}.tag.bad{background:#fbe4e1;color:#a3271b}
.tag.ok:before{content:'✓ '}.tag.bad:before{content:'✕ '}
.pending{display:inline-block;padding:2px 10px;border-radius:6px;background:#fff3d6;color:#7a5200;font-weight:700}
.chart-fig{margin:0;background:white;border:1px solid var(--line);border-radius:12px;padding:10px 12px 8px}
.chart .grid{stroke:#e6eaf1;stroke-width:1}.chart .base{stroke:#9aa6b8;stroke-width:1}
.chart .axis{font-size:12px;fill:#61708a}.chart .axis.cat{font-size:13px;fill:#354761;font-weight:600}.chart .val{font-size:12.5px;fill:#172033;font-weight:700}
.legend{display:flex;gap:18px;font-size:13px;color:#354761;padding:2px 4px 0}.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.mcp-diagram{display:grid;grid-template-columns:170px 1fr 170px;gap:14px;align-items:stretch;background:white;border:1px solid var(--line);border-radius:12px;padding:18px}
.mcp-diagram .actor{display:flex;flex-direction:column;justify-content:center;text-align:center;border-radius:10px;background:#172840;color:white;font-weight:800;font-size:18px;padding:14px}
.mcp-diagram .actor.teal{background:#0d6f6a}.mcp-diagram .actor small{display:block;font-weight:400;font-size:13px;opacity:.85;margin-top:6px}
.mcp-diagram .msgs{display:flex;flex-direction:column;gap:7px;justify-content:center}
.mcp-diagram .msgs span{font:14.5px Consolas,monospace;padding:6px 10px;border-radius:6px;background:#edf2fa}
.mcp-diagram .msgs span:nth-child(even){background:#e8f5f4;text-align:right}
.xp{display:inline-block;font-size:12px;font-weight:800;letter-spacing:.3px;padding:2px 8px;border-radius:5px;margin-right:6px;vertical-align:2px;color:white;white-space:nowrap}.xp.ok{background:var(--teal)}.xp.gap{background:#b07a14}.xp.new{background:var(--violet)}.lead .xp{vertical-align:3px}.proto-grid{grid-template-columns:1fr 1fr;align-items:stretch}.proto-grid>.cell{display:flex}.proto-grid .proto{flex:1;height:auto}.proto .code-wrap{margin-top:auto}.proto pre.code{font-size:13px;line-height:1.5;padding:8px 12px}.proto{height:100%;background:white;border:1px solid var(--line);border-top:4px solid var(--teal);border-radius:12px;padding:14px 18px;display:flex;flex-direction:column;gap:9px}.proto.violet{border-top-color:var(--violet)}.proto-head{display:flex;align-items:baseline;gap:10px}.proto-head span{font-size:13px;font-weight:800;letter-spacing:1.5px;color:white;background:var(--teal);padding:3px 9px;border-radius:6px}.proto.violet .proto-head span{background:var(--violet)}.proto-head b{font-size:22px;font-weight:800}.proto-head small{margin-left:auto;font-size:13px;color:var(--muted)}.proto-def{font-size:17px;line-height:1.5;color:#354761}.proto .mcp-diagram{grid-template-columns:118px 1fr 118px;padding:10px;gap:10px}.proto .mcp-diagram .actor{font-size:15px;padding:10px 6px}.proto .mcp-diagram .msgs span{font-size:13px;padding:5px 8px}.proto .mcp-diagram .actor.violet{background:#5b3f94}.proto .mcp-diagram .msgs{gap:5px}.proto .mcp-diagram .msgs span.fwd{background:#edf2fa;text-align:left}.proto .mcp-diagram .msgs span.back{background:#e8f5f4;text-align:right}.proto .mcp-diagram .msgs span{padding:4px 8px}.proto .mcp-diagram .msgs span small{display:block;font-size:11.5px;color:var(--muted);margin-top:1px}.proto .mcp-diagram .msgs span.local{background:none;border:1.5px dashed #b6c2d4;font-family:inherit;font-size:13px;font-weight:700;color:#354761;text-align:center}.proto .mcp-diagram .msgs span.local.l:before{content:'◀ ';color:var(--teal)}.proto .mcp-diagram .msgs span.local.r:after{content:' ▶';color:var(--violet)}.proto-list{list-style:none;font-size:15.5px;line-height:1.5;color:#3f4f68}.proto-list li+li{margin-top:4px}.proto-list b{color:var(--ink)}.proto-ev{margin-top:auto;font-size:14.5px;line-height:1.5;padding:9px 12px;background:#fff3dc;border-left:4px solid #d09a34;border-radius:0 8px 8px 0;color:#5a4410}
.toc-grid.four .toc-item{min-height:128px;padding:22px 22px}
.conclusion-list{display:flex;flex-direction:column;gap:11px}
.conclusion-list>div{display:flex;gap:16px;align-items:center;background:white;border:1px solid var(--line);border-radius:10px;padding:12px 18px}
.conclusion-list span{flex:none;width:34px;height:34px;border-radius:50%;background:#172840;color:white;display:grid;place-items:center;font-weight:800}
.conclusion-list p{font-size:19px;line-height:1.45;color:#22324c}
.agent-diagram{position:relative;height:330px;background:white;border:1px solid var(--line);border-radius:12px}
.agent-diagram>div{position:absolute;display:flex;flex-direction:column;justify-content:center;text-align:center;border-radius:12px;font-weight:800;font-size:18px}
.agent-diagram small{display:block;font-weight:400;font-size:13px;opacity:.85;margin-top:4px}
.agent-diagram .core{left:50%;top:50%;width:190px;height:96px;transform:translate(-50%,-50%);background:#172840;color:white}
.agent-diagram .part{width:170px;height:70px;background:#e8f5f4;color:#123b3a;border:1px solid #bfe3df}
.agent-diagram .p1{left:22px;top:22px}.agent-diagram .p2{right:22px;top:22px}.agent-diagram .p3{left:22px;bottom:22px}.agent-diagram .p4{right:22px;bottom:22px}
.ladder{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;align-items:end;margin-bottom:16px}
.ladder .rung{background:white;border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.ladder .rung b{display:block;font-size:19px;color:#172840;margin-bottom:6px}.ladder .rung span{font-size:15px;line-height:1.45;color:#3f4f68}
.ladder .rung em{display:block;font-style:normal;font-size:13.5px;line-height:1.45;color:#61708a;margin-top:8px}.ladder .r4 em{color:#cfe0f5}
.ladder .r1{min-height:140px}.ladder .r2{min-height:170px}.ladder .r3{min-height:200px}.ladder .r4{min-height:230px;background:#172840}.ladder .r4 b,.ladder .r4 span{color:white}
.req-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:8px 0 22px}
.req{background:white;border:1px solid var(--line);border-radius:12px;padding:20px 20px;min-height:150px}
.req-head{display:flex;align-items:center;gap:10px;margin-bottom:8px}.req-head span{flex:none;width:30px;height:30px;border-radius:50%;background:#172840;color:white;display:grid;place-items:center;font-weight:800;font-size:15px}
.req-head b{font-size:23px;color:#172840}.req-head small{margin-left:auto;font-size:13px;font-weight:700;color:#0d6f6a;background:#e8f5f4;border-radius:999px;padding:2px 9px}
.req p{font-size:18px;line-height:1.5;color:#22324c}.req p.miss{margin-top:10px;font-size:16px;color:#a3271b}
.book-map{display:grid;grid-template-columns:1fr 1.25fr 1.25fr;gap:16px}
.part-col{background:white;border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.part-col h3{font-size:20px;font-weight:800;color:#172840;margin-bottom:10px}.part-col h3 small{font-size:13px;font-weight:500;color:#61708a;margin-left:8px}
.chip{display:flex;align-items:center;gap:10px;padding:7px 10px;border-radius:8px;background:#f2f5fa;margin-bottom:7px;font-size:16px}
.chip b{flex:none;width:26px;height:26px;border-radius:50%;background:#172840;color:white;display:grid;place-items:center;font-size:13px}
.chip.hot{background:#0d6f6a;color:white;font-weight:700}.chip.hot b{background:white;color:#0d6f6a}
"""


def clock(n): return f"{n // 60:02}:{n % 60:02}"


t = 0
for s in slides:
    s["start"] = clock(t); t += s["seconds"]; s["end"] = clock(t); s["duration"] = clock(s["seconds"])
    s["page"] = 1; s["cue"] = f"선택 멘트(분위기 보고): {s['aside']}" if s["aside"] else ""

def fill_times(text):
    text = re.sub(r"@@S(\d+)@@", lambda m: slides[int(m.group(1)) - 1]["start"], text)
    return re.sub(r"@@E(\d+)@@", lambda m: slides[int(m.group(1)) - 1]["end"], text)


for s in slides:
    s["body"] = fill_times(s["body"])
parts = []
for i, s in enumerate(slides):
    if i == 0:
        body = ('<div class="title-top"><span class="pill dark">AI AGENTS · CONCEPT &amp; REQUIREMENTS</span><span>IRV_LAB SEMINAR · 20 MIN</span></div>'
                '<div class="title-main"><div class="title-rule"></div><h1>AI 에이전트의<br>개념과 구현 조건</h1><h2>Building Applications with AI Agents · Michael Albada · O’Reilly</h2>'
                '<p class="title-korean">AI 에이전트로 애플리케이션 만들기</p>'
                '<p class="authors">멀티에이전트 시스템의 설계와 구현</p></div>'
                f'<div class="title-meta"><div><small>PRESENTER</small><b>박천웅</b></div><div><small>AFFILIATION</small><b>IRV_Lab</b></div>'
                f'<div><small>DATE</small><b>2026. 10. 30.</b></div><div><small>TIME LIMIT</small><b>20 min</b></div></div>')
    else:
        stamp = f'{s["start"]}–{s["end"]} · {s["duration"]}' if s["seconds"] else "질의응답용 · 본편 시간 미포함"
        body = (f'<header class="slide-header"><div><div class="eyebrow">{s["section"]}</div><h2 class="slide-title">{s["title"]}</h2></div>'
                f'<div class="slide-kicker">AI Agents · {DATE}<br>{stamp}</div></header><div class="slide-body">{s["body"]}</div>'
                f'<footer class="slide-footer"><span class="source"><a href="SOURCES.md" target="_blank">{esc(s["source"])}</a></span>'
                f'<span class="slide-no">{i + 1:02} / {len(slides):02} · ' + ("MAIN" if i < MAIN else "APPENDIX") + "</span></footer>")
    parts.append(f'<section class="slide {"title-slide" if i == 0 else ""}" data-title="{esc(s["title"])}" aria-label="{i + 1}. {esc(s["title"])}">{body}</section>')

controls = old[old.index("<nav"):old.index("<script>")]
controls = re.sub(r'max="\d+"', f'max="{len(slides)}"', controls)
controls = re.sub(r"/ \d+</label>", f"/ {len(slides)}</label>", controls)
controls = controls.replace("논문 원문 확대", "이미지 확대").replace("제공된 PDF·src의 원문 이미지 · ", "")
js = old[old.index("const slides=[...document.querySelectorAll"):old.rindex("</script>")]
js = re.sub(r"const variance=.*?updateFusion\(\);\n", "", js, flags=re.S)
js = re.sub(r"const mainCount=\d+", f"const mainCount={MAIN}", js)
js = js.replace("| VADTree Seminar", "| AI Agents Seminar").replace("vadtreeTimer", "toolUseTimer")
assert "updateFusion" not in js and f"const mainCount={MAIN}" in js
head = old[:old.index("<style>")]
head = re.sub(r'<meta name="description" content="[^"]*">',
              '<meta name="description" content="AI 에이전트의 개념과 구현 조건 · IRV_Lab 2026.10.30 · 박천웅 · 20분 세미나">', head)
head = re.sub(r"<title>.*?</title>", "<title>AI Agents · 2026.10.30 Seminar</title>", head)
data = [{k: v for k, v in s.items() if k != "body"} for s in slides]
result = (head + "<style>" + css + '</style></head><body class="deck"><main class="viewport"><div id="deck">' + "".join(parts)
          + "</div></main>" + controls + "<script>const slideData=" + json.dumps(data, ensure_ascii=False) + ";\n" + js + "</script></body></html>")
(root / "index.html").write_text(result, encoding="utf8")
(root / "assets").mkdir(exist_ok=True)
(root / "assets/slide_manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf8")

# code snapshot so the folder is self-contained
snap = root / "code"  # overwrite in place: OneDrive can hold locks that make rmtree fail
for sub in ("demos", "repro", "results"):
    shutil.copytree(proj / sub, snap / sub, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "logs"))
for f in (".env.example", "requirements.lock.txt", "README.md"):
    if (proj / f).exists():
        shutil.copy2(proj / f, snap / f)

script = ["# AI 에이전트의 개념과 구현 조건 — 세미나 발표 대본", "", f"박천웅 · IRV_Lab · {DATE}", "",
          f"본편 **{MAIN}장 · 계획 19:00**, 전환 여유 **1:00**, 발표 제한 **20:00**. 부록 {len(slides) - MAIN}장은 본편에 포함하지 않습니다. "
          "실제 발화 시간은 리허설로 확인해야 합니다.", "", "## 시간 운영", "",
          "- 표지에서 `T`를 눌러 20분 타이머를 시작합니다. `T`는 일시정지/재개, `↺`는 초기화입니다.",
          "- 체크포인트: @@E3@@ 문제 제기 종료 / @@E6@@ 에이전트란 종료 / @@E11@@ 도구 종료 / @@E18@@ 구현 조건 종료 / @@E19@@ 정리 종료.",
          "- 1분 이상 늦으면 17장(MCP와 A2A)은 마지막 결론 한 문장만 말하고 넘어갑니다.", "",
          "## 본편 시간표", "", "| 장 | 주제 | 구간 | 배정 |", "|---|---|---|---|"]
for i, s in enumerate(slides[:MAIN]):
    script.append(f'| {i + 1:02} | {s["title"]} | {s["start"]}–{s["end"]} | {s["duration"]} |')
for i, s in enumerate(slides):
    script += ["", f"## Slide {i + 1:02}. {s['title']}", "",
               f"- 시간: {s['start']}–{s['end']} / {s['duration']}" if s["seconds"] else "- 시간: 질의응답용 · 본편 미포함",
               f"- 근거: {s['source']}", "", s["notes"]]
    if s["short"]:
        script += ["", "시간 부족 시: " + s["short"]]
    if s["aside"]:
        script += ["", "> 선택 멘트(분위기 보고, 슬라이드에는 없음): " + s["aside"]]
(root / "presentation_script.md").write_text(fill_times("\n".join(script)) + "\n", encoding="utf8")
print(json.dumps({"slides": len(slides), "main": MAIN, "planned_seconds": t if False else sum(s["seconds"] for s in slides),
                  "script_chars_main": sum(len(s["notes"]) for s in slides[:MAIN]),
                  "pending": [s["title"] for s in slides if "실행 대기" in s["body"]]}, ensure_ascii=False))
