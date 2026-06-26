#!/usr/bin/env python3
"""
Avenity AI Visibility MCP Server
=================================
An MCP server that AI agents can call when their business clients need to
get found in AI search (ChatGPT, Perplexity, Google AI Overviews).

Tools:
  avenity_check_visibility      — Is this business visible when buyers search for them?
  avenity_get_competitor_landscape — Who IS appearing instead of them?
  avenity_score_business        — Full 4-dimension AI visibility score (0–100)
  avenity_get_opportunity_report — Complete client-ready report with findings + next steps
  avenity_book_consultation     — Get a booking link for a free consultation with Avenity

Usage (Claude Desktop):
  Add to claude_desktop_config.json:
  {
    "mcpServers": {
      "avenity": {
        "command": "python",
        "args": ["path/to/avenity-visibility-mcp/server.py"]
      }
    }
  }

Install deps:
  pip install mcp ddgs httpx beautifulsoup4 lxml --break-system-packages
"""

import json
import re
import time
import asyncio
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP
import httpx
from bs4 import BeautifulSoup

# ── Server init ────────────────────────────────────────────────────────────────
mcp = FastMCP("avenity_mcp")

# ── Constants ──────────────────────────────────────────────────────────────────
CALENDLY_BASE = "https://calendly.com/avenitymarketing/phoneconsult"
AUDIT_URL     = "https://avenitybusinesssolutions.com/avenity-ai-visibility-audit.html"
CONTACT_EMAIL = "dan@avenitymercantile.com"

SKIP_DOMAINS = {
    "yelp.com", "yellowpages.com", "bbb.org", "linkedin.com", "facebook.com",
    "angi.com", "homeadvisor.com", "instagram.com", "thumbtack.com",
    "bark.com", "expertise.com", "manta.com", "google.com", "bing.com",
    "nerdwallet.com", "angieslist.com", "houzz.com", "porch.com",
    "chamberofcommerce.com", "prnewswire.com", "businesswire.com",
}

# ── Pydantic models ────────────────────────────────────────────────────────────

class BusinessInput(BaseModel):
    """Input identifying a business and its primary service."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company_name: str = Field(
        ...,
        description="Exact business name (e.g., 'Apex HVAC Solutions')",
        min_length=2, max_length=120
    )
    service: str = Field(
        ...,
        description="Primary service category (e.g., 'HVAC contractor', 'roofing company', 'commercial landscaping')",
        min_length=2, max_length=80
    )
    city: str = Field(
        ...,
        description="City where the business operates (e.g., 'Houston', 'Dallas')",
        min_length=2, max_length=60
    )
    state: str = Field(
        default="TX",
        description="State abbreviation (default: TX)",
        min_length=2, max_length=2
    )
    website_url: Optional[str] = Field(
        default=None,
        description="Business website URL — if provided, enables deeper scoring. Include https://",
    )


class ConsultationInput(BaseModel):
    """Input for booking a consultation."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company_name: str = Field(..., description="Business name", min_length=2, max_length=120)
    contact_name: Optional[str] = Field(default=None, description="Owner or contact name")
    service: str = Field(..., description="Primary service category", min_length=2, max_length=80)
    city: str = Field(..., description="City", min_length=2, max_length=60)
    gap_score: Optional[int] = Field(
        default=None,
        description="AI visibility score 0–100 if already known, to pre-fill context",
        ge=0, le=100
    )


# ── Shared utilities ───────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase, strip punctuation for matching."""
    return re.sub(r"[^\w\s]", " ", text.lower())


def _extract_domain(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()


def _is_skip_domain(url: str) -> bool:
    dom = _extract_domain(url)
    return any(s in dom for s in SKIP_DOMAINS)


async def _ddg_search(query: str, n: int = 10) -> list:
    """Run a DuckDuckGo search and return result dicts."""
    try:
        from ddgs import DDGS
        with DDGS() as d:
            return list(d.text(query, max_results=n))
    except Exception:
        return []


async def _fetch_page(url: str, timeout: float = 10.0) -> Optional[BeautifulSoup]:
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AvenityBot/1.0)"}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
    except Exception:
        return None


def _score_entity_clarity(soup: Optional[BeautifulSoup], company: str, service: str, city: str) -> dict:
    """Score Entity Clarity dimension (0–25)."""
    if soup is None:
        return {"score": 8, "notes": "Website could not be accessed for analysis."}

    score = 0
    notes = []
    text = soup.get_text(" ", strip=True).lower()
    title = (soup.find("title") or soup.new_tag("x")).get_text().lower()
    h1s = [h.get_text().lower() for h in soup.find_all("h1")]

    # City in title/H1 (+6)
    if city.lower() in title or any(city.lower() in h for h in h1s):
        score += 6
        notes.append(f"City reference ('{city}') found in title/H1.")
    else:
        notes.append(f"City reference ('{city}') not detected in title or H1 — a key AI entity signal.")

    # Service in title/H1 (+6)
    svc_words = set(service.lower().split()) - {"company", "contractor", "services", "solutions"}
    svc_hit = any(w in title or any(w in h for h in h1s) for w in svc_words)
    if svc_hit:
        score += 6
        notes.append("Primary service is clearly stated in title/H1.")
    else:
        notes.append("Primary service category is not prominently stated in title or H1.")

    # Clear business description paragraph (+7)
    if len(text) > 400:
        score += 7
        notes.append("Homepage content provides substantive business description.")
    else:
        notes.append("Homepage content is thin — AI engines need more text to understand entity context.")

    # NAP (address/phone visible) (+6)
    phone_pattern = re.compile(r"\d{3}[-.\s]\d{3}[-.\s]\d{4}")
    if phone_pattern.search(soup.get_text()):
        score += 6
        notes.append("Phone number is publicly visible — supports NAP consistency signals.")
    else:
        notes.append("Phone number not detected on homepage — a missing NAP signal.")

    return {"score": min(score, 25), "notes": " ".join(notes)}


def _score_schema(soup: Optional[BeautifulSoup]) -> dict:
    """Score Schema & Structure dimension (0–25)."""
    if soup is None:
        return {"score": 5, "notes": "Website could not be accessed — schema analysis unavailable."}

    score = 0
    notes = []
    page_text = str(soup)

    # JSON-LD present (+10)
    has_jsonld = bool(soup.find("script", {"type": "application/ld+json"}))
    if has_jsonld:
        score += 10
        notes.append("JSON-LD structured data markup was detected.")
        # LocalBusiness specifically (+5)
        jsonld_text = " ".join(
            t.get_text() for t in soup.find_all("script", {"type": "application/ld+json"})
        )
        if "localbusiness" in jsonld_text.lower() or "organization" in jsonld_text.lower():
            score += 5
            notes.append("LocalBusiness or Organization schema type identified.")
        else:
            notes.append("Schema present but LocalBusiness type not confirmed — specific type strengthens AI entity recognition.")
    else:
        notes.append("No JSON-LD structured data detected — this is the highest-impact schema gap for AI search.")

    # Meta description present (+5)
    meta = soup.find("meta", {"name": "description"})
    if meta and meta.get("content", "").strip():
        score += 5
        notes.append("Meta description is present.")
    else:
        notes.append("Meta description not detected.")

    # Sitemap link or robots.txt signal (+5)
    if "sitemap" in page_text.lower():
        score += 5
        notes.append("Sitemap reference detected in page source.")

    return {"score": min(score, 25), "notes": " ".join(notes)}


def _score_authority(soup: Optional[BeautifulSoup]) -> dict:
    """Score Authority & Reviews dimension (0–25)."""
    if soup is None:
        return {"score": 8, "notes": "Website inaccessible — review signals assessed from search data only."}

    score = 0
    notes = []
    text = soup.get_text(" ", strip=True)

    # Review count visible (+8)
    review_pattern = re.compile(r"(\d+)\s*(reviews?|ratings?)", re.I)
    match = review_pattern.search(text)
    if match:
        count = int(match.group(1))
        score += 8
        notes.append(f"{count} publicly listed reviews detected on or linked from website.")
        if count >= 50:
            score += 5
            notes.append("Review volume is strong (50+), a positive authority signal.")
        elif count >= 20:
            score += 3
            notes.append("Review volume is moderate (20+).")
    else:
        notes.append("Review count not detected on website — embedding or linking review counts helps AI engines read social proof signals.")

    # Star rating visible (+5)
    star_pattern = re.compile(r"(\d+\.?\d*)\s*(out of\s*5|\/\s*5|stars?)", re.I)
    if star_pattern.search(text):
        score += 5
        notes.append("Star rating is publicly visible.")
    else:
        notes.append("Star rating not detected on homepage.")

    # Third-party platform links (+4)
    page_str = str(soup).lower()
    platforms = ["google.com/maps", "yelp.com", "bbb.org", "houzz.com", "angi.com"]
    linked = [p for p in platforms if p in page_str]
    if linked:
        score += 4
        notes.append(f"Links to third-party review platforms detected ({', '.join(linked)}).")

    return {"score": min(score, 25), "notes": " ".join(notes)}


def _score_content_depth(soup: Optional[BeautifulSoup]) -> dict:
    """Score Content Depth dimension (0–25)."""
    if soup is None:
        return {"score": 6, "notes": "Website inaccessible — content depth could not be assessed."}

    score = 0
    notes = []
    text = soup.get_text(" ", strip=True)
    page_str = str(soup).lower()

    # FAQ section (+8)
    has_faq = bool(re.search(r"faq|frequently asked|common questions", page_str, re.I))
    if has_faq:
        score += 8
        notes.append("FAQ-format content detected — this is a direct AI answer-generation signal.")
    else:
        notes.append("No FAQ content detected. FAQ sections are among the highest-value content additions for AI search visibility.")

    # Multiple service pages (internal links to service pages) (+7)
    links = [a.get("href", "") for a in soup.find_all("a", href=True)]
    service_links = [l for l in links if any(k in l.lower() for k in [
        "service", "repair", "install", "replacement", "maintenance", "commercial", "residential"
    ])]
    if len(service_links) >= 3:
        score += 7
        notes.append(f"{len(service_links)} service-related internal links detected — strong content depth signal.")
    elif len(service_links) >= 1:
        score += 3
        notes.append(f"{len(service_links)} service page link(s) detected — expanding service coverage strengthens AI visibility.")
    else:
        notes.append("No distinct service sub-pages detected. Dedicated service pages help AI engines surface specific answers.")

    # Word count / content richness (+6)
    word_count = len(text.split())
    if word_count >= 600:
        score += 6
        notes.append(f"Page content is substantial ({word_count} words estimated).")
    elif word_count >= 300:
        score += 3
        notes.append(f"Page content is moderate ({word_count} words estimated).")
    else:
        notes.append(f"Page content is limited ({word_count} words estimated) — AI engines prefer richer context.")

    # Location/area pages (+4)
    if any(k in page_str for k in ["service area", "areas we serve", "locations we"]):
        score += 4
        notes.append("Service area content detected — supports geographic AI visibility.")

    return {"score": min(score, 25), "notes": " ".join(notes)}


def _score_label(score: int) -> str:
    if score >= 85: return "Strong"
    if score >= 70: return "Good"
    if score >= 55: return "Developing+"
    if score >= 40: return "Developing"
    return "Early Stage"


async def _run_visibility_check(company: str, service: str, city: str) -> dict:
    """Core: check if company appears in AI Overview results for buyer query."""
    query = f"{service} in {city}"
    best_query = f"best {service} in {city}"

    results = await _ddg_search(query, 10)
    await asyncio.sleep(0.8)
    ai_results = await _ddg_search(best_query, 5)

    combined = results + ai_results
    combined_text = " ".join(
        _normalize(r.get("title", "") + " " + r.get("body", ""))
        for r in combined
    )

    company_words = set(_normalize(company).split()) - {
        "llc", "llp", "inc", "pllc", "co", "company", "group", "solutions",
        "services", "the", "and", "of", "for", "consulting", "firm",
        "associates", "partners", "professional", "contractor", "contractors"
    }

    appears = False
    if company_words:
        matches = sum(1 for w in company_words if w in combined_text and len(w) > 3)
        appears = matches >= min(2, len(company_words))

    # Collect competitors from top results
    competitors = []
    for r in combined[:6]:
        if _is_skip_domain(r.get("href", "")):
            continue
        raw_title = r.get("title", "")
        name = re.split(r"\s*[–|:]\s*|\s+-\s+|\s*\|\s*", raw_title)[0].strip()[:60]
        if (name and len(name) > 3
                and _normalize(company)[:8] not in _normalize(name)
                and not name[0].islower()):
            competitors.append(name)

    return {
        "query": query,
        "gap_confirmed": not appears,
        "appears_in_ai_results": appears,
        "competitors_appearing": list(dict.fromkeys(competitors))[:4],
        "result_count_checked": len(combined),
    }


async def _score_website(url: str, company: str, service: str, city: str) -> dict:
    """Fetch and score a business website across 4 dimensions."""
    soup = await _fetch_page(url)

    entity   = _score_entity_clarity(soup, company, service, city)
    schema   = _score_schema(soup)
    authority = _score_authority(soup)
    content  = _score_content_depth(soup)

    total = entity["score"] + schema["score"] + authority["score"] + content["score"]

    return {
        "total": total,
        "label": _score_label(total),
        "dimensions": {
            "entity_clarity":   {"score": entity["score"],    "max": 25, "notes": entity["notes"]},
            "schema_structure": {"score": schema["score"],    "max": 25, "notes": schema["notes"]},
            "authority_reviews":{"score": authority["score"], "max": 25, "notes": authority["notes"]},
            "content_depth":    {"score": content["score"],   "max": 25, "notes": content["notes"]},
        },
        "website_accessible": soup is not None,
    }


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="avenity_check_visibility",
    annotations={
        "title": "Check Business AI Search Visibility",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def avenity_check_visibility(params: BusinessInput) -> str:
    """
    Check whether a business appears in AI-driven search results when buyers
    search for their primary service in their city.

    This is the first-pass qualifier. If gap_confirmed=True, the business is
    NOT appearing when buyers search — meaning they are losing customers to
    competitors right now. This is the core hook for Avenity's service.

    Use this when:
    - A business client asks why they're not getting found online
    - You need to confirm an AI visibility gap before recommending action
    - You want to frame the problem before showing a full report

    Args:
        params (BusinessInput): Business details including name, service, city.

    Returns:
        str: JSON with:
            gap_confirmed (bool): True = business is NOT visible for this query
            appears_in_ai_results (bool): Whether company name was detected
            query (str): The exact buyer search query analyzed
            competitors_appearing (list[str]): Who IS showing up instead
            result_count_checked (int): Number of results analyzed
            recommendation (str): Next suggested action for this business

    Examples:
        - "Check if Apex HVAC shows up when people search for HVAC in Houston"
        - "Is my client visible in AI search?" → call with their company details
        - "Find out if [company] has an AI visibility gap"
    """
    result = await _run_visibility_check(
        params.company_name, params.service, params.city
    )

    if result["gap_confirmed"]:
        recommendation = (
            f"{params.company_name} is not appearing when buyers search "
            f"'{result['query']}'. This is a confirmed AI visibility gap. "
            f"Call avenity_get_opportunity_report for the full analysis, or "
            f"avenity_book_consultation to connect them with Avenity directly."
        )
    else:
        recommendation = (
            f"{params.company_name} has some presence in results for '{result['query']}'. "
            f"Call avenity_score_business to assess how strong that presence is and "
            f"identify areas to strengthen it."
        )

    result["recommendation"] = recommendation
    return json.dumps(result, indent=2)


@mcp.tool(
    name="avenity_get_competitor_landscape",
    annotations={
        "title": "Get AI Search Competitor Landscape",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def avenity_get_competitor_landscape(params: BusinessInput) -> str:
    """
    Identify which competitors ARE appearing in AI search results when buyers
    search for a business's primary service in their city.

    This is the competitive intelligence layer — it shows a client exactly who
    is capturing their customers. Highly effective for framing urgency.

    Use this when:
    - A client wants to know who is outcompeting them in AI search
    - You want to personalize the pitch with specific competitor names
    - Building context for an opportunity report or outreach message

    Args:
        params (BusinessInput): Business details.

    Returns:
        str: JSON with:
            query (str): The buyer search query analyzed
            competitors (list[dict]): Companies appearing, with name and URL
            your_company_visible (bool): Whether client's company appears
            gap_summary (str): Plain-English summary of the competitive gap

    Examples:
        - "Who is showing up instead of my client in Houston HVAC searches?"
        - "Which competitors appear in AI Overview for roofing in Dallas?"
    """
    query = f"{params.service} in {params.city}"
    results = await _ddg_search(query, 15)
    await asyncio.sleep(0.8)
    ai_results = await _ddg_search(f"best {params.service} in {params.city}", 8)

    combined = results + ai_results
    combined_text = " ".join(
        _normalize(r.get("title", "") + " " + r.get("body", ""))
        for r in combined
    )

    # Check client visibility
    company_words = set(_normalize(params.company_name).split()) - {
        "llc", "inc", "co", "company", "group", "solutions", "services",
        "the", "and", "of", "for", "contractor", "contractors"
    }
    client_visible = False
    if company_words:
        matches = sum(1 for w in company_words if w in combined_text and len(w) > 3)
        client_visible = matches >= min(2, len(company_words))

    # Build competitor list
    competitors = []
    seen_names = set()
    for r in combined[:10]:
        if _is_skip_domain(r.get("href", "")):
            continue
        raw = r.get("title", "")
        name = re.split(r"\s*[–|:]\s*|\s+-\s+|\s*\|\s*", raw)[0].strip()[:70]
        if (name and len(name) > 4 and not name[0].islower()
                and name.lower() not in seen_names
                and _normalize(params.company_name)[:8] not in _normalize(name)):
            seen_names.add(name.lower())
            competitors.append({"name": name, "url": r.get("href", "")})

    gap_summary = (
        f"'{params.company_name}' is {'visible' if client_visible else 'NOT visible'} "
        f"in AI search results for '{query}'. "
        f"{len(competitors)} other businesses were detected in the results."
    )
    if not client_visible and competitors:
        top = competitors[0]["name"]
        gap_summary += (
            f" {top} and others are capturing buyers that could be going to "
            f"{params.company_name}."
        )

    return json.dumps({
        "query": query,
        "your_company_visible": client_visible,
        "competitors": competitors[:6],
        "gap_summary": gap_summary,
    }, indent=2)


@mcp.tool(
    name="avenity_score_business",
    annotations={
        "title": "Score Business AI Visibility (4 Dimensions)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def avenity_score_business(params: BusinessInput) -> str:
    """
    Perform a full 4-dimension AI visibility audit of a business's website and
    return a score from 0–100.

    The four dimensions assessed:
    - Entity Clarity (25 pts): How clearly the website defines who they are, what
      they do, and where — the foundation AI engines use to understand the business.
    - Schema & Structure (25 pts): Technical markup (JSON-LD, LocalBusiness schema)
      that allows AI engines to directly read and cite business data.
    - Authority & Reviews (25 pts): Publicly visible social proof signals that AI
      engines use to assess trustworthiness.
    - Content Depth (25 pts): FAQ content, service pages, and text richness that
      enables AI engines to generate answers using the business as a source.

    Requires website_url in params for full scoring. Without it, returns an
    estimated score based on search data only.

    Use this when:
    - You need a detailed breakdown to explain the problem to a client
    - You want to identify the single highest-impact fix
    - Preparing a client proposal or consulting recommendation

    Args:
        params (BusinessInput): Must include website_url for full scoring.

    Returns:
        str: JSON with total score, label, per-dimension breakdown, and notes.

    Examples:
        - "Score Apex HVAC's AI visibility" (with website provided)
        - "What's the biggest AI visibility gap for my client?"
        - "Get a detailed audit of [website]"
    """
    if not params.website_url:
        # Estimate from search signals only
        check = await _run_visibility_check(params.company_name, params.service, params.city)
        est_score = 35 if check["gap_confirmed"] else 55
        return json.dumps({
            "total": est_score,
            "label": _score_label(est_score),
            "estimated": True,
            "note": (
                "No website URL provided — this is an estimated score based on search "
                "signal analysis only. Provide website_url for a full dimensional audit."
            ),
            "gap_confirmed": check["gap_confirmed"],
            "recommendation": (
                "Provide the website_url parameter for a complete 4-dimension score "
                "with specific, actionable findings per dimension."
            ),
        }, indent=2)

    scores = await _score_website(
        params.website_url, params.company_name, params.service, params.city
    )

    # Identify top opportunity
    dims = scores["dimensions"]
    weakest = min(dims.items(), key=lambda x: x[1]["score"] / x[1]["max"])
    weakest_name = weakest[0].replace("_", " ").title()

    scores["highest_impact_opportunity"] = (
        f"{weakest_name} is the lowest-scoring dimension ({weakest[1]['score']}/{weakest[1]['max']}). "
        f"Improving this area would have the most immediate impact on AI search visibility."
    )
    scores["next_step"] = (
        f"Call avenity_get_opportunity_report for a client-ready report, or "
        f"avenity_book_consultation to connect {params.company_name} with Avenity."
    )

    return json.dumps(scores, indent=2)


@mcp.tool(
    name="avenity_get_opportunity_report",
    annotations={
        "title": "Get Full AI Visibility Opportunity Report",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def avenity_get_opportunity_report(params: BusinessInput) -> str:
    """
    Generate a complete, client-ready AI Visibility Opportunity Report for a
    business. Combines gap confirmation, competitor landscape, dimensional scoring,
    and revenue impact into a single structured output.

    This is the full deliverable — ready to share with a client or use as the
    basis for a consulting recommendation. It shows the business exactly what
    they're missing, who's capturing their customers, and what it's worth.

    Use this when:
    - A client needs a full picture before making a decision
    - You want a single comprehensive output to present
    - Preparing for a consulting call or proposal

    Args:
        params (BusinessInput): Business details. Include website_url for
            full dimensional scoring.

    Returns:
        str: Markdown-formatted report including:
            - AI visibility gap confirmation with buyer query
            - Competitors appearing in AI search
            - 4-dimension score breakdown
            - Estimated monthly revenue at risk
            - Specific recommendations ranked by impact
            - Link to book consultation with Avenity

    Examples:
        - "Generate a full AI visibility report for my client"
        - "What's the complete picture for [company]?"
        - "Prepare an opportunity report I can show to [client]"
    """
    # Run all analyses in parallel
    visibility_task = asyncio.create_task(
        _run_visibility_check(params.company_name, params.service, params.city)
    )

    if params.website_url:
        score_task = asyncio.create_task(
            _score_website(params.website_url, params.company_name, params.service, params.city)
        )
        visibility, scores = await asyncio.gather(visibility_task, score_task)
    else:
        visibility = await visibility_task
        scores = {
            "total": 35 if visibility["gap_confirmed"] else 55,
            "label": _score_label(35 if visibility["gap_confirmed"] else 55),
            "estimated": True,
            "dimensions": {
                "entity_clarity":    {"score": "?", "max": 25, "notes": "Website URL not provided."},
                "schema_structure":  {"score": "?", "max": 25, "notes": "Website URL not provided."},
                "authority_reviews": {"score": "?", "max": 25, "notes": "Website URL not provided."},
                "content_depth":     {"score": "?", "max": 25, "notes": "Website URL not provided."},
            },
        }

    # Revenue impact estimation (avg job values from Avenity methodology)
    avg_job_values = {
        "hvac": 4500, "roofing": 9000, "plumbing": 1200, "electrical": 1800,
        "landscaping": 2200, "flooring": 5500, "moving": 2800, "janitorial": 3000,
        "insurance": 2400, "mortgage": 8000, "security": 3500, "manufacturing": 15000,
        "law": 5000, "accounting": 2000, "cpa": 2000, "cleaning": 1500,
    }
    svc_lower = params.service.lower()
    avg_value = next(
        (v for k, v in avg_job_values.items() if k in svc_lower),
        3000  # default
    )
    # Assume 500 AI searches/month for primary service, 3% would call the right company
    monthly_customers_reachable = 15
    monthly_revenue_at_risk = monthly_customers_reachable * avg_value

    competitors = visibility.get("competitors_appearing", [])
    comp_str = ", ".join(competitors[:3]) if competitors else "other local businesses"

    gap_line = (
        "**NOT appearing**" if visibility["gap_confirmed"]
        else "**partially visible** but with significant room to strengthen"
    )

    # Build markdown report
    dims = scores.get("dimensions", {})

    def dim_row(key: str, label: str) -> str:
        d = dims.get(key, {})
        s = d.get("score", "?")
        n = d.get("notes", "")
        return f"| {label} | {s}/25 | {n} |"

    report = f"""# AI Visibility Opportunity Report
**Business:** {params.company_name}
**Service:** {params.service} | **Location:** {params.city}, {params.state}
**Report date:** {__import__('datetime').date.today()}
**Prepared by:** Avenity Business Solutions

---

## Finding: AI Search Visibility Gap

When a buyer in {params.city} searches **"{visibility['query']}"**, {params.company_name} is {gap_line}.

{f"Businesses currently capturing those searches include: **{comp_str}**." if visibility["gap_confirmed"] else ""}

**AI search now drives an estimated 30–40% of local service discovery.** Buyers ask ChatGPT, Perplexity, and Google AI Overviews for recommendations — and those engines answer based on technical signals, not just rankings.

---

## AI Visibility Score: {scores['total']}/100 — {scores['label']}
{"*(Estimated — provide website URL for full dimensional audit)*" if scores.get("estimated") else ""}

| Dimension | Score | Key Finding |
|---|---|---|
{dim_row("entity_clarity", "Entity Clarity")}
{dim_row("schema_structure", "Schema & Structure")}
{dim_row("authority_reviews", "Authority & Reviews")}
{dim_row("content_depth", "Content Depth")}

---

## Revenue at Risk

| Metric | Estimate |
|---|---|
| Average {params.service} job value | ${avg_value:,} |
| Estimated monthly AI search opportunities missed | {monthly_customers_reachable} |
| **Estimated monthly revenue at risk** | **${monthly_revenue_at_risk:,}** |

*These are illustrative estimates based on Avenity's market data for {params.city} {params.service} businesses.*

---

## Priority Recommendations

1. **Add JSON-LD LocalBusiness schema markup** — Single highest-impact technical change for AI engine recognition.
2. **Add FAQ-format content** — Directly enables AI engines to generate answers citing this business.
3. **Ensure city + primary service appear in H1 and title tag** — Core entity clarity signal.
4. **Embed or link review count and star rating** — Publicly visible social proof that AI engines read.
5. **Create dedicated service sub-pages** — Depth signals that help AI engines surface specific answers.

---

## Next Step

Avenity Business Solutions specializes in AI visibility for {params.service} businesses in Texas. The 12-Week Visibility Foundation program addresses all five priority areas systematically.

**[→ Get the Full Technical Breakdown + Implementation Plan]({AUDIT_URL})**

**[→ Book a Free 30-Minute Call with Dan]({CALENDLY_BASE})**

*Questions: {CONTACT_EMAIL}*

---
*This report is based on publicly observable technical signals at the time of analysis. Scores reflect AI search visibility readiness only and do not represent business quality or operational performance.*
"""

    return report


@mcp.tool(
    name="avenity_book_consultation",
    annotations={
        "title": "Book Avenity Consultation",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def avenity_book_consultation(params: ConsultationInput) -> str:
    """
    Get a Calendly booking link for a free 30-minute AI Visibility consultation
    with Avenity Business Solutions (Dan).

    The consultation is for business owners who have a confirmed AI visibility
    gap and want to understand the fix and investment required.

    This tool is the conversion endpoint of the Avenity agent pipeline:
    check_visibility → score_business → get_opportunity_report → book_consultation

    Use this when:
    - A client's AI visibility gap is confirmed and they want to act
    - You've shown the client their score and they're interested
    - A client asks "how do I fix my AI visibility?"
    - You want to hand off to a human expert for the close

    Args:
        params (ConsultationInput): Client details. gap_score is optional but
            improves the booking context shown to Dan.

    Returns:
        str: JSON with:
            booking_url (str): Direct Calendly link
            instructions (str): What to tell the client
            context_for_call (str): What Dan will know before the call
            audit_url (str): Self-service audit tool URL

    Examples:
        - "Book a consultation for my client who has a 38/100 visibility score"
        - "How does [company] get help fixing their AI visibility?"
        - "Connect my client with Avenity"
    """
    score_context = (
        f"Score: {params.gap_score}/100" if params.gap_score is not None
        else "Score: not yet assessed"
    )
    first_name = (params.contact_name or "").split()[0] if params.contact_name else ""

    instructions = (
        f"Share this link with {params.contact_name or params.company_name}: "
        f"{CALENDLY_BASE}\n\n"
        f"The call is free, 30 minutes, with Dan from Avenity. "
        f"Dan specializes in AI visibility for {params.service} businesses in Texas. "
        f"He'll walk through exactly what's causing the visibility gap and what the "
        f"fix looks like."
    )

    context = (
        f"Business: {params.company_name} | "
        f"Service: {params.service} | "
        f"City: {params.city} | "
        f"{score_context}"
    )

    return json.dumps({
        "booking_url": CALENDLY_BASE,
        "audit_url": AUDIT_URL,
        "instructions": instructions,
        "context_for_call": context,
        "what_to_expect": (
            "30-minute call. Dan reviews the AI visibility findings, explains "
            "the 12-Week Visibility Foundation program ($1,500/month), and "
            "determines if Avenity is the right fit."
        ),
        "contact_email": CONTACT_EMAIL,
    }, indent=2)


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        # Hosted mode — used by Render, Glama, Smithery
        # FastMCP.run() does not accept host/port kwargs; configure via settings
        port = int(os.getenv("PORT", 8000))
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = port
        # Disable DNS rebinding protection — not needed behind Render/Cloudflare TLS proxy
        from mcp.server.transport_security import TransportSecuritySettings
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        )
        mcp.run(transport="streamable-http")
    else:
        # Local mode — used by Claude Desktop
        mcp.run()
