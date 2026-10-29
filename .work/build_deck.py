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
add("AI 에이전트 시스템과 도구 사용", "Title", 15, "",
    "오늘은 AI 에이전트 시스템을 어떻게 설계하고 운영하는지 다룬 책 한 권을 소개하고, 그중 에이전트가 실제로 일을 하게 만드는 핵심인 도구 사용을 조금 깊게 보겠습니다. "
    "책을 읽지 않으셨어도 따라오실 수 있게 용어부터 정리하겠습니다.",
    "Michael Albada · Building Applications with AI Agents · O’Reilly")

add("목차", "Roadmap", 25,
    '<div class="toc-grid four">'
    '<button class="toc-item" data-jump="3"><span>00</span><div><h3>왜 이 주제인가</h3><p>말하는 모델에서 일하는 시스템으로 · 오늘의 출처</p></div><b>@@S3@@–@@E3@@</b></button>'
    '<button class="toc-item" data-jump="4"><span>01</span><div><h3>책 한 권의 지도</h3><p>에이전트란 · 언제 쓰나 · 13장 구성 · 구축과 운영</p></div><b>@@S4@@–@@E10@@</b></button>'
    '<button class="toc-item" data-jump="11"><span>02</span><div><h3>심화: 도구 사용</h3><p>작동 방식 · 도구 종류 · 표준 연결 · 위험 관리</p></div><b>@@S11@@–@@E18@@</b></button>'
    '<button class="toc-item" data-jump="19"><span>03</span><div><h3>정리</h3><p>에이전트의 신뢰성은 도구 설계에서 결정</p></div><b>@@S19@@–@@E19@@</b></button>'
    "</div>" + take("오늘의 질문: 언어 모델이 우리 프로그램을 실행할 수 있게 되면, 무엇을 모델이 아니라 시스템이 보장해야 하는가?"),
    "순서는 이렇습니다. 먼저 이 주제를 왜 다루는지 짧게 말씀드리고, 책 전체를 지도처럼 훑겠습니다. 에이전트가 무엇이고, 언제 쓰는 게 맞으며, 책이 설계부터 운영까지 어떤 순서로 다루는지 보겠습니다. "
    "그다음 책의 4장, 도구 사용을 심화로 다루고, 책의 주장 중 몇 가지는 제가 직접 실행해 확인한 결과를 근거로 붙였습니다. 관통하는 질문은 아래 한 줄입니다.",
    "발표 구성")

add("말하는 모델에서 일하는 시스템으로", "00 · Context", 55,
    flow(("챗봇", "질문에 글로 답함"), ("+ 도구", "검색·계산·API 호출"), ("+ 메모리·계획", "여러 단계를 이어 감"), ("에이전트 시스템", "판단하고 실제로 행동함"), cls="big")
    + grid(box("오늘의 출처", "Michael Albada, <b>Building Applications with AI Agents: Designing and Implementing Multiagent Systems</b> (O’Reilly). "
             "13장 구성 · 설계 → 구축 → 운영 → 사람과의 협업")
         , box("오늘 다루는 방식", "① 책 전체의 지도 — 각 장이 답하는 질문 하나씩<br>② 4장 <b>도구 사용</b> 심화 — 책의 주장 + 로컬 LLM으로 직접 확인한 결과<br>"
               "실험 수치는 책 주장의 근거로만 사용 · 모델 일반의 성능 주장 아님", "teal"))
    + take("에이전트를 만드는 일 = 좋은 모델을 고르는 일 + 모델 주변의 시스템(도구·메모리·검증·감시)을 설계하는 일"),
    "최근 LLM 활용은 질문에 글로 답하는 챗봇에서, 검색하고 계산하고 외부 시스템을 직접 조작하는 시스템으로 옮겨 가고 있습니다. 이런 시스템을 흔히 에이전트라고 부릅니다. "
    "오늘 소개할 책은 O'Reilly에서 나온 Building Applications with AI Agents로, 에이전트를 만들고 운영하는 전 과정을 13개 장에 걸쳐 다룹니다. "
    "오늘은 먼저 책 전체를 지도처럼 보고, 그중 4장 도구 사용을 깊게 보겠습니다. 4장의 몇몇 주장은 제 노트북의 로컬 모델로 직접 실행해 확인했는데, 그 수치는 근거로만 봐 주시면 됩니다.",
    "Preface · Ch.1 p.1", aside="저는 이 책을 대학원 수업 교재로 읽고 있습니다.")

# ---------------- 01 · Book overview ------------------------------------------------------------
add("에이전트란 무엇인가", "01 · Book Map · Ch.1", 70,
    grid('<div class="agent-diagram"><div class="core">기반 모델<small>LLM · 판단</small></div>'
         '<div class="part p1">도구<small>정보 조회 · 행동</small></div><div class="part p2">메모리<small>맥락 · 지식</small></div>'
         '<div class="part p3">오케스트레이션<small>계획 · 실행 순서</small></div><div class="part p4">인프라<small>배포 · 감시 · 보안</small></div></div>'
         + note("책의 용어 <b>agentic system</b> = 에이전트가 동작하는 데 필요한 전체: 모델 + 도구 + 메모리 + 오케스트레이션 + 인프라"),
         box("책의 정의", "데이터를 분석하고 환경을 해석해 <b>맥락에 따라 스스로 결정</b>하는 지능형 시스템 (p.1)")
         + box("자율성은 스펙트럼", "“에이전트”라 불리는 많은 시스템이 실제로는 정해진 스크립트를 실행할 뿐임. <b>판별 기준: 고정된 스크립트가 아니라 실제로 결정을 내리는가</b>", "amber")
         + box("가능해진 이유", "기반 모델이 글뿐 아니라 <b>함수 이름과 인자</b>를 구조화해 출력 가능 → 프레임워크가 그 함수를 실행", "teal"),
         cls="wide-left"),
    "책의 정의부터 보겠습니다. 에이전트는 데이터를 분석하고 환경을 해석해 맥락에 따라 스스로 결정하는 시스템입니다. 책은 여기서 중요한 단서를 답니다. 자율성은 있다 없다가 아니라 스펙트럼이고, "
    "에이전트라고 불리는 많은 시스템이 사실은 정해진 스크립트를 돌릴 뿐이라는 겁니다. 판별 기준은 실제로 결정을 내리느냐입니다. "
    "이게 가능해진 건 모델이 글뿐 아니라 어떤 함수를 어떤 인자로 부를지를 구조화해서 내놓을 수 있게 됐기 때문이고, 이것이 오늘 심화로 볼 도구 사용입니다. "
    "책은 모델 하나가 아니라 도구, 메모리, 오케스트레이션, 인프라까지 묶은 전체를 agentic system이라고 부릅니다.",
    "Ch.1 p.1–2")

add("언제 에이전트를 쓰는가", "01 · Book Map · Ch.1", 55,
    '<div class="ladder">'
    + "".join(f'<div class="rung r{i}"><b>{t}</b><span>{d}</span></div>' for i, (t, d) in enumerate([
        ("일반 코드", "입력이 완전히 예측 가능 · 밀리초 단위 지연 · 규제상 결정적 로직 필요"),
        ("결정적 워크플로", "분기를 미리 다 열거할 수 있음 · 재시도·승인 단계를 명시적으로 통제"),
        ("챗봇 · RAG", "자연어 이해와 문서 검색은 필요하지만 여러 단계의 자율 계획은 불필요"),
        ("에이전트", "입력이 다양하고 여러 단계의 판단과 도구 조합이 필요한 경우")], 1)) + "</div>"
    + grid(box("책이 제시한 네 가지 판단 기준", "입력의 변동성 · 필요한 추론의 복잡도 · 성능과 규제 제약 · 유지보수 부담"),
           box("핵심 태도", "에이전트는 가장 마지막 선택지. 단순한 방법으로 충분하면 그쪽이 더 빠르고 저렴하며 검증이 쉬움.", "teal")),
    "책 1장에서 실무적으로 가장 유용한 부분은 언제 에이전트를 쓰지 말아야 하는지입니다. 입력이 완전히 예측 가능하거나 지연이 밀리초 단위로 중요하거나 규제 때문에 결정적인 로직이 필요하면 그냥 코드가 낫습니다. "
    "분기를 미리 다 나열할 수 있으면 워크플로, 자연어 이해와 검색만 필요하면 챗봇이나 RAG로 충분합니다. 에이전트는 입력이 다양하고 여러 단계의 판단이 필요할 때 쓰는 마지막 선택지라는 게 책의 태도입니다.",
    "Ch.1 p.8–11 · Workflows and Agents")

add("책 13장의 구성", "01 · Book Map", 60,
    '<div class="book-map">'
    + "".join(f'<div class="part-col"><h3>{t}<small>{sub}</small></h3>' + "".join(
        f'<div class="chip{" hot" if n == 4 else ""}"><b>{n}</b><span>{name}</span></div>' for n, name in chs) + "</div>"
        for t, sub, chs in [
            ("기초", "무엇을, 누구를 위해", [(1, "에이전트 소개"), (2, "에이전트 시스템 설계"), (3, "에이전트 UX 설계")]),
            ("구축", "만들고 확장하기", [(4, "도구 사용"), (5, "오케스트레이션"), (6, "지식과 메모리"), (7, "경험으로부터의 학습"), (8, "하나에서 여럿으로")]),
            ("운영", "믿고 쓸 수 있게", [(9, "검증과 측정"), (10, "운영 모니터링"), (11, "개선 루프"), (12, "에이전트 보안"), (13, "사람–에이전트 협업")])]) + "</div>"
    + note("책 스스로 밝힌 성격: ML 기초 입문서도, 특정 도구의 단계별 튜토리얼도 아닌 <b>설계 판단과 트레이드오프</b>의 안내서 · 예제는 고객 지원, 법률, 공급망 등 업무 사례"),
    "책은 이렇게 세 부분입니다. 1장부터 3장은 기초로, 에이전트가 무엇이고 어떻게 설계하며 사용자는 어떻게 경험하는지를 다룹니다. 4장부터 8장은 구축으로, 도구, 오케스트레이션, 메모리, 학습, 멀티에이전트입니다. "
    "9장부터 13장은 운영으로, 평가, 모니터링, 개선, 보안, 사람과의 협업입니다. 책은 스스로 ML 입문서도 튜토리얼도 아니고 설계 판단과 트레이드오프를 안내하는 책이라고 말합니다. 표시한 4장이 오늘 심화로 볼 부분입니다.",
    "Preface p.xv–xvi · Table of contents")

add("첫 에이전트와 설계 요소", "01 · Book Map · Ch.2–3", 55,
    grid(code('''@tool
def cancel_order(order_id: str) -> str:
    """Cancel an order that hasn't shipped."""
    return f"Order {order_id} has been cancelled."

# 1) LLM이 cancel_order를 부를지 결정
# 2) 코드가 실제로 실행
# 3) LLM이 결과로 확인 메시지 작성''', "책 2장의 첫 예제: 전자상거래 고객지원 (요약)"),
         table(["설계 요소", "책이 묻는 질문"], [
             ["모델 선택", "어떤 크기·비용·지연의 모델인가"], ["도구", "어떤 행동을 허용하는가"], ["메모리", "무엇을 얼마나 기억하는가"],
             ["오케스트레이션", "어떤 순서로 계획하고 실행하는가"], ["트레이드오프", "성능 · 확장성 · 신뢰성 · 비용"],
             ["UX (3장)", "능력과 한계를 어떻게 알리고 신뢰를 쌓는가"]], cls="compact-table"), cls="code-grid")
    + take("책의 조언: 큰 설계 문서보다 작고 검증 가능한 한 조각(주문 취소)부터 — 성공 기준을 먼저 정의"),
    "2장은 책 전체의 축소판입니다. 고객지원 메일을 처리하는 에이전트를 예로 드는데, 범위를 주문 취소 하나로 좁혀서 시작합니다. 모델이 cancel_order를 부를지 결정하고, 코드가 실행하고, 모델이 확인 메시지를 씁니다. "
    "그리고 오른쪽의 설계 요소들, 모델 선택, 도구, 메모리, 오케스트레이션, 그리고 성능, 확장성, 신뢰성, 비용 사이의 트레이드오프를 짚습니다. 3장은 사용자 경험으로, 에이전트가 할 수 있는 것과 없는 것을 어떻게 알리고 신뢰를 쌓는지를 다룹니다.",
    "Ch.2 p.17–39 · Ch.3 p.41–69")

add("구축: 4–8장", "01 · Book Map · Building", 70,
    grid(box("4 · 도구", "에이전트가 정보를 얻고 행동하는 수단. 로컬·API·플러그인·MCP·상태 도구 → <b>오늘의 심화</b>", "teal"),
         box("5 · 오케스트레이션", "어떤 도구를 어떤 순서로? 도구 선택(생성형·의미 검색·계층적), 실행 구조(체인·트리·그래프), 계획 전략(ReAct, 계획–실행 분리)"),
         box("6 · 지식과 메모리", "컨텍스트 창 → 벡터 검색·RAG → 지식 그래프(GraphRAG) → 작업 메모리(화이트보드·메모)"),
         box("7 · 학습", "가중치를 바꾸지 않는 학습(경험을 예시로, 반성) vs 미세조정(SFT·DPO)"),
         box("8 · 여럿으로", "언제 에이전트를 나누나 · 조정 방식(민주적·관리자·계층·행위자–비평자) · 에이전트 간 프로토콜 A2A", "violet"),
         box("공통 조언", "가장 단순한 방법에서 시작 · 필요가 확인될 때만 복잡도 상향 (5장 결론)", "amber"), cols=3),
    "구축 파트입니다. 4장 도구는 잠시 뒤에 자세히 보겠습니다. 5장 오케스트레이션은 어떤 도구를 어떤 순서로 쓸지, 즉 도구 선택과 실행 구조, ReAct 같은 계획 전략을 다룹니다. "
    "6장은 메모리로, 컨텍스트 창에서 시작해 벡터 검색과 RAG, 지식 그래프, 작업 메모리까지 갑니다. 7장은 학습인데, 가중치를 건드리지 않고 경험을 예시나 반성으로 쓰는 방법과, 미세조정을 비교합니다. "
    "8장은 에이전트를 여러 개로 나눌 때의 조정 방식과 에이전트끼리 통신하는 A2A 프로토콜입니다. 장마다 반복되는 조언은 가장 단순한 방법부터 시작하라는 것입니다.",
    "Ch.4–8 conclusions")

add("운영: 9–13장", "01 · Book Map · Operating", 75,
    table(["장", "다루는 질문", "대표 내용"], [
        ["9 · 검증과 측정", "출시해도 되는가", "목표·지표 정의 · 평가 세트 · 도구/계획/메모리 단위 테스트 · 종단 통합 테스트 · 환각 검사"],
        ["10 · 운영 모니터링", "지금 잘 돌고 있는가", "실패 원인 · OpenTelemetry·Loki·Tempo·Grafana · 분포 변화 감지 · 섀도 모드·카나리"],
        ["11 · 개선 루프", "어떻게 나아지는가", "피드백 파이프라인 · 섀도 배포·A/B 테스트·밴딧 · 지속 학습"],
        ["12 · 보안", "어떻게 지키는가", "에이전트 고유 위험 · 모델·데이터·에이전트 보호 · 역할 기반 접근 제어 · 레드팀"],
        ["13 · 사람과 협업", "누가 책임지는가", "감독 · 투명성 · 공정성 · 설명 가능성 · 규제와 책임"],
    ], cls="compact-table")
    + take("책 분량의 3분의 1 이상(205–313쪽)이 “만든 다음”에 할애 — 확률적으로 동작하는 시스템은 만들기보다 믿고 쓰게 만드는 일이 더 어려움"),
    "운영 파트는 만든 다음의 이야기입니다. 9장은 출시해도 되는지 판단하는 평가, 10장은 실제 운영 중 모니터링, 11장은 피드백으로 개선하는 루프, 12장은 보안, 13장은 사람의 감독과 책임입니다. "
    "책 분량의 3분의 1 이상이 여기에 쓰인다는 점이 인상적입니다. 모델이 확률적으로 동작하기 때문에, 만드는 것보다 믿고 쓰게 만드는 일이 더 어렵다는 관점입니다.",
    "Ch.9–13 conclusions")

add("왜 도구 사용을 깊게 보는가", "01 → 02", 45,
    grid(box("도구 = 실제 행동의 통로", "“도구는 평범한 챗봇에서 사용자를 위해 실제 일을 하는 시스템으로 넘어가는 방법이다” (3장 결론)", "teal"),
         box("뒤의 모든 장이 도구를 다시 다룸", "5장 도구 선택 · 9장 도구 호출 평가 · 10장 도구 실패 감지 · 12장 도구 권한 제한"),
         cols=2)
    + lead("심화의 질문 세 가지: <b>모델은 도구를 어떻게 부르는가</b> · <b>어떤 도구를 어떻게 연결하는가</b> · <b>잘못 불렀을 때 무엇이 막아 주는가</b>"),
    "왜 도구를 골랐는지 말씀드리겠습니다. 책은 도구를 챗봇에서 실제로 일하는 시스템으로 넘어가는 통로라고 부르고, 뒤의 거의 모든 장이 도구를 다시 다룹니다. 도구 선택, 도구 호출 평가, 도구 실패 감지, 도구 권한 제한입니다. "
    "그래서 4장을 이해하면 책의 나머지가 훨씬 쉽게 읽힙니다. 심화에서는 세 가지 질문을 따라가겠습니다.",
    "Ch.3 p.69 · Ch.5, 9, 10, 12")

# ---------------- 02 · Tool use deep dive -------------------------------------------------------
add("모델은 도구를 어떻게 부르는가", "02 · Tool Use · Ch.4", 80,
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
           + box("로컬 모델 실행 결과", f"로컬 7B 모델({esc(d1_model.split(':', 1)[1])})로도 책의 예제가 정확한 인자로 동작 · 이후 실험은 모두 같은 모델", "violet"),
           cls="code-grid"),
    "이제 4장입니다. 도구 호출은 이 다섯 단계로 이뤄집니다. 함수를 도구로 등록하면 이름과 설명, 입력 형식이 모델에게 전달됩니다. 모델은 답 대신 multiply를 393과 12.25로 불러 달라는 요청을 냅니다. "
    "실제 계산은 우리 코드가 하고, 결과를 대화에 넣어 주면 모델이 그걸 근거로 최종 답을 씁니다. 가장 중요한 포인트는 모델이 직접 실행하지 않는다는 것입니다. 그래서 검증과 실패 처리는 전부 코드 쪽 책임이고, 오늘 심화 전체가 이 사실에서 출발합니다. "
    "참고로 책 예제를 로컬 7B 모델로 돌려 보니 정확한 인자로 잘 동작했고, 이후 실험도 같은 모델로 했습니다.",
    "Ch.4 p.72–75 · repro/r1_book_calculator.py")

add("도구의 종류", "02 · Tool Use · Ch.4", 45,
    table(["유형", "정의", "장점", "주의점"], [
        ["<b>로컬</b>", "에이전트와 함께 배포되는 함수", "정확·예측 가능 (산술, 날짜, 지도)", "팀마다 중복 구현, 재배포 필요"],
        ["<b>API</b>", "외부 서비스 호출", "실시간 데이터, 무거운 계산", "장애·호출 제한·보안"],
        ["<b>플러그인</b>", "플랫폼이 제공하는 모듈", "빠른 통합", "맞춤화 한계"],
        ["<b>MCP</b>", "도구 연결 표준 프로토콜", "한 번 만들어 여러 에이전트가 재사용", "인증·접근 제어는 미표준"],
        ["<b>상태 도구</b>", "DB처럼 영속 데이터를 바꾸는 도구", "실제 업무 수행", "파괴적 실수·악용"],
        ["<b>자동 생성</b>", "모델이 도구 코드를 직접 작성", "새 API에 빠르게 적응", "품질·보안·반복성"],
    ], cls="compact-table")
    + note("아래로 갈수록 할 수 있는 일이 커지고, 그만큼 잘못됐을 때의 피해도 커짐"),
    "책이 구분하는 도구는 여섯 가지입니다. 로컬 도구는 에이전트와 함께 배포되는 함수, API 도구는 외부 서비스, 플러그인은 플랫폼이 만들어 둔 모듈, MCP는 이걸 표준으로 연결하는 프로토콜, "
    "상태 도구는 데이터베이스처럼 영속 상태를 바꾸는 도구, 마지막은 모델이 도구 코드를 직접 만드는 경우입니다. 아래로 갈수록 할 수 있는 일이 커지고, 잘못됐을 때의 피해도 커집니다.",
    "Ch.4 p.73–87")

if D1:
    rec = [[d1_cell(n, q, "tool_recall") for n in (6, 15, 30)] for q in ("good", "poor")]
    tok = [d1_cell(n, "good", "mean_input_tokens") for n in (6, 15, 30)]
    d1_chart = bars([("좋은 메타데이터", BLUE), ("나쁜 메타데이터", AMBER)], ["6개", "15개", "30개"], rec, w=460, h=280, unit_label="정답 도구 선택률")
    d1_notes = (f"로컬 도구에서 책이 가장 강조하는 건 메타데이터입니다. 모델은 함수 본문을 보지 않고 이름과 설명, 입력 형식만 보고 도구를 고르기 때문에, 좁고 정확한 이름, 서로 구별되는 설명, 엄격한 입력 형식이 중요하다고 합니다. "
                f"이걸 확인해 봤습니다. 정답 도구 6개에 헷갈리는 방해 도구를 섞어 6개, 15개, 30개로 늘리고, 같은 함수의 이름과 설명만 모호하게 바꾼 조건과 비교했습니다. "
                f"좋은 메타데이터는 30개에서도 정답 도구를 {pct(rec[0][2])} 골랐고, 모호한 메타데이터는 {pct(rec[1][0])}, {pct(rec[1][1])}, {pct(rec[1][2])}로 떨어졌습니다. "
                f"또 도구 설명은 매번 모델 입력에 들어가기 때문에 도구 수만 늘려도 입력이 {tok[0]:,}에서 {tok[2]:,} 토큰으로 3배 넘게 커집니다. 도구를 많이 붙이는 건 공짜가 아니라는 뜻이고, 이 문제가 5장의 도구 선택으로 이어집니다.")
else:
    d1_chart, d1_notes, tok = lead(PENDING), "실행 후 채워집니다.", [0, 0, 0]
add("선택을 좌우하는 도구 설명", "02 · Local Tools · 확인 실험", 90,
    grid(lead("모델은 코드를 보지 않음 — <b>이름 · 설명 · 입력 형식</b>만 보고 선택 (p.73)")
         + grid(code('''get_current_weather
"Get the weather right now
 for a city. Not for future days."''', "좋은 메타데이터"), code('''place_info
"Gets information
 about a place."''', "나쁜 메타데이터 (같은 함수)"))
         + note(f"질의 24개 · 헷갈리는 방해 도구 포함(현재 날씨↔예보, 환율↔환전) · 입력 토큰: 6개 {tok[0]:,} → 30개 {tok[2]:,}")
         + box("두 번째 근거: 설명 한 줄이 검색어를 결정",
               f"Wikipedia 검색 도구 설명에 “입력은 문서 제목(예: 인물 이름)” 한 줄 추가 → 인물 6명 질문 성공 {pct(W_ORIG)} → {pct(W_TITLE)}. "
               "기존에는 질문 문장을 그대로 검색어로 사용해 엉뚱한 문서 반환", "teal"),
         d1_chart + note("세로축: 질의에 맞는 도구를 고른 비율 (tool recall)"), cls="wide-left"),
    d1_notes + (f" 두 번째 근거도 있습니다. 책의 Wikipedia 예제에서 모델은 질문 문장을 그대로 검색어로 넣어 엉뚱한 문서를 받았는데, 도구 설명에 입력은 문서 제목이라고 한 줄 적자 "
                f"인물 6명 질문의 성공률이 {pct(W_ORIG)}에서 {pct(W_TITLE)}로 올랐습니다. 설명 한 줄이 도구 선택뿐 아니라 인자까지 바꾼다는 뜻입니다." if W_TITLE is not None else ""),
    "Ch.4 p.73 · demos/d1_tool_selection.py · repro/hypotheses.py w_desc")

b_rows = []
for r in (D2 or D2_RUN1 or {}).get("part_b", []):
    res = r["result"]
    ko = {"primary ok": "정상", "primary flaky (503 x2)": "일시 오류 2회", "primary down -> backup": "주 서버 다운",
          "primary slow (timeout) -> backup": "주 서버 응답 지연", "both down -> cache": "두 서버 모두 다운", "invalid input": "잘못된 입력"}
    out = f'{res.get("price")} · {res.get("source")}' if "price" in res else esc(res.get("error", ""))
    b_rows.append([ko.get(r["scenario"], esc(r["scenario"])), str(r["n_requests"]), out])
add("외부 API 도구와 실패", "02 · API Tools · 확인 실험", 70,
    grid(box("책의 권고 (p.78)", "외부 서비스는 언제든 멈춤 → <b>신뢰성 · 우아한 실패 · 여러 제공자</b>, HTTPS·인증, 호출 제한, 개인정보 보호", "teal")
         + box("근거: 책 예제를 그대로 실행하면", "Wikipedia: 서비스 호출 제한(HTTP 429) 오류가 그대로 전파되어 에이전트 중단 · 주가: 자리표시자 주소로 연결 오류. "
               "원인 확인 후 최소 수정(식별용 User-Agent, 실제 시세 API) → 둘 다 동작 — 단, 장애 대비는 여전히 없음", "amber"),
         table(["주입한 장애 (모의 서버)", "요청", "결과 · 출처"], b_rows, cls="compact-table small-rows")
         + note("시간 제한 → 지수 백오프 재시도 → 백업 제공자 → 캐시(시각 표시) · 실패도 예외 대신 모델이 읽을 수 있는 결과로 반환"),
         cls="narrow-left"),
    "API 도구는 외부 서비스를 부르기 때문에 언제든 실패합니다. 책은 신뢰성, 우아한 실패, 여러 제공자를 권합니다. 그런데 책의 예제를 그대로 돌려 보니, 같은 요청을 반복하자 Wikipedia가 차단했고 그 오류가 그대로 터져 에이전트가 멈췄습니다. "
    "주가 예제도 시간 제한 없이 연결 오류를 던집니다. 그래서 책의 권고대로 도구를 보강해 장애를 일부러 주입해 봤습니다. 일시 오류는 재시도로, 주 서버 장애는 백업으로, 둘 다 죽으면 시각을 표시한 캐시 값으로 넘어갑니다. "
    "핵심은 실패도 예외로 던지지 않고 모델이 읽을 수 있는 결과로 돌려줘서, 모델이 사용자에게 상황을 설명하게 하는 것입니다.",
    "Ch.4 p.75–78 · demos/d2_api_tools.py · 상세: 부록")

add("MCP: 도구 연결의 표준", "02 · Plug-ins & MCP · 확인 실험", 85,
    grid('<div class="mcp-diagram"><div class="actor">클라이언트<small>에이전트</small></div>'
         '<div class="msgs"><span>→ initialize</span><span>← 서버 정보</span><span>→ tools/list</span><span>← 이름 · 설명 · 입력 형식</span>'
         '<span>→ tools/call</span><span>← 결과</span></div><div class="actor teal">서버<small>DB · API · 업무 로직</small></div></div>'
         + note("플러그인은 플랫폼마다 방식이 제각각 (ChatGPT 전용 플러그인, Claude·Gemini의 함수 호출 API) → 표준이 필요 · MCP = JSON-RPC 2.0, “AI의 USB-C 포트”"),
         bars([("책 방식: 키워드 규칙", AMBER), ("모델이 tools/list로 선택", BLUE)], ["최종 정답률 (질의 12개)"], [[MCP_KW], [MCP_BEST]], w=380, h=240)
         + box("근거", "책의 서버는 표준(MCP)을 따르지 않아 연결 불가 → 같은 로직을 MCP로 노출하고, 실험으로 원인을 확인한 버그 2개(앞 공백, 도시 이름)만 수정", "amber"),
         cls="wide-left"),
    f"도구가 많아지면 연결 방식이 문제입니다. 책은 플랫폼마다 플러그인 방식이 달랐던 상황을 짚고, 그 표준으로 MCP를 소개합니다. 클라이언트가 서버에 접속해 tools/list로 도구 목록과 설명을 받아 오고, tools/call로 호출합니다. "
    f"서버를 한 번 만들면 어떤 에이전트든 재사용할 수 있어서 AI의 USB-C 포트라고 부릅니다. 다만 책도 인정하듯 인증과 접근 제어는 아직 표준이 강제하지 않습니다. "
    f"책의 예제 서버는 실제로는 표준을 따르지 않아 공식 클라이언트와 연결이 안 됩니다. 그래서 책 서버의 로직은 그대로 두고 MCP로만 노출했습니다. 책의 에이전트는 받은 목록을 두고도 연산 기호나 weather라는 단어로 도구를 고르는데, "
    f"질의 12개의 최종 정답률이 {pct(MCP_KW)}였습니다. 실패를 추적해 보니 수학 서버가 공백 처리 버그로 자기 예제도 못 풀었고, 날씨 서버는 'weather in 도시' 문구만 이해했습니다. 이 두 줄을 고치고 모델이 도구 설명을 보고 고르게 하자 {pct(MCP_BEST)}가 됐습니다. "
    f"표준의 장점인 발견 기능을 살리려면 선택도 설명 기반이어야 합니다.",
    "Ch.4 p.78–84 · repro/hypotheses.py mcp_fix · 상세: 부록")

cases = [r for r in (D4 or {}).get("battery", []) if "case" in r]
case_names = list(dict.fromkeys(r["case"] for r in cases))
case_ko = {"benign read": "정상 조회", "'optimize': delete old rows (the book's incident)": "“최적화”라며 오래된 행 삭제",
           "injected DROP": "주입된 테이블 삭제", "mass UPDATE": "전체 이메일 덮어쓰기", "planted admin row": "관리자 계정 몰래 추가"}


def dmg(design, case):
    r = next(x for x in cases if x["design"] == design and x["case"] == case)
    return tag(not r["damaged"], "무손상", "손상")


add("상태를 바꾸는 도구와 최소 권한", "02 · Stateful Tools · 확인 실험", 90,
    grid(box("책의 실제 사고 사례 (p.84)", "에이전트가 DB 성능을 “최적화”한다며 운영 테이블의 행 절반을 삭제. 악의가 없어도 의도를 오해하면 발생", "amber")
         + box("책의 처방: 최소 권한", "① 임의 SQL 대신 좁은 연산만 도구로 ② 위험 구문 거부·파라미터 바인딩 ③ 읽기 전용 계정 ④ 모든 호출 기록·알림", "teal"),
         table(["모델이 보낼 수 있는 호출", "임의 SQL 도구", "DROP·ALTER만 차단", "좁은 도구 + 읽기 전용"],
               [[case_ko.get(c, esc(c))] + [dmg(d, c) for d in ("raw", "blocklist", "scoped")] for c in case_names], cls="compact-table center small-rows")
         + note(f"같은 요청(“느린 고객 테이블을 정리해 달라”)을 실제 모델에게: 임의 SQL 도구 → {sum(1 for x in raw_deleted if x > 0)}/{len(raw_runs)}회 DELETE 실행, "
                f"매회 200명 중 {raw_deleted[0] if raw_deleted else '–'}명 삭제 · 좁은 도구 → {sum(1 for r in scoped_runs if r['after'] == r['before'])}/{len(scoped_runs)}회 무손상, 삭제 후보만 보고"),
         cls="narrow-left"),
    "도구가 데이터를 바꿀 수 있게 되면 위험이 커집니다. 책은 에이전트가 DB를 최적화한다며 운영 테이블의 행 절반을 지운 실제 사고로 이 절을 시작합니다. 처방은 최소 권한입니다. 임의 SQL을 열어 주지 말고 좁은 연산만 도구로 등록하고, "
    "읽기 전용 계정을 쓰고, 모든 호출을 기록하라는 것입니다. SQLite로 확인해 봤습니다. 헷갈리거나 공격받은 모델이 보낼 법한 호출 다섯 가지를 세 가지 설계에 보냈더니, 임의 SQL은 대부분 손상됐고, "
    "위험 구문 몇 개만 막는 방식은 테이블 삭제 하나만 막고 사고 사례인 대량 삭제는 그대로 통과했습니다. 좁은 도구는 모두 무손상이었습니다. 실제 모델에게 테이블 정리를 요청하자 임의 SQL 도구를 받은 모델은 매번 고객 115명을 지웠고, "
    "좁은 도구를 받은 모델은 삭제 후보만 보고했습니다. 모델은 요청을 따랐을 뿐이고, 되돌릴 수 없는 작업이 확인 없이 가능했느냐는 도구 설계가 정합니다.",
    "Ch.4 p.84–85 · demos/d4_stateful_sqlite.py")

add("모델이 도구를 만드는 경우", "02 · Automated Tool Development", 20,
    flow(("명세 입력", "API 문서·예시"), ("초안 생성", "모델이 래퍼 작성"), ("샌드박스 실행", "오류 확인"), ("자기 수정", "반복"), ("사람 검토", "배포 전"))
    + grid(box("장점", "수십 개 API 클라이언트의 반복 코드 절감 · 새 API에 즉시 적응", "teal"),
           box("책이 꼽은 위험", "품질 · 보안 · 자원 소비 · <b>반복성</b>: 매번 새로 만들면 같은 입력에도 다른 코드가 나와 테스트와 인증이 어려움", "amber")),
    "모델이 도구 코드를 직접 만드는 경우도 있습니다. 명세를 주고 초안을 만들게 한 뒤 샌드박스에서 실행하고 고치는 루프입니다. 책이 강조하는 건 배포 전 사람의 검토, 그리고 반복성 문제입니다. 이 부분은 실험하지 않았습니다.",
    "Ch.4 p.85–87")

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
add("도구 사용 설정과 검증", "02 · Tool Use Configuration · 확인 실험", 80,
    grid(tc_tbl + note("산술 질의 중 도구를 호출한 비율 · 요청 본문에 설정이 실려 간 것을 확인했는데도 로컬 모델 서버(Ollama)가 경고 없이 무시 → none을 줘도 100% 호출"),
         box("책의 권고 (p.87–88)", "응답마다 확인: <b>검증</b>(형식·도구 이름) → <b>재시도</b>(일시 오류만, 백오프) → <b>대체</b>(백업·캐시·안전한 기본값) → <b>모든 단계 기록</b>", "teal")
         + box("확인 결과: 오류를 알려도 답을 지어냄", f"도구 실패를 알렸는데도 모델이 {n_bad}/{len(b5)}회 곱셈 결과를 지어냄(예: 60.0). "
               "→ 최종 답을 도구 결과와 대조하는 검사 추가 후 모두 정답 또는 명시적 실패로 전환", "amber")
         + note(f"과한 강제도 문제: 곱셈을 고정하면 “Say hello in French.”에도 <code>{esc(pin_txt)}</code>"), cls="wide-left")
    + take("설정은 의도의 선언일 뿐 — 꼭 지켜야 할 제약과 답의 근거는 코드가 확인"),
    f"마지막으로 도구 사용 설정입니다. 책은 tool_choice라는 설정으로 모델이 도구를 알아서 쓸지, 반드시 쓸지, 쓰지 못하게 할지, 특정 도구로 고정할지 정할 수 있다고 합니다. 그런데 로컬 모델 연동에서는 이 설정이 경고 없이 무시돼서, "
    f"호출 금지를 줘도 산술 질의의 {pct(nr['tool_rate_math'])}에서 도구를 불렀습니다. 코드로 강제하면 {pct(er['tool_rate_math'])}가 됩니다. 반대로 곱셈을 고정하면 인사말 질문에도 인자를 지어냅니다. "
    "책은 응답마다 검증, 재시도, 대체, 기록을 하라고 권하는데, 해 보니 하나가 더 필요했습니다. 도구가 실패했다고 알려 줘도 모델이 결과를 지어낸 경우가 있어서, 최종 답의 숫자를 실제 도구 결과와 대조하는 검사를 넣었고, "
    "그러자 모두 정답이거나 명시적인 실패로 바뀌었습니다. 설정은 의도의 선언일 뿐이고, 보장은 코드가 해야 한다는 결론입니다.",
    "Ch.4 p.87–88 · demos/d5_tool_choice.py · 상세: 부록")

# ---------------- 03 · Close --------------------------------------------------------------------
add("정리", "03 · Conclusion", 55,
    '<div class="conclusion-list">'
    + "".join(f'<div><span>{i}</span><p>{t}</p></div>' for i, t in enumerate([
        "책은 에이전트를 <b>모델 + 도구 + 메모리 + 오케스트레이션 + 인프라</b>의 시스템으로 보고, 설계·구축·운영 전 과정을 다룸",
        "에이전트는 마지막 선택지 — 코드·워크플로·RAG로 충분하면 그쪽이 나음",
        "도구는 에이전트가 실제로 일하는 통로. 모델은 <b>선택</b>만, <b>실행·검증·복구</b>는 시스템의 몫",
        "좋은 설명, 표준 연결(MCP), 최소 권한, 최종 답 검사 — 신뢰성은 모델보다 <b>도구 설계</b>에서 나옴",
    ], 1)) + "</div>"
    + take("책을 처음 읽는다면: 1–2장(지도) → 4장(도구) → 9·12장(평가·보안) 순서를 추천"),
    "정리하겠습니다. 이 책은 에이전트를 모델 하나가 아니라 도구, 메모리, 오케스트레이션, 인프라를 갖춘 시스템으로 보고, 만들기부터 운영까지 다룹니다. 에이전트는 마지막 선택지이고, 더 단순한 방법으로 충분하면 그쪽이 낫습니다. "
    "도구는 에이전트가 실제로 일하는 통로인데, 모델은 고를 뿐이고 실행과 검증, 복구는 시스템이 해야 합니다. 직접 확인해 보니 신뢰성은 모델보다 도구 설계에서 나왔습니다. "
    "책을 읽어 보실 분께는 1, 2장으로 지도를 잡고, 4장, 그리고 평가와 보안을 다룬 9장과 12장 순서를 추천드립니다. 감사합니다.",
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
.flow.vertical .step:not(:last-child):after{content:'↓';right:auto;left:22px;top:auto;bottom:-17px;transform:none;font-size:14px}
.data-table.compact-table{font-size:15.5px}.data-table.compact-table th{padding:10px 12px;font-size:14.5px}.data-table.compact-table td{padding:9px 12px;line-height:1.4}
.data-table.center td:not(:first-child),.data-table.center th:not(:first-child){text-align:center}
.data-table.small-rows td{padding:6px 10px;font-size:14px}
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
.ladder .r1{min-height:140px}.ladder .r2{min-height:170px}.ladder .r3{min-height:200px}.ladder .r4{min-height:230px;background:#172840}.ladder .r4 b,.ladder .r4 span{color:white}
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
        body = ('<div class="title-top"><span class="pill dark">BOOK OVERVIEW · TOOL USE DEEP DIVE</span><span>IRV_LAB SEMINAR · 20 MIN</span></div>'
                '<div class="title-main"><div class="title-rule"></div><h1>AI 에이전트 시스템과<br>도구 사용</h1><h2>Building Applications with AI Agents · Michael Albada · O’Reilly</h2>'
                '<p class="title-korean">책 한 권의 지도와, 에이전트가 실제로 일하게 만드는 도구</p>'
                '<p class="authors">설계 · 구축 · 운영 13장 개관 → 4장 도구 사용 심화<br>책의 주장 일부는 로컬 LLM으로 직접 확인</p></div>'
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
              '<meta name="description" content="AI 에이전트 시스템과 도구 사용 · IRV_Lab 2026.10.30 · 박천웅 · 20분 세미나">', head)
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

script = ["# AI 에이전트 시스템과 도구 사용 — 세미나 발표 대본", "", f"박천웅 · IRV_Lab · {DATE}", "",
          f"본편 **{MAIN}장 · 계획 19:00**, 전환 여유 **1:00**, 발표 제한 **20:00**. 부록 {len(slides) - MAIN}장은 본편에 포함하지 않습니다. "
          "실제 발화 시간은 리허설로 확인해야 합니다.", "", "## 시간 운영", "",
          "- 표지에서 `T`를 눌러 20분 타이머를 시작합니다. `T`는 일시정지/재개, `↺`는 초기화입니다.",
          "- 체크포인트: @@E3@@ 도입 종료 / @@E10@@ 책 개관 종료 / @@E18@@ 도구 사용 심화 종료 / @@E19@@ 정리 종료.",
          "- 1분 이상 늦으면 각 장의 “시간 부족 시” 문장을 사용합니다. 17장(모델이 도구를 만드는 경우)은 생략할 수 있습니다.", "",
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
