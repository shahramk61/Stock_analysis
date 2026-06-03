# Phase 2: Quantitative Analyst Integration Implementation Plan

**Status**: Phase 2 - Implementation Planning  
**Date**: 2026-05-16

---

## Goal
Create a practical, flexible plan to integrate the Quantitative Analyst into TradingAgents while following first principles and keeping future extensibility in mind.

---

## Core Principles for Implementation

1. **First Principles Thinking**
   - Design based on what the system actually needs (rich quantitative data + risk signals).
   - Avoid blindly copying existing analyst patterns if they don't fit well.

2. **Flexibility & Extensibility**
   - Start simple.
   - Make it easy to later add: debate participation, dedicated tool nodes, heavier LLM usage, etc.

3. **Minimal Disruption**
   - Integrate cleanly without breaking existing analyst flow.

---

## Recommended Integration Steps

### Step 1: Port the Agent to TradingAgents Structure

**Recommended location:**
```
tradingagents/agents/analysts/quantitative_analyst.py
```

**Key requirements when porting:**
- Keep the function signature: `create_quantitative_analyst(llm=None)`
- Accept `llm` for consistency, but primarily rely on our signals package.
- Return a node function that updates the shared state with `quantitative_report`.

### Step 2: Make it Selectable

Modify the analyst selection logic so users can enable it via:

```python
selected_analysts = ["market", "fundamentals", "quantitative"]
```

This is the cleanest and most consistent way with how TradingAgents currently works.

### Step 3: Wire it into GraphSetup

- Add the Quantitative Analyst to run in parallel with other analysts.
- Ensure its output (`quantitative_report`) is available to Researchers and the Trader.

### Step 4: Start Simple (v1 MVP)

**v1 Design Principles:**
- The agent acts as a **Data Provider** (not an active debater).
- It outputs the hybrid quantitative report.
- It does **not** actively speak in the Researcher debate in v1.
- Debate participation can be added in v2+ if desired.
- Keep implementation simple and focused on delivering high-quality quantitative reports.

---

## Implementation Recommendations

| Area                        | Recommendation                              | Rationale |
|----------------------------|---------------------------------------------|---------|
| **LLM Usage**              | Light / Optional                            | Our strength is in the signals, not LLM reasoning |
| **Debate Participation**   | Start as read-only data provider            | Easier to add speaking ability later |
| **Tool Node**              | Not required in first version               | Can be added later if needed |
| **Output**                 | Keep hybrid format + Key Takeaways          | Already working well |
| **Conviction**             | Keep multi-factor logic                     | Provides useful signal to other agents |

---

## Potential Challenges & Mitigations

| Challenge                          | Mitigation |
|------------------------------------|----------|
| Overlap with Market Analyst        | Clearly position Quantitative Analyst as "model-driven + risk focused" vs technical indicators |
| LLM parameter handling             | Accept it gracefully but don't depend on it heavily |
| Future desire to let it debate     | Design the node so adding debate capability later is easy |
| Maintaining sync with our signals  | Keep the core logic in our `signals/` package and import it |

---

## Suggested Development Order

1. Create `quantitative_analyst.py` in TradingAgents (following the existing pattern).
2. Add it to the analyst selection system.
3. Wire it into the graph so it runs in parallel.
4. Test with `selected_analysts` including `"quantitative"`.
5. Validate that Researchers and Trader can access its output.
6. (Optional later) Add ability for it to participate in debate.

---

## Open Items for Discussion

- Do we want to create a small wrapper so the agent can be developed in our repo and imported into TradingAgents?
- Should we prepare a minimal example of how to enable it via config/CLI?
- Any specific output fields the Trader or Risk Manager would benefit from?

---

**Next Step after this plan**: Begin actual integration work (either by creating the file in TradingAgents or preparing importable code from our repo).