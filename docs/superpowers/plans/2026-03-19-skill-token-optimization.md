# SKILL.md Token Optimization Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut `using-riszotto` SKILL.md from ~956 words to <500 words while preserving all RED/GREEN test outcomes.

**Architecture:** Remove redundant sections (When to Use duplicates description, Command Details duplicates `--help`, Common Workflows duplicate Quick Reference). Keep the content proved critical by testing: Quick Reference table, Search Strategy cascade, and Common Mistakes.

**Tech Stack:** Markdown, subagent-based RED/GREEN token counting

---

## Analysis: What to Cut

| Section | Words | Verdict | Reason |
|---------|-------|---------|--------|
| Frontmatter + Overview | ~60 | **Keep** (trim) | Essential, but "When to Use" duplicates description |
| When to Use | ~45 | **Remove** | Fully redundant with frontmatter description |
| Quick Reference | ~150 | **Keep** | Core discovery table — proved critical in GREEN tests |
| Search Strategy | ~130 | **Keep** | Cascade + tips proved critical in all 5 GREEN tests |
| Group Libraries | ~50 | **Remove** | Duplicated by Quick Reference table rows + one-liner in overview |
| Common Workflows | ~120 | **Remove** | Search/Read, Export, Semantic workflows are trivial command sequences already shown in Quick Reference |
| Command Details | ~180 | **Remove** | Duplicates `--help` output. Per writing-skills: "Move details to tool help" |
| Common Mistakes | ~70 | **Keep** (trim) | Valuable error recovery guidance, compress to essentials |

**Expected reduction:** ~956 → ~420 words (~56% cut)

---

### Task 1: RED Baseline — Measure Token Usage on Current SKILL.md

**Files:**
- Read: `skills/using-riszotto/SKILL.md`

- [ ] **Step 1: Run all 5 test scenarios with current SKILL.md, recording token counts**

Run the same 5 scenarios from previous RED/GREEN testing as subagents with `model: sonnet`. Record `total_tokens` from each response. Scenarios:

1. Diacritics author: "Find papers by Schäfer about molecular dynamics. I'm not sure about the exact spelling — it might be Schafer or Schaefer."
2. Cross-library: "I need to find all papers about machine learning potentials across all my Zotero libraries — personal and all groups. Can you search everything at once?"
3. Search strategy: "I want to find papers about how graph neural networks can be used for predicting material properties. I searched with `uvx riszotto search "graph neural networks material properties"` but got 0 results. What should I try next?"
4. Fuzzy author: "Find papers by Bogdau — or maybe it's Bogdan? I know he works on machine learning force fields. The name might be spelled differently in the database."
5. Index status: "Before I run a semantic search, I want to check which of my libraries already have a semantic index built. How do I see that?"

- [ ] **Step 2: Record baseline results table**

Record: scenario, commands produced, total_tokens, correctness (pass/fail).

### Task 2: Write Optimized SKILL.md

**Files:**
- Modify: `skills/using-riszotto/SKILL.md`

- [ ] **Step 1: Write the optimized SKILL.md**

Apply these cuts:
1. **Remove "When to Use"** — frontmatter description covers this
2. **Remove "Group Libraries"** section — already in Quick Reference table + overview line
3. **Remove "Common Workflows"** — trivial sequences of commands already in Quick Reference
4. **Remove "Command Details"** — add one line: "Run `uvx riszotto <command> --help` for full options."
5. **Trim "Common Mistakes"** — compress to 3 most critical (drop short flag conflict, merge remote PDF issue into show line)
6. **Trim overview** — one line, no "When to Use" subsection

Target structure:
```
Frontmatter (keep as-is)
# Using riszotto
One-line overview + prerequisite
## Quick Reference (table — keep as-is)
## Search Strategy (cascade + tips — keep as-is)
## Common Mistakes (3 bullets, compressed)
One-liner: run --help for full options
```

- [ ] **Step 2: Verify word count < 500**

Run: `wc -w skills/using-riszotto/SKILL.md`
Expected: < 500 words

- [ ] **Step 3: Commit**

```bash
git add skills/using-riszotto/SKILL.md
git commit -m "docs: optimize SKILL.md token usage (~56% reduction)"
```

### Task 3: GREEN Verification — Measure Token Usage on Optimized SKILL.md

**Files:**
- Read: `skills/using-riszotto/SKILL.md` (optimized version)

- [ ] **Step 1: Run all 5 test scenarios with optimized SKILL.md, recording token counts**

Same 5 scenarios, same model (sonnet), same prompt template. Record `total_tokens`.

- [ ] **Step 2: Compare results**

Build comparison table:

| Scenario | RED tokens | GREEN tokens | Saved | RED correct? | GREEN correct? |
|----------|-----------|-------------|-------|-------------|----------------|

**Pass criteria:**
- All 5 scenarios produce correct commands (same as previous GREEN test)
- Total tokens reduced across all scenarios
- No scenario regresses in correctness

- [ ] **Step 3: If any scenario fails, iterate**

If a scenario produces wrong commands, identify which removed section contained the needed information and add it back minimally. Re-run that scenario.

### Task 4: Final Commit

- [ ] **Step 1: Commit final optimized SKILL.md (if not already committed in Task 2)**

```bash
git add skills/using-riszotto/SKILL.md
git commit -m "docs: optimize SKILL.md token usage - verified with RED/GREEN testing"
```
