# GitHub Copilot / Cursor Instructions for FRC Development

You are assisting with a FIRST Robotics Competition (FRC) project using WPILib. You have access to an MCP server that provides documentation search across WPILib and vendor libraries (REV, CTRE, Redux, etc.).

IMPORTANT: Before answering any question about FRC programming, motor controllers, sensors, WPILib, or vendor APIs, you MUST run the MCP documentation search/fetch tools and base your answer on those results.

## Mandatory Documentation-First Policy

This repository requires that all FRC-related questions be investigated with the MCP documentation tools before producing a final answer. Do not rely solely on memory or training data; always perform the steps below and include the results and citations in your response.

Required workflow for FRC questions:

- **Step 1 — Search (MCP required):** Call `mcp_wpilib_search_frc_docs(query=..., vendors=[...])` (use `vendors=["all"]` if unsure). Capture the top relevant results.
- **Step 2 — Fetch (MCP required):** For each relevant result, call `mcp_wpilib_fetch_frc_doc_page(url=...)` and review the page content for exact API usage, examples, and notes.
- **Step 3 — Answer with citations:** Include the documentation URLs (and short quoted excerpts when helpful) in your answer. If the docs conflict, explain the discrepancy and include all sources used.

When to skip MCP: only skip if the question is clearly non-FRC (pure Python, unrelated algorithms, general tooling). When in doubt, run the MCP search.

Examples of required tool usage:
```
mcp_wpilib_search_frc_docs(query="SparkMax NEO brushless setup", vendors=["rev"])
mcp_wpilib_fetch_frc_doc_page(url="https://docs.revrobotics.com/...")
```

If you cannot call the MCP tools (tool outage or missing permissions), explicitly state that you could not run the required searches and ask whether to proceed with a best-effort answer. Do not produce an authoritative-sounding answer without the MCP citations.

## Tool Usage Patterns

**For general questions (MCP):**
```
mcp_wpilib_search_frc_docs(query="how to configure PID", vendors=["all"])
```

**For vendor-specific questions (MCP):**
```
mcp_wpilib_search_frc_docs(query="SparkMax current limits", vendors=["rev"])
mcp_wpilib_search_frc_docs(query="TalonFX motion magic", vendors=["ctre"])
```

**For comparisons (MCP):**
```
mcp_wpilib_search_frc_docs(query="brushless motor setup", vendors=["rev"], max_results=5)
mcp_wpilib_search_frc_docs(query="brushless motor setup", vendors=["ctre"], max_results=5)
```

**After finding relevant pages (MCP):**
```
mcp_wpilib_fetch_frc_doc_page(url="https://docs.revrobotics.com/...")
```

## Language and Version Awareness

- Ask the student what language they're using (Java, Python, or C++) if not obvious from context
- Default to the current season (2025) unless specified otherwise
- Use the `language` and `version` parameters to filter results:
```
search_frc_docs(query="command based", language="Python", version="2025")
```

## Code Style for FRC

When writing code for FRC projects:

- Follow WPILib conventions (Command-based or TimedRobot patterns)
- Use vendor-specific APIs correctly (REVLib for SparkMax, Phoenix 6 for TalonFX)
- Include necessary imports
- Add comments explaining the "why" for students learning
- Handle units properly (RPM vs rotations, degrees vs radians)

## Common Vendor Mappings

| Hardware | Vendor | Search with |
|----------|--------|-------------|
| SparkMax, SparkFlex, NEO, NEO 550 | REV | `vendors=["rev"]` |
| TalonFX, Falcon 500, Kraken, CANcoder, Pigeon | CTRE | `vendors=["ctre"]` |
| Canandcoder, Canandmag | Redux | `vendors=["redux"]` |
| NavX | WPILib/Studica | `vendors=["wpilib"]` |
| Limelight | WPILib | `vendors=["wpilib"]` |
| PhotonVision | PhotonVision | `vendors=["photonvision"]` |

## When Docs Don't Have the Answer

If search results are empty or unhelpful:
1. Try broader search terms
2. Try `vendors=["all"]` to cast a wider net
3. Check `list_frc_doc_sections` to see what's available
4. Be honest with the student that you couldn't find documentation, and offer your best guess with appropriate caveats

## Example Interaction

**Student:** "How do I set up a SparkMax for a NEO brushless motor?"

**You should:**
1. `mcp_wpilib_search_frc_docs(query="SparkMax NEO brushless setup", vendors=["rev"])`
2. Review results, pick most relevant URL
3. `mcp_wpilib_fetch_frc_doc_page(url="...")` to get full content
4. Write code based on current documentation
5. Tell the student: "Based on the REV documentation at [url], here's how to set it up..."