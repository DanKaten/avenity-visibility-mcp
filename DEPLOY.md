# Go Live in 30 Minutes — Deployment Checklist

This is the complete sequence to get the Avenity MCP server live and discoverable by AI agents.

---

## Step 1: Push to GitHub (5 min)

1. Go to github.com → New repository
2. Name it: `avenity-visibility-mcp`
3. Set to **Public** (required for Smithery and Glama indexing)
4. In GitHub Desktop: commit and push this entire `avenity-visibility-mcp/` folder
5. Note your GitHub username — you'll need it below

---

## Step 2: Deploy to Render.com (10 min)

Render gives you a free public HTTPS URL — this is what Glama and Smithery call.

1. Go to [render.com](https://render.com) → Sign up (free)
2. New → Web Service
3. Connect your GitHub repo: `avenity-visibility-mcp`
4. Render auto-detects `render.yaml` — click **Deploy**
5. Wait ~3 min for build to finish
6. Copy your URL: `https://avenity-visibility-mcp.onrender.com`

**Test it works:**
```
curl https://avenity-visibility-mcp.onrender.com/health
```

---

## Step 3: Update the URL in smithery.yaml (2 min)

In `smithery.yaml`, uncomment and update the URL line:
```yaml
server:
  type: http
  url: https://avenity-visibility-mcp.onrender.com/mcp
```

Commit and push the change.

---

## Step 4: Submit to Smithery (5 min)

1. Go to [smithery.ai](https://smithery.ai)
2. Click **Publish** (top nav)
3. Enter your GitHub repo: `yourusername/avenity-visibility-mcp`
4. Smithery reads `smithery.yaml` and auto-creates the listing

---

## Step 5: Submit to Glama (5 min)

Glama is where the AEO/AI visibility agent builders are.

1. Update `glama-connector.json` with your Render URL and GitHub username
2. Go to [glama.ai](https://glama.ai)
3. Sign up with GitHub
4. Navigate to: My Connectors → New Connector
5. Enter your Render URL: `https://avenity-visibility-mcp.onrender.com/mcp`
6. Description: "Check AI search visibility gaps for SMB clients and connect them with Avenity's expert for implementation. Free. No API key."
7. Select categories: Marketing, Search, AI & Machine Learning
8. Submit

Glama will auto-verify within a few minutes.

---

## Step 6: Publish the dev.to article (5 min)

This targets agent builders searching for AI visibility tools.

1. Go to [dev.to](https://dev.to) → Sign up
2. New Post → paste the contents of `devto-article.md`
3. Add tags: `mcp`, `llm`, `claude`, `aiagents`
4. Publish

---

## What happens next

Within 24–48 hours:
- Smithery indexes the server → it appears in searches for "AI visibility", "local business", "marketing"
- Glama indexes it → appears alongside AEO Scanner, ai-visibility-scanner
- dev.to article gets indexed by Bing → appears in AI search citations

When an AI agent (Claude, GPT, etc.) is helping a business client who asks "why am I not in AI search?" — that agent can now discover and call Avenity's tools → gap confirmed → score → **Calendly booking for Dan**.

---

## Cost

- GitHub: Free
- Render.com free tier: Free (server sleeps after 15 min, wakes in ~30s on call)
- Smithery listing: Free
- Glama listing: Free
- dev.to article: Free

**Total: $0**
