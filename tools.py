"""tools.py - STUDENT IMPLEMENTS.  Source tools for the research agents.   Guide: GUIDE.md, part 1.

Rules for every tool:
  * runs on the HOST (not in the sandbox): API keys must never enter the sandbox;
  * returns a STRING (JSON text of compact records) and NEVER raises:
        "NO RESULTS"  when the source answers with nothing,
        "ERROR: ..."  when the source keeps failing after the retries (the agent then tries another source);
  * the docstring is the tool description the LLM reads: keep it precise (what it does, what it returns, when to use it).
Try your tools without any agent:   python tools.py
"""
import json
import os
import random
import re
import time
import xml.etree.ElementTree as ET

import httpx
from langchain_core.tools import tool

# ---- constants (given) ----
ARXIV_URL = "https://export.arxiv.org/api/query"  # https only: http answers 301
HF_DAILY_URL = "https://huggingface.co/api/daily_papers"
HF_SEARCH_URL = "https://huggingface.co/api/papers/search"
EXA_URL = "https://mcp.exa.ai/mcp"

_LAST_ARXIV_CALL = 0.0


class RetryableError(Exception):
    """Given. Raise it inside a call to ask with_retry to wait and try again (retry_after in seconds, optional)."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


# ---- TODO 1: retry helper ----
def with_retry(fn, *, attempts=5, base=1.0, cap=30.0):
    """Call fn(); when it raises RetryableError, wait and call it again."""
    for attempt in range(attempts):
        try:
            return fn()
        except (RetryableError, httpx.HTTPStatusError, httpx.TransportError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {429, 500, 502, 503, 504}:
                raise
            if attempt == attempts - 1:
                raise
            retry_after = None
            if isinstance(exc, RetryableError) and exc.retry_after is not None:
                try:
                    retry_after = float(exc.retry_after)
                except (ValueError, TypeError):
                    pass
            elif isinstance(exc, httpx.HTTPStatusError):
                hdr = exc.response.headers.get("retry-after")
                if hdr:
                    try:
                        retry_after = float(hdr)
                    except (ValueError, TypeError):
                        pass

            if retry_after is not None:
                delay = retry_after
            else:
                delay = base * (2 ** attempt) + random.uniform(0.0, 1.0)
            delay = min(delay, cap)
            time.sleep(delay)


# ---- TODO 2: arXiv ----
@tool
def arxiv_search(query: str, max_results: int = 10) -> str:
    """Search arXiv papers by keywords, newest first. Returns a JSON list of {id, url, published, title, summary}. Source family: 'arxiv'."""
    global _LAST_ARXIV_CALL
    try:
        raw_terms = re.findall(r"[\w-]+", query)
        stop_words = {"and", "or", "not", "the", "a", "an", "of", "in", "for", "on", "with", "to", "about"}
        terms = [t for t in raw_terms if t.lower() not in stop_words]
        if not terms:
            terms = raw_terms
        if not terms:
            return "NO RESULTS"

        clamped = max(1, min(30, int(max_results)))
        search_query = " AND ".join(f"all:{t}" for t in terms[:4])

        def _do_get():
            global _LAST_ARXIV_CALL
            now = time.time()
            elapsed = now - _LAST_ARXIV_CALL
            if elapsed < 3.5:
                time.sleep(3.5 - elapsed)
            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.get(
                        ARXIV_URL,
                        params={
                            "search_query": search_query,
                            "sortBy": "submittedDate",
                            "sortOrder": "descending",
                            "max_results": clamped,
                        },
                        headers={"User-Agent": "curl/8.4.0", "Accept": "*/*"},
                    )
                    resp.raise_for_status()
                    return resp.text
            finally:
                _LAST_ARXIV_CALL = time.time()

        xml_text = with_retry(_do_get, attempts=6, base=5.0, cap=60.0)
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        if not entries:
            return "NO RESULTS"

        records = []
        for entry in entries:
            id_elem = entry.find("atom:id", ns)
            if id_elem is None or not id_elem.text:
                continue
            raw_id = id_elem.text.strip().split("/abs/")[-1]
            paper_id = re.sub(r"v\d+$", "", raw_id)
            url = f"https://arxiv.org/abs/{paper_id}"

            pub_elem = entry.find("atom:published", ns)
            published = pub_elem.text.strip()[:10] if pub_elem is not None and pub_elem.text else ""

            title_elem = entry.find("atom:title", ns)
            title = " ".join((title_elem.text or "").split()) if title_elem is not None else ""

            summary_elem = entry.find("atom:summary", ns)
            summary = " ".join((summary_elem.text or "").split())[:600] if summary_elem is not None else ""

            records.append({
                "id": paper_id,
                "url": url,
                "published": published,
                "title": title,
                "summary": summary,
            })

        return json.dumps(records, ensure_ascii=False) if records else "NO RESULTS"
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


# ---- TODO 3: Hugging Face ----
@tool
def hf_daily_papers(limit: int = 30, date: str = "", keyword: str = "") -> str:
    """Hugging Face Daily Papers = trending AI research papers on Hugging Face. Returns a JSON list of
    {id, url, published, title, summary, upvotes, github, stars} sorted by upvotes. `date` is YYYY-MM-DD (empty = latest).
    Use `keyword` to filter for papers matching your topic. Source family: 'hf-daily'."""
    try:
        clamped = max(1, min(100, int(limit)))
        params = {"limit": clamped}
        if date and str(date).strip():
            params["date"] = str(date).strip()

        def _do_get():
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(HF_DAILY_URL, params=params)
                resp.raise_for_status()
                return resp.json()

        items = with_retry(_do_get, attempts=5, base=1.0, cap=30.0)
        if not isinstance(items, list):
            return "NO RESULTS"

        records = []
        for item in items:
            paper = item.get("paper") if isinstance(item, dict) else None
            if not isinstance(paper, dict) or not paper.get("id"):
                continue
            paper_id = str(paper["id"])
            url = f"https://huggingface.co/papers/{paper_id}"
            title = " ".join(str(paper.get("title") or item.get("title") or "").split())
            summary = " ".join(str(paper.get("summary") or item.get("summary") or "").split())[:600]
            published = str(paper.get("publishedAt") or item.get("publishedAt") or "")[:10]
            upvotes = int(paper.get("upvotes") or item.get("upvotes") or 0)
            github = str(paper.get("githubRepo") or item.get("githubRepo") or "")
            stars = int(paper.get("githubStars") or item.get("githubStars") or 0)

            records.append({
                "id": paper_id,
                "url": url,
                "published": published,
                "title": title,
                "summary": summary,
                "upvotes": upvotes,
                "github": github,
                "stars": stars,
            })

        if keyword and str(keyword).strip():
            kw = str(keyword).strip().lower()
            words = [w for w in re.findall(r"[\w-]+", kw) if len(w) >= 3]
            filtered = [r for r in records if kw in (r["title"] + " " + r["summary"]).lower()]
            if not filtered and words:
                filtered = [r for r in records if any(w in (r["title"] + " " + r["summary"]).lower() for w in words)]
            if filtered:
                records = filtered

        records.sort(key=lambda r: r.get("upvotes", 0), reverse=True)
        return json.dumps(records, ensure_ascii=False) if records else "NO RESULTS"
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


@tool
def hf_search_papers(query: str, limit: int = 10) -> str:
    """Search Hugging Face papers by topic keywords. Returns a JSON list of
    {id, url, published, title, summary, upvotes, github, stars}. Source family: 'hf-search'."""
    try:
        q = str(query).strip()
        if not q:
            return "NO RESULTS"
        clamped = max(1, min(50, int(limit)))
        params = {"q": q, "limit": clamped}

        def _do_get():
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(HF_SEARCH_URL, params=params)
                resp.raise_for_status()
                return resp.json()

        items = with_retry(_do_get, attempts=5, base=1.0, cap=30.0)
        if not isinstance(items, list):
            return "NO RESULTS"

        records = []
        for item in items:
            paper = item.get("paper") if isinstance(item, dict) else None
            if not isinstance(paper, dict) or not paper.get("id"):
                continue
            paper_id = str(paper["id"])
            url = f"https://huggingface.co/papers/{paper_id}"
            title = " ".join(str(paper.get("title") or item.get("title") or "").split())
            raw_summary = paper.get("ai_summary") or paper.get("summary") or item.get("ai_summary") or item.get("summary") or ""
            summary = " ".join(str(raw_summary).split())[:600]
            published = str(paper.get("publishedAt") or item.get("publishedAt") or "")[:10]
            upvotes = int(paper.get("upvotes") or item.get("upvotes") or 0)
            github = str(paper.get("githubRepo") or item.get("githubRepo") or "")
            stars = int(paper.get("githubStars") or item.get("githubStars") or 0)

            records.append({
                "id": paper_id,
                "url": url,
                "published": published,
                "title": title,
                "summary": summary,
                "upvotes": upvotes,
                "github": github,
                "stars": stars,
            })

        return json.dumps(records, ensure_ascii=False) if records else "NO RESULTS"
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


# ---- TODO 4: web search / fetch through the Exa MCP endpoint ----
def _call_exa_mcp(tool_name: str, arguments: dict) -> str:
    api_key = (os.getenv("EXA_API_KEY") or "").strip()
    endpoint = f"{EXA_URL}?exaApiKey={api_key}" if api_key else EXA_URL
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }

    def _post():
        with httpx.Client(timeout=35.0) as client:
            resp = client.post(endpoint, headers=headers, json=payload)
            resp.raise_for_status()

            # Parse SSE or json
            data = None
            for line in resp.text.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    try:
                        data = json.loads(line[5:].strip())
                        break
                    except ValueError:
                        pass
            if data is None:
                data = resp.json()

            if "error" in data:
                err = data["error"]
                msg = err.get("message", "") if isinstance(err, dict) else str(err)
                if "rate limit" in msg.lower() or (isinstance(err, dict) and err.get("code") == -32000):
                    raise RetryableError(f"Exa rate limit: {msg}", retry_after=20.0)
                raise RuntimeError(f"Exa error: {msg}")

            result = data.get("result", {})
            meta = result.get("_meta", {})
            if meta.get("rateLimited") or "rate limit" in str(meta).lower():
                raise RetryableError("Exa rate limited in _meta", retry_after=20.0)

            content = result.get("content", [])
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))

            full_text = "\n".join(text_parts).strip()
            if "hit exa's free mcp rate limit" in full_text.lower():
                raise RetryableError("Exa free tier rate limit", retry_after=20.0)

            return full_text

    return with_retry(_post, attempts=2, base=1.0, cap=5.0)


def _redact_key(msg: str) -> str:
    api_key = (os.getenv("EXA_API_KEY") or "").strip()
    if api_key and api_key in msg:
        msg = msg.replace(api_key, "[REDACTED]")
    return msg


@tool
def web_search(query: str, objective: str = "", num_results: int = 5) -> str:
    """Search the web (Exa). Describe the ideal page in natural language. Returns clean text of the top results with URLs."""
    try:
        q = str(query).strip()
        if not q:
            return "NO RESULTS"
        obj = str(objective).strip() or f"search for {q}"
        num = max(1, min(10, int(num_results)))

        text = _call_exa_mcp("web_search_exa", {"query": q, "objective": obj, "numResults": num})
        if not text:
            return "NO RESULTS"
        return _redact_key(text)
    except Exception as exc:
        msg = _redact_key(f"ERROR: {type(exc).__name__}: {exc}")
        return msg


@tool
def web_fetch(url: str) -> str:
    """Read the full content of one web page (e.g. an arXiv abstract page) as markdown. Long pages are truncated."""
    try:
        u = str(url).strip()
        if not u:
            return "NO RESULTS"
        text = _call_exa_mcp("web_fetch_exa", {"urls": [u]})
        if not text:
            return "NO RESULTS"
        return _redact_key(text[:12000])
    except Exception as exc:
        msg = _redact_key(f"ERROR: {type(exc).__name__}: {exc}")
        return msg


# ---- TODO 5: registry (the researcher subagent gets exactly these) ----
SOURCE_TOOLS = [arxiv_search, hf_daily_papers, hf_search_papers, web_search, web_fetch]


if __name__ == "__main__":
    for name, fn, args in [
        ("arxiv_search", arxiv_search, {"query": "world model", "max_results": 3}),
        ("hf_daily_papers", hf_daily_papers, {"limit": 20}),
        ("hf_search_papers", hf_search_papers, {"query": "world model", "limit": 3}),
        ("web_search", web_search, {"query": "survey paper on world models", "num_results": 2}),
        ("web_fetch", web_fetch, {"url": "https://arxiv.org/abs/1803.10122"}),
    ]:
        try:
            print(f"== {name}\n{fn.invoke(args)[:400]}\n")
        except NotImplementedError as exc:
            print(f"== {name}: not implemented yet ({exc})\n")
