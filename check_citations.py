"""check_citations.py - STUDENT IMPLEMENTS `check`.   Runs INSIDE the sandbox (standard library only).

research.py uploads this file to the sandbox and the lead agent runs it with the `execute` tool:
    python3 /tmp/work/research/check_citations.py [report.md] [sources.json]
It must exit 0 and print "OK: ..." when the report is consistent, else print each problem and exit 1.
"""
import json
import re
import sys

REPORT = "/tmp/work/report/report.md"
SOURCES = "/tmp/work/research/sources.json"


def _group_numbers(group):
    numbers = []
    for part in re.split(r"\s*,\s*", group):
        span = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", part)
        if span:
            a, b = int(span.group(1)), int(span.group(2))
            numbers.extend(range(a, b + 1) if 0 <= b - a <= 200 else [a, b])
        else:
            numbers.append(int(part))
    return numbers


def check(report_text, sources):
    """Return a list of problem strings (empty list = OK)."""
    problems = []
    if not sources or not isinstance(sources, list):
        return ["no sources in sources.json"]

    seen_urls = set()
    by_n = {}
    for entry in sources:
        if not isinstance(entry, dict):
            problems.append(f"source entry is not an object: {entry!r}")
            continue
        n = entry.get("n")
        if not isinstance(n, int):
            problems.append(f"source entry has non-integer n: {n!r}")
        elif n in by_n:
            problems.append(f"duplicate source number n={n} in sources.json")
        else:
            by_n[n] = entry

        url = entry.get("url")
        if not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
            problems.append(f"source [{n}] has invalid url: {url!r}")
        elif url in seen_urls:
            problems.append(f"duplicate url in sources.json: {url}")
        else:
            seen_urls.add(url)

        if "example.com" in str(url) or "<" in str(url) or ">" in str(url):
            problems.append(f"source [{n}] has placeholder url: {url}")
        source_fam = entry.get("source")
        if source_fam == "arxiv" and not re.match(r"^https://arxiv\.org/abs/([a-z\-]+/\d{7}|\d{4}\.\d{4,5})(v\d+)?$", str(url)):
            problems.append(f"source [{n}] family is 'arxiv' but url is not canonical https://arxiv.org/abs/<id>: {url}")
        if source_fam in {"hf-daily", "hf-search"} and not re.match(r"^https://huggingface\.co/papers/\d{4}\.\d{4,5}$", str(url)):
            problems.append(f"source [{n}] family is '{source_fam}' but url is not canonical https://huggingface.co/papers/<id>: {url}")

    ref_heading_match = list(re.finditer(r"(?m)^##[ \t]+References[ \t]*$", report_text))
    if not ref_heading_match:
        problems.append("missing '## References' section heading")
        return problems

    last_match = ref_heading_match[-1]
    body = report_text[:last_match.start()]
    ref_section = report_text[last_match.end():]

    # Extract cited numbers in the body only (ignoring code blocks and markdown links)
    code_pattern = re.compile(r"(```.*?```|`[^`\n]*`)", re.DOTALL)
    group_pattern = re.compile(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\](?!\()")

    segments = code_pattern.split(body)
    cited = set()
    for i, segment in enumerate(segments):
        if i % 2 == 1:
            continue  # inside code block / span
        for match in group_pattern.finditer(segment):
            for num in _group_numbers(match.group(1)):
                cited.add(num)

    for num in sorted(cited):
        if num not in by_n:
            problems.append(f"[{num}] cited in body but missing from sources.json")

    for n in sorted(by_n.keys()):
        if n not in cited:
            problems.append(f"source [{n}] never cited in report body")

    # Check the ## References section
    ref_lines_raw = [line.strip() for line in ref_section.splitlines() if line.strip()]
    seen_ref_ns = set()
    ref_count = 0
    url_pattern = re.compile(r"https?://\S+")

    for line in ref_lines_raw:
        m = re.match(r"^\[(\d+)\]\s*(.*)$", line)
        if not m:
            continue
        ref_count += 1
        ref_n = int(m.group(1))
        content = m.group(2)

        if ref_n in seen_ref_ns:
            problems.append(f"reference [{ref_n}] appears multiple times in References section")
        seen_ref_ns.add(ref_n)

        if ref_n not in by_n:
            problems.append(f"reference [{ref_n}] in References is not in sources.json")
            continue

        raw_urls = url_pattern.findall(line)
        cleaned_urls = [u.rstrip(".)") for u in raw_urls]
        if len(cleaned_urls) != 1:
            problems.append(f"reference line [{ref_n}] must contain exactly one URL, found {len(cleaned_urls)}")
        else:
            expected_url = by_n[ref_n].get("url")
            if cleaned_urls[0] != expected_url and raw_urls[0] != expected_url:
                problems.append(f"reference [{ref_n}] URL mismatch: {cleaned_urls[0]} != {expected_url}")

    missing_refs = set(by_n.keys()) - seen_ref_ns
    for n in sorted(missing_refs):
        problems.append(f"source [{n}] missing from References section")

    families = {"arxiv", "hf-daily", "hf-search", "web"}
    found_families = {entry.get("source") for entry in sources if isinstance(entry, dict) and entry.get("source")}
    if len(families & found_families) < 3:
        problems.append(
            f"sources.json has only {len(families & found_families)} source families: "
            f"{sorted(families & found_families)} (need >= 3 of {sorted(families)})"
        )

    return problems


def main(argv):
    report_path = argv[1] if len(argv) > 1 else REPORT
    sources_path = argv[2] if len(argv) > 2 else SOURCES
    try:
        with open(report_path, encoding="utf-8") as f:
            report = f.read()
        with open(sources_path, encoding="utf-8") as f:
            sources = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"cannot read inputs: {exc}")
        return 1
    problems = check(report, sources)
    if problems:
        print("\n".join(problems))
        return 1
    print(f"OK: {len(sources)} sources, all citations resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
