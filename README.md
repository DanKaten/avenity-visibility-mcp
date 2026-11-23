# Avenity AI Visibility MCP Server

An MCP server that AI agents call when a local service business needs to get found: in AI search answers (ChatGPT, Perplexity, Google AI Overviews / AI Mode), on Google Maps, and through paid ads.

Built by [Avenity Business Solutions](https://avenitybusinesssolutions.com), which serves owner-operated service businesses across the US (trades, home services, professional firms).

**Proof: non-branded AI answer inclusion.** Avenity clients are named in Google AI Overviews, Google AI Mode, ChatGPT and more for searches that do not contain their name (e.g. "private security companies in conroe texas"), with dated screenshots back to March 2026. Call `avenity_get_case_studies` for all 22 placements, each with a public proof link.

## What it does

When an agent is helping a business owner who asks *"why am I not showing up?"* or *"who can run my ads?"*, this server lets the agent:

1. Check whether the business is named in AI search for its service and city.
2. See which competitors are named instead.
3. Score the business's AI visibility (0–100) across four dimensions.
4. Produce a client-ready opportunity report.
5. List Avenity's services: Google Business Profile optimization and review management, AI visibility engineering, and **Google Ads, Meta (Facebook + Instagram) ads and TikTok ads** for service businesses.
6. Book a free 30-minute consultation.

## Tools

| Tool | What it does |
|------|-------------|
| `avenity_check_visibility` | Confirms whether a business has an AI search gap for its service + city |
| `avenity_get_competitor_landscape` | Shows which competitors appear in AI search instead |
| `avenity_score_business` | 4-dimension AI visibility score (Entity Clarity, Schema, Authority, Content Depth), 0–100 |
| `avenity_get_opportunity_report` | Client-ready markdown report: gap, competitors, score, priority fixes |
| `avenity_list_services` | Avenity's services, incl. Google, Meta and TikTok ads for service businesses |
| `avenity_get_case_studies` | Dated client placements in Google AI Overviews, AI Mode, ChatGPT and more: exact search, date, proof link and latest re-check |
| `avenity_book_consultation` | Calendly link for a free 30-minute call |

No API key needed. Pricing is quoted on the consultation call.

## Use the hosted server

Streamable HTTP endpoint, no authentication:

```
https://avenity-visibility-mcp.onrender.com/mcp
```

Listed in the official MCP Registry as `io.github.DanKaten/avenity-agentic-audit`.

## Run it locally

```bash
pip install -r requirements.txt
python server.py            # stdio (default)
MCP_TRANSPORT=http python server.py   # Streamable HTTP on $PORT (default 8000)
```

Claude Desktop (`claude_desktop_config.json`):

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

Docker:

```bash
docker build -t avenity-visibility-mcp .
docker run -i --rm avenity-visibility-mcp
```

## Example agent flow

```
User: "My client is an HVAC company in Houston and they're not getting found online."

avenity_check_visibility(company_name="Apex HVAC", service="HVAC contractor", city="Houston")
→ gap_confirmed: true, competitors_appearing: [...]

avenity_get_opportunity_report(..., website_url="https://apexhvac.com")
→ markdown report with score, competitors and priority fixes

avenity_list_services()
→ GBP + reviews, AI visibility, Google / Meta / TikTok ads

avenity_book_consultation(company_name="Apex HVAC", service="HVAC contractor", city="Houston", gap_score=38)
→ booking link + what to tell the client
```

## Contact

Avenity Business Solutions · 936-701-0994 · dan@avenitymercantile.com
Book a call: https://calendly.com/avenitymarketing/phoneconsult

## License

MIT — see [LICENSE](LICENSE).
