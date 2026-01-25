# GitHub Copilot / Cursor Instructions for FRC Development

You are assisting with a FIRST Robotics Competition (FRC) project using WPILib. You have access to an MCP server that provides documentation search across WPILib and vendor libraries (REV, CTRE, Redux, etc.).

IMPORTANT: Before answering any question about FRC programming, motor controllers, sensors, WPILib, or vendor APIs, you SHOULD run the MCP documentation search/fetch tools to verify your answer and provide citations.

## Documentation-First Policy with Smart Fallback

Use MCP tools to search documentation, but apply judgment about when to trust results vs. your own knowledge:

**When to trust search results:**
- Results have high confidence scores (> 0.5)
- Multiple relevant results from the same vendor
- Results directly mention the exact API/hardware asked about

**When to use your knowledge instead:**
- Search returns no results or very low confidence
- Results seem irrelevant to the actual question
- You have strong knowledge about a common FRC topic

Required workflow for FRC questions:

- **Step 1 — Format Query:** Convert the user's question into effective search keywords (see Query Formatting below)
- **Step 2 — Search:** Call `mcp_wpilib_search_frc_docs(query=..., vendors=[...])`. Check the `confidence` scores and `suggestions` in results.
- **Step 3 — Evaluate Results:** If confidence is low or results seem off, try alternative queries or use your knowledge with appropriate caveats.
- **Step 4 — Fetch:** For high-confidence results, call `mcp_wpilib_fetch_frc_doc_page(url=...)` to get full content.
- **Step 5 — Answer with citations:** Include documentation URLs when available. If using your knowledge, note that documentation wasn't available.

## Query Formatting Guidelines

**CRITICAL:** Format queries as keyword searches, not natural language questions.

| User Question | BAD Query | GOOD Query |
|---------------|-----------|------------|
| "How do I configure a SparkMax?" | "how do I configure a sparkmax" | "SparkMax configuration" |
| "What's the best way to set up PID?" | "what is the best way to set up pid" | "PID controller setup" |
| "Can you show me CAN bus wiring?" | "can you show me can bus wiring" | "CAN bus wiring" |

**Query formatting rules:**
1. Remove question words (how, what, why, can, etc.)
2. Use the exact product names: `SparkMax`, `TalonFX`, `CANcoder`, `NEO`
3. Keep FRC acronyms intact: `CAN`, `PID`, `PWM`, `DIO`
4. Use 2-4 keywords, not full sentences
5. Include the action: "configure", "setup", "wiring", "code example"

**Examples of good queries:**
```
"SparkMax brushless configuration"
"TalonFX PID tuning"
"CAN bus troubleshooting"
"command-based subsystem example"
"swerve drive odometry"
"NEO current limit"
```

## Understanding Search Results

The search returns results with these fields:
- `confidence`: 0.0-1.0 score (higher = more relevant)
- `suggestions`: Alternative queries if results are weak

**Interpreting confidence:**
- `> 0.7`: High confidence - trust these results
- `0.4 - 0.7`: Medium confidence - results may be relevant
- `< 0.4`: Low confidence - consider rephrasing or using your knowledge

If you see suggestions like `'sparkmax' → 'spark max'`, try the suggested term.

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

## Automatic Context Detection

The search tool **automatically detects** the project's programming language and vendor libraries by scanning:
- File extensions (.java, .py, .cpp)
- Build files (build.gradle, pyproject.toml, CMakeLists.txt)
- Vendordeps folder (vendordeps/*.json)
- Import statements in source code

**This means you usually don't need to specify `language` or `vendors`!**

```
# Let auto-detection handle it (recommended)
mcp_wpilib_search_frc_docs(query="SparkMax configuration")

# Or disable auto-detection if needed
mcp_wpilib_search_frc_docs(query="SparkMax configuration", auto_detect=false, vendors=["rev"], language="Java")
```

**To see what was detected:**
```
mcp_wpilib_detect_project_context()
```

This returns the detected language, vendors, and confidence level. Use this at the start of a session to understand the project's stack.

## Language and Version Awareness

- The language is **auto-detected** from the project. Only ask the student if detection fails.
- Default to the current season (2025) unless specified otherwise
- Override auto-detection when needed:
```
search_frc_docs(query="command based", language="Python", version="2025", auto_detect=false)
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

If search results are empty, low confidence, or seem irrelevant:

1. **Rephrase the query** using the formatting guidelines above
2. **Try synonyms:** The search expands common terms automatically, but you can try:
   - "motor controller" ↔ "SparkMax" / "TalonFX"
   - "encoder" ↔ "CANcoder" / "through bore"
   - "gyro" ↔ "Pigeon" / "NavX"
3. **Broaden the vendor:** Try `vendors=["all"]`
4. **Check suggestions:** The search may suggest alternative spellings
5. **Use your knowledge:** If search consistently fails, you likely have accurate knowledge about the topic. Answer with a note like: "I couldn't find this in the current documentation index, but based on my knowledge..."

**Don't apologize excessively** for missing docs. The documentation index doesn't cover everything - it's a supplement, not a replacement for your knowledge.

## Example Interaction

**Student:** "How do I set up a SparkMax for a NEO brushless motor?"

**You should:**
1. `mcp_wpilib_search_frc_docs(query="SparkMax NEO brushless setup", vendors=["rev"])`
2. Review results, pick most relevant URL
3. `mcp_wpilib_fetch_frc_doc_page(url="...")` to get full content
4. Write code based on current documentation
5. Tell the student: "Based on the REV documentation at [url], here's how to set it up..."