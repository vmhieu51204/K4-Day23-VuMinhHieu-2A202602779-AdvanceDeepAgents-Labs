"""research.py - STUDENT IMPLEMENTS.  The main script.   Guide: GUIDE.md, part 3.

Usage:  python research.py "survey about world model"
Result: reports/<slug>.md   reports/<slug>.sources.json   reports/<slug>.meta.json
"""
import json  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import sys
import time  # noqa: F401
from collections import Counter  # noqa: F401
from pathlib import Path

from agents import FINALIZER_PATH, REPORT_PATH, SOURCES_PATH, VALIDATOR_PATH, WORKDIR, build_lead_agent  # noqa: F401
from model import make_model  # noqa: F401
from sandbox import download, open_sandbox, upload  # noqa: F401

ROOT = Path(__file__).parent
REPORTS = ROOT / "reports"
VALIDATOR_SOURCE = ROOT / "check_citations.py"
FINALIZER_SOURCE = ROOT / "finalize_citations.py"   # provided: uploaded next to your validator


def slugify(topic):
    """Turn a topic into a safe file name: lower case, runs of non-word characters become one "-", max 60 chars,
    never empty (fall back to "topic"). The topic is user input: "../../x" must not escape reports/."""
    s = str(topic or "").strip().lower()
    words = re.findall(r"[a-z0-9]+", s)
    if not words:
        return "topic"
    slug = "-".join(words)
    if len(slug) > 60:
        slug = slug[:60].rstrip("-")
    return slug or "topic"


def build_prompt(topic):
    """The user message sent to the lead agent."""
    return f"""Conduct a deep academic research survey on the topic: "{topic}".

Follow the mandated workflow:
1. Call write_todos to plan your research, dividing the topic into at least 3 distinct sub-questions.
2. Delegate each sub-question to the researcher subagent using the task tool (you must make at least 3 subagent task calls). In each delegation message, include the topic, sub-question, destination notes file path (e.g. /tmp/work/research/notes/01-subtopic.md), note format, and instruct the subagent to retrieve at least 3-4 distinct papers using arxiv_search ('arxiv'), hf_search_papers ('hf-search'), and hf_daily_papers with keyword ('hf-daily').
3. Review researcher notes, verify them, and merge all sources into /tmp/work/research/sources.json (aim for at least 8-12 real sources, numbered sequentially from 1, unique URLs).
   MANDATORY: Ensure the sources represent AT LEAST 3 distinct source families: specifically 'arxiv', 'hf-search', and 'hf-daily'.
4. Write the survey report body into /tmp/work/report/report.md following REPORT_TEMPLATE.md (TL;DR with [n] citations, Background with [n] citations, thematic comparison sections synthesizing across papers with inline [n] citations, Trends and open problems). Do NOT write ## References.
   CRITICAL: In your body text, synthesize across at least 8-12 sources and cite sources from ALL THREE families ('arxiv', 'hf-search', and 'hf-daily') using inline [n] citations. Uncited sources are deleted by finalize_citations.py, so ensure every collected source is cited!
5. Run /tmp/work/research/finalize_citations.py via the execute tool to generate ## References and synchronize sources.json.
6. Run /tmp/work/research/check_citations.py via the execute tool until it reports OK.
7. Use citation-checker to spot-check key claims.
"""


def summarize(messages, elapsed, model_name):
    """Return {"model", "elapsed_s", "subagent_calls", "tool_calls": {name: count}, "tokens": {"input", "output"}}."""
    tool_counts = Counter()
    input_tokens = 0
    output_tokens = 0

    for msg in messages:
        tool_calls = []
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_calls = msg.tool_calls
        elif isinstance(msg, dict) and msg.get("tool_calls"):
            tool_calls = msg["tool_calls"]

        for call in tool_calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", "")
            if name:
                tool_counts[name] += 1

        usage = None
        if hasattr(msg, "usage_metadata") and msg.usage_metadata:
            usage = msg.usage_metadata
        elif isinstance(msg, dict) and msg.get("usage_metadata"):
            usage = msg["usage_metadata"]
        elif hasattr(msg, "response_metadata") and isinstance(msg.response_metadata, dict):
            usage = msg.response_metadata.get("token_usage")

        if usage and isinstance(usage, dict):
            input_tokens += int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
            output_tokens += int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)

    subagent_calls = tool_counts.get("task", 0)
    return {
        "model": model_name,
        "elapsed_s": round(float(elapsed), 1),
        "subagent_calls": subagent_calls,
        "tool_calls": dict(tool_counts),
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
        },
    }


def parse_sources_bytes(sources_bytes):
    """Parse sources_bytes into a Python list, recovering from trailing text or markdown fences if present."""
    text = sources_bytes.decode("utf-8", errors="replace").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except Exception:
        pass

    decoder = json.JSONDecoder()
    pos = 0
    all_items = []
    while pos < len(text):
        match = re.search(r"[\[\{]", text[pos:])
        if not match:
            break
        pos += match.start()
        try:
            obj, end = decoder.raw_decode(text[pos:])
            pos += end
            if isinstance(obj, list):
                all_items.extend(obj)
            elif isinstance(obj, dict):
                all_items.append(obj)
        except ValueError:
            pos += 1

    if all_items:
        return all_items
    raise RuntimeError("sources.json does not contain a valid JSON array")


def save_outputs(backend, topic, messages, elapsed, model_name, reports_dir=REPORTS):
    """Download the report from the sandbox and write the three files into reports_dir. Return the report path."""
    files = download(backend, [REPORT_PATH, SOURCES_PATH])
    report_bytes = files.get(REPORT_PATH)
    sources_bytes = files.get(SOURCES_PATH)

    if not report_bytes or not report_bytes.strip():
        raise RuntimeError("Report file is missing or empty in sandbox")
    if not sources_bytes or not sources_bytes.strip():
        raise RuntimeError("sources.json is missing or empty in sandbox")

    try:
        sources_data = parse_sources_bytes(sources_bytes)
    except Exception as exc:
        raise RuntimeError(f"sources.json is invalid JSON: {exc}") from exc

    if not isinstance(sources_data, list) or not sources_data:
        raise RuntimeError("sources.json must be a non-empty JSON array")

    slug = slugify(topic)
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    summary = summarize(messages, elapsed, model_name)
    source_families = sorted(list({s.get("source") for s in sources_data if isinstance(s, dict) and s.get("source")}))

    meta = {
        "topic": topic,
        **summary,
        "n_sources": len(sources_data),
        "source_families": source_families,
    }

    sources_file = reports_dir / f"{slug}.sources.json"
    meta_file = reports_dir / f"{slug}.meta.json"
    report_file = reports_dir / f"{slug}.md"

    sources_file.write_text(json.dumps(sources_data, indent=2, ensure_ascii=False), encoding="utf-8")
    meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    report_file.write_bytes(report_bytes)

    return report_file


def main(topic):
    """Return the process exit code (0 ok, 1 failed run, 2 no topic)."""
    if not topic or not str(topic).strip():
        print("Usage: python research.py <topic>", file=sys.stderr)
        return 2

    topic = str(topic).strip()
    try:
        model = make_model()
        if hasattr(model, "max_retries"):
            model.max_retries = 6
    except Exception as exc:
        print(f"FAILED to initialize model: {exc}", file=sys.stderr)
        return 1

    model_name = getattr(model, "model_name", None) or os.getenv("LAB_MODEL", "model")
    start = time.monotonic()

    try:
        with open_sandbox() as backend:
            backend.execute(f"mkdir -p {WORKDIR}/research/notes {WORKDIR}/report")
            upload(backend, {VALIDATOR_PATH: VALIDATOR_SOURCE.read_bytes(), FINALIZER_PATH: FINALIZER_SOURCE.read_bytes()})
            agent = build_lead_agent(backend, model)
            result = agent.invoke({"messages": [{"role": "user", "content": build_prompt(topic)}]},
                                  config={"recursion_limit": 1000})
            messages = result.get("messages", [])
            elapsed = time.monotonic() - start
            out_path = save_outputs(backend, topic, messages, elapsed, str(model_name))
            print(f"Report saved: {out_path}")
            return 0
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
