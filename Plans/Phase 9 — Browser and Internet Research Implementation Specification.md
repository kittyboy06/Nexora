# NEXORA — Phase 9: Browser and Internet Research Implementation Specification

## 1. Executive Summary & Purpose

Phase 9 introduces a centralized, governed **Browser and Internet Research Platform** into NEXORA. It equips autonomous agents and multi-agent fleets with structured web research tools (`web_search`, `web_fetch`, `web_extract_citations`, `web_download_quarantine`) while enforcing rigorous Anti-SSRF controls, indirect prompt-injection defenses, resource caps, and isolated quarantine storage for external downloads.

---

## 2. Core Constraints & Guarantees

1. **Anti-SSRF Protection:** Pre-flight DNS resolution blocks private, loopback, link-local, and cloud metadata IPs (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `::1`). Redirect hops (capped at 5) are re-validated before opening connection sockets.
2. **Anti-Prompt-Injection Boundary:** All extracted web content returned to the LLM is wrapped in bounded `<untrusted_web_evidence>` quotation containers with tag escaping, preventing untrusted webpage text from hijacking agent instructions or altering system policies.
3. **Dual-Engine Execution:** Fast asynchronous HTTP extraction (`httpx` + HTML cleaner) handles 80%+ of static articles/docs with sub-200ms latency. Headless Playwright (Chromium) is lazily launched only when dynamic JavaScript execution or page screenshots are explicitly requested.
4. **Zero-Ambient Storage & Ephemeral Browser Contexts:** Playwright browser contexts are created per-task and destroyed immediately upon completion. No ambient user profiles, cookies, or credentials are leaked across tasks.
5. **Isolated Quarantine Downloads:** External file downloads are quarantined strictly into `data/quarantine/<task_id>/` with MIME and SHA-256 checks. Downloading a file confers zero execution permissions.
6. **Governance Tiers:** Search, page navigation, and text extraction are governed as `CONTROLLED` actions. Remote file downloads and external session attachments are `SENSITIVE` (requiring explicit operator approval).

---

## 3. Decision Log

| ID | Decision | Alternatives Considered | Rationale |
| :--- | :--- | :--- | :--- |
| **D1** | Dual-engine architecture (HTTP fast-path + Playwright headless) | Pure Playwright; Pure HTTP scraper; Subprocess MCP worker | Minimizes memory/latency for static docs while providing full DOM fidelity for dynamic JS when needed. |
| **D2** | Pluggable search factory with DuckDuckGo as default | Requiring commercial API keys; Browser DOM scraping | Provides immediate out-of-the-box research capability with zero setup, with seamless upgrade path via encrypted vault. |
| **D3** | Pre-flight DNS resolution & IP-level validation on every hop | URL string regex checking; Host header validation | Prevents DNS rebinding, internal IP bypasses, octal/hex IP obfuscation, and cloud metadata theft. |
| **D4** | Strict 5 MB / 100k char bounds with 20s timeout | Unbounded streaming; Higher 50MB limits | Prevents Denial-of-Service, memory bloat, and context-window exhaustion from massive files or tarpits. |
| **D5** | Dynamic engine selection (`render_js: bool = False` default) | Always run browser; Force user to choose separate tools | 80%+ of research queries are documentation or articles that do not require heavy Chromium rendering. Defaulting to fast HTTP saves CPU, memory, and reduces latency. |
| **D6** | Ephemeral task-scoped Playwright context lifecycle | Reusing a global browser profile across all tasks | Eliminates cross-task cookie/session leakage, prevents zombie processes, and enforces strict security isolation. |
| **D7** | Bounded `<untrusted_web_evidence>` quotation wrapper | Feeding raw markdown directly into agent prompt | Eliminates indirect prompt injection risks by establishing a syntactic and semantic sandbox around untrusted external web text. |
| **D8** | Dedicated `data/quarantine/<task_id>/` download boundary | Saving directly to user's `Downloads` or project root | Isolates downloaded payloads, enforces malware/traversal checks, and prevents accidental code execution. |
| **D9** | `CONTROLLED` for search/fetch; `SENSITIVE` for downloads | Making all web tools `SENSITIVE`; Making all web tools `SAFE` | Balances research autonomy (agents can search and read docs without constant prompts) with strict operator gating for disk side-effects. |
| **D10** | Integrated Evidence Panel in Task Detail view | Creating a separate top-level Desktop tab | Research evidence is directly tied to specific task plans and steps; surfacing it contextually inside the Task Detail view provides clearer provenance for operators. |

---

## 4. Architecture & Module Design

```
backend/app/research/
├── __init__.py
├── models.py           # Domain models: ResearchEvidence, SearchResult, FetchResult, QuarantineItem
├── policy.py           # Anti-SSRF IP validator, domain allowlist/denylist, redirect & size limits
├── sanitizer.py        # Tag escaper & <untrusted_web_evidence> quotation wrapper
├── search/             # Pluggable search providers
│   ├── __init__.py
│   ├── base.py         # Abstract SearchProvider interface
│   ├── duckduckgo.py   # Zero-config DuckDuckGo provider
│   └── factory.py      # Factory resolving Brave/Tavily via McpVaultService if configured
├── engines/            # Dual fetch engines
│   ├── __init__.py
│   ├── base.py         # Abstract FetchEngine interface
│   ├── http.py         # Fast async HTTP engine (httpx + HTML parser)
│   └── browser.py      # Playwright headless browser engine
├── evidence.py         # Evidence artifact recorder (data/research/<task_id>/)
├── quarantine.py       # Isolated download manager with MIME & SHA-256 checks (data/quarantine/<task_id>/)
├── service.py          # BrowserResearchService orchestrator & context lifecycle manager
├── tools.py            # Typed BaseTools: web_search, web_fetch, web_extract_citations, web_download_quarantine
└── router.py           # FastAPI router for research evidence inspection & active sessions
```

```mermaid
graph TD
    Agent[Agent / Fleet Worker] -->|Tool Invocation| Tools[Research Tools in ToolRegistry]
    Tools --> PM[PermissionManager: CONTROLLED / SENSITIVE]
    PM --> Svc[BrowserResearchService]
    Svc --> Policy[DomainPolicy & Anti-SSRF Gate]
    Policy -->|Allowed| EngineRouter{Require JS?}
    EngineRouter -->|No| HTTP[HttpFetchEngine (httpx)]
    EngineRouter -->|Yes| PW[PlaywrightBrowserEngine (Chromium)]
    HTTP --> Extractor[Content & Citation Extractor]
    PW --> Extractor
    Extractor --> Evidence[ResearchEvidenceStore (data/research/)]
    Extractor --> AntiInject[Anti-Injection Quotation Wrapper]
    AntiInject --> Agent
```

---

## 5. Domain Models (`backend/app/research/models.py`)

```python
class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    rank: int

class CitationItem(BaseModel):
    quote: str
    source_url: str
    char_offset: int = 0

class FetchResult(BaseModel):
    url: str
    title: str
    content: str
    citations: list[CitationItem] = []
    content_hash: str
    http_status: int = 200
    engine: str = "http"
    screenshot_path: Optional[str] = None

class ResearchEvidence(BaseModel):
    evidence_id: str
    task_id: str
    url: str
    title: str
    timestamp: str
    content_snippet: str
    content_hash: str
    citations: list[CitationItem] = []
    engine: str
    screenshot_path: Optional[str] = None

class QuarantineItem(BaseModel):
    task_id: str
    filename: str
    original_url: str
    file_size: int
    content_type: str
    sha256_hash: str
    quarantine_path: str
    downloaded_at: str
```

---

## 6. Implementation Milestones

* **Milestone 1:** Domain Models & Anti-SSRF Policy Gate (`models.py`, `policy.py`, `sanitizer.py`, tests in `test_research_policy.py`).
* **Milestone 2:** Search Providers & Fast HTTP Fetch Engine (`search/`, `engines/http.py`, tests in `test_research_http.py`).
* **Milestone 3:** Playwright Headless Browser Engine & Lifecycle (`engines/browser.py`, tests in `test_research_browser.py`).
* **Milestone 4:** Evidence Recorder & Quarantine Download Manager (`evidence.py`, `quarantine.py`, tests in `test_research_quarantine.py`).
* **Milestone 5:** Research Service & ToolRegistry Integration (`service.py`, `tools.py`, tests in `test_research_tools.py`).
* **Milestone 6:** FastAPI Endpoints & Application Wiring (`router.py`, `main.py`, tests in `test_research_api.py`).
* **Milestone 7:** WinUI 3 Desktop Control Plane (Research & Evidence panel in `MainWindow.xaml`, C# DTOs, `TaskDetailViewModel`, tests in `Nexora.Desktop.Tests`).
* **Milestone 8:** Verification & End-to-End Suite (`test_research_e2e.py`, full suite regression pass).
