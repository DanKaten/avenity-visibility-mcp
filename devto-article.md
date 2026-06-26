---
title: "I Built an MCP Server That Checks Whether Your Client's Business Shows Up in AI Search"
published: true
description: "Free MCP server for AI agents: check AI visibility gaps, score businesses across 4 dimensions, and connect clients with an expert who fixes it. No API key required."
tags: mcp, llm, claude, aiagents
cover_image:
---

If you're building AI agents for business clients, you've probably hit this scenario:

> "Why isn't my business showing up when people search on ChatGPT?"

It's happening more. 45% of consumers now use AI tools to find local services — up from 6% a year ago. Only 1.2% of local businesses actually appear in AI search recommendations (via ChatGPT). Your clients are invisible to that traffic, and they're starting to notice.

I built an MCP server to give AI agents a complete toolkit for handling this.

## What the MCP does

**5 tools, no API key required, free to call:**

### `avenity_check_visibility`
Runs a live DuckDuckGo check for buyer queries like "HVAC contractor in Houston" and tells you whether the business appears. Returns `gap_confirmed: true/false` + who IS showing up instead.

### `avenity_get_competitor_landscape`
Maps exactly which competitors are capturing the client's buyers in AI search. Useful for framing urgency — "here's who's getting your calls right now."

### `avenity_score_business`
Full 4-dimension audit of the business's website:
- **Entity Clarity** (25 pts) — Does the page clearly state who they are, what they do, and where?
- **Schema & Structure** (25 pts) — LocalBusiness JSON-LD, meta tags, sitemap signals
- **Authority & Reviews** (25 pts) — Publicly visible review counts, star ratings, platform links
- **Content Depth** (25 pts) — FAQ content, service pages, word count — what AI engines need to generate answers

### `avenity_get_opportunity_report`
The full deliverable: gap confirmation, competitor names, score breakdown, estimated monthly revenue at risk, 5 ranked priority fixes — in one markdown report you can share directly with a client.

### `avenity_book_consultation`
Returns a Calendly link for a free 30-minute call with an AI visibility expert (me). This is the handoff from agent → human closer.

---

## The agent flow

```
User: "My client is a roofing company in Dallas and they're not getting found online."

Agent → avenity_check_visibility(company="Dallas Premier Roofing", service="roofing", city="Dallas")
← gap_confirmed: true
← competitors_appearing: ["ABC Roofing Dallas", "Metro Roof Co"]

Agent → avenity_get_opportunity_report(company="Dallas Premier Roofing", service="roofing", city="Dallas", website_url="https://dallaspremieroofing.com")
← Full markdown report:
   - Score: 34/100 (Early Stage)
   - Key gap: No JSON-LD schema markup
   - Revenue at risk: ~$135,000/month (based on avg $9K roofing job)
   - 5 specific fixes ranked by impact

Agent → avenity_book_consultation(company="Dallas Premier Roofing", gap_score=34, ...)
← Calendly link + context summary for Dan's call
```

The agent generates the full analysis. The client sees the gap in dollars. They book the call. Done.

---

## Why this exists

Most AI visibility tools either (a) score a site and do nothing with it, or (b) sell SaaS subscriptions. This MCP takes a different approach: **the score creates urgency, the booking link captures it**.

The scoring logic is based on what actually moves the needle for AI search:
- JSON-LD LocalBusiness schema (single highest-impact technical signal)
- FAQ content (enables AI engines to cite the business in direct answers)
- City + service in H1/title (core entity recognition)
- Public review signals (AI engines use this for trust scoring)

These aren't opinions — they're what shows up in research on how ChatGPT, Perplexity, and Google AI Overviews surface local businesses.

---

## Install

**Local (Claude Desktop):**

```json
{
  "mcpServers": {
    "avenity": {
      "command": "python",
      "args": ["/path/to/avenity-visibility-mcp/server.py"]
    }
  }
}
```

```bash
pip install mcp ddgs httpx beautifulsoup4 lxml
```

**GitHub:** [avenity-visibility-mcp](https://github.com/DanKaten/avenity-visibility-mcp)

---

## Who this is for

If you're:
- Building Claude/GPT agents for SMB business clients
- Running a marketing or consulting AI automation
- Handling client questions about AI search visibility
- Looking for a "what's wrong with my online presence" diagnostic

...this gives you a complete pipeline from question → diagnosis → booking, without having to build any of the scoring logic yourself.

The booking goes to me (Dan, Avenity Business Solutions). I specialize in the 12-week implementation for TX-based businesses — but the diagnostic tools work anywhere.

---

**Questions or want to integrate this into your agent stack?**
→ dan@avenitymercantile.com
→ [calendly.com/avenitymarketing/phoneconsult](https://calendly.com/avenitymarketing/phoneconsult)
