---
name: obsidian-knowledge-base
description: |
  Manages the project's local Obsidian knowledge base vault under `.notes/`.
  Provides structured rules, guidelines, and templates for creating, editing,
  and inter-linking Architecture Decision Records (ADRs), bug logs, design patterns,
  and the project overview.
---

# SKILL: Obsidian Knowledge Base Workflow Manager

This skill details how to manage, write, update, and link notes inside the project's local Obsidian vault located at `.notes/` at the root of the workspace. Using this workflow helps preserve critical context (decisions, trade-offs, bugs, patterns) across different AI sessions.

## 1. Vault Directory Structure

The vault must maintain the following structure:
*   `.notes/decisions/` - Architecture Decision Records (ADRs) tracking key system design choices.
*   `.notes/patterns/` - Explanations of code architecture, API design, and custom hook/component patterns.
*   `.notes/bugs/` - Records of encountered bugs, symptoms, root causes, and applied fixes.
*   `.notes/context/` - Project overview and roadmap documents.

---

## 2. Note Creation & Editing Rules

### 2.1 General Writing Rules
*   **Write Clean Markdown**: Use standard Markdown headings, lists, and code blocks.
*   **Keep it Lightweight**: Write notes as concise memos. Do not overcomplicate the formatting.
*   **Obsidian Callouts**: Use callouts (`> [!NOTE]`, `> [!WARNING]`, etc.) to emphasize crucial implementation details.
*   **Wikilinks**: Link notes together using Obsidian's wikilink syntax: `[[Note Name]]` or `[[Note Name|Display Text]]`.
*   **YAML Frontmatter**: Every note must start with a YAML frontmatter block containing metadata properties like:
    ```yaml
    ---
    type: adr | bug | pattern | context
    created: YYYY-MM-DD
    status: proposed | accepted | superseded | resolved
    tags: [tech-stack-tag, feature-tag]
    ---
    ```

---

## 3. Note Templates

### 3.1 Architecture Decision Records (ADRs)
*   **Location**: `.notes/decisions/ADR-XXX-[short-name].md`
*   **Template**:
    ```markdown
    ---
    type: adr
    id: ADR-XXX
    created: YYYY-MM-DD
    status: proposed | accepted | superseded
    tags: [architecture, design-decision]
    ---

    # ADR-XXX: [Title of Decision]

    ## Context
    [What is the problem or situation we are addressing? What are the requirements and constraints?]

    ## Decision
    [What is the chosen approach? Be direct and clear.]

    ## Reasoning & Trade-offs
    *   **Pro**: [Benefit 1]
    *   **Pro**: [Benefit 2]
    *   **Con**: [Trade-off/Limitation 1]

    ## Rejected Alternatives
    *   **[Alternative Name]**: [Why was it rejected? e.g., too complex, wrong abstraction]

    ## Code References
    *   [Link or symbol referring to files affected, e.g., `src/components/MyComponent.tsx`]
    ```

### 3.2 Bug Logs
*   **Location**: `.notes/bugs/BUG-[short-name].md`
*   **Template**:
    ```markdown
    ---
    type: bug
    created: YYYY-MM-DD
    status: resolved | open
    tags: [debugging, issue-type]
    ---

    # Bug: [Short Description of Issue]

    ## Symptom
    [What did the user observe? Paste stack traces, error messages, or logs here.]

    ## Root Cause
    [Why did it happen? Detail the code flow, race condition, or API mismatch.]

    ## Applied Fix
    [How was it fixed? Show the code changes or diff, and explain the logic.]

    ## How to Avoid in the Future
    [What rules or tests should be in place to prevent regression?]

    ## Affected Files
    *   [File link, e.g., `src/hooks/useFetch.ts`]
    ```

### 3.3 Design/Code Patterns
*   **Location**: `.notes/patterns/[pattern-name].md`
*   **Template**:
    ```markdown
    ---
    type: pattern
    created: YYYY-MM-DD
    tags: [pattern, code-design]
    ---

    # Pattern: [Name of Design Pattern or Module Architecture]

    ## Purpose
    [What problem does this pattern solve in our codebase?]

    ## Code Blueprint
    ```typescript
    // Example implementation code of the pattern
    ```

    ## Key Rules
    1.  [Rule 1, e.g., All state must be localized to this hook]
    2.  [Rule 2]

    ## Context for Next Session
    [Important things to note when extending or refactoring this pattern.]
    ```

---

## 4. Agent Session Lifecycle Integration

### 4.1 Start of Session
At the start of any new session or feature development:
1.  Read `.notes/context/project-overview.md` to load the current state of the application.
2.  Use `grep_search` or `list_dir` on `.notes/decisions/` and `.notes/bugs/` to check for decisions or bug patterns relevant to the files you are about to touch.

### 4.2 End of Session (Updates)
Before finishing a task or concluding a turn:
1.  **Create/Update ADRs**: If a major design choice was made, document it in `.notes/decisions/`.
2.  **Log Bugs**: If an elusive bug was solved, document it in `.notes/bugs/`.
3.  **Update Overview**: Modify `.notes/context/project-overview.md` under `Recent Changes` and `Open Issues` to reflect the session's work.
