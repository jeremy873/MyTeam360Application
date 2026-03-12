# MyTeam360 — Conceptual Test Plan

**Version:** 1.0
**Date:** March 3, 2026
**Mode:** No API keys required (mock/browser-fallback mode)

---

## Prerequisites

Before you start, run these commands in your terminal:

```bash
cd myteam360
pip install flask cryptography qrcode requests --break-system-packages
rm -f data/myteam360.db data/initial_credentials.txt data/.encryption_key
ANTHROPIC_API_KEY=test python3 app.py
```

The `ANTHROPIC_API_KEY=test` is a dummy — it lets the server boot without a real key. Chat responses will return errors from the AI provider, but everything else works. Keep this terminal open.

Open a second terminal for running test commands. All `curl` commands below assume the server is at `http://127.0.0.1:5000`.

### Step 0: Get Your Token

```bash
# Login
TOKEN=$(curl -s -X POST http://127.0.0.1:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@localhost","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")

echo "Token: $TOKEN"

# Accept the Acceptable Use Policy
POLICY_ID=$(curl -s http://127.0.0.1:5000/api/policy/check \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('policy_id',''))")

curl -s -X POST http://127.0.0.1:5000/api/policy/accept \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"policy_id\":\"$POLICY_ID\"}"

# Run the setup wizard (creates 8 departments + 18 agents)
curl -s -X POST http://127.0.0.1:5000/api/setup/complete \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Created {len(d.get(\"departments_created\",[]))} departments, {len(d.get(\"agents_created\",[]))} agents')"
```

Save the TOKEN — you'll use it in every command below as `-H "Authorization: Bearer $TOKEN"`.

---

## Part 1: Demo Walkthrough (Does It Feel Right?)

The goal here is to experience the platform like a first-time user would. Go through each flow and ask yourself: does this make sense? Is anything confusing? What's missing?

### 1.1 First Impressions

Open `http://127.0.0.1:5000` in your browser. Note:

- [ ] Does the login page load cleanly?
- [ ] Does login with `admin@localhost` / `admin123` work?
- [ ] Does the AUP acceptance flow appear?
- [ ] After accepting, does the main dashboard load?

### 1.2 Agent Discovery

```bash
# List all agents
curl -s http://127.0.0.1:5000/api/agents \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -50
```

- [ ] Do 18 agents appear across 8 departments?
- [ ] Does each agent have a name, description, and model assigned?
- [ ] Do the department groupings make sense (Sales, Marketing, Legal, etc.)?

### 1.3 Agent Voice Personalities

```bash
# Check voices on first 5 agents
for AGENT_ID in $(curl -s http://127.0.0.1:5000/api/agents \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json
agents = json.load(sys.stdin).get('agents',[])
for a in agents[:5]:
    print(a['id'])
"); do
  echo "---"
  curl -s "http://127.0.0.1:5000/api/agents/$AGENT_ID/voice" \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
done
```

- [ ] Do different agents have different voices (onyx, echo, shimmer, nova, etc.)?
- [ ] Do voice speeds vary (legal agents slower, sales agents faster)?
- [ ] Does the voice assignment match the agent personality?

### 1.4 Voice Chat UI

Open `http://127.0.0.1:5000/voice-chat` (or `http://127.0.0.1:5000/voice-chat?token=YOUR_TOKEN`).

- [ ] Does the dark atmosphere with purple orb render?
- [ ] Does the agent dropdown populate with your 18 agents?
- [ ] Does tapping the orb trigger a mic permission prompt?
- [ ] If you grant mic access, does the orb animate (pulse, rings)?
- [ ] Does the settings panel slide out when you tap the gear icon?
- [ ] Are TTS provider options listed (Browser, OpenAI, ElevenLabs, Google)?

Note: Without real API keys, voice responses will use browser-native TTS. The orb should still transition between states (listening → thinking → speaking → listening).

### 1.5 Department Structure

```bash
curl -s http://127.0.0.1:5000/api/departments \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

- [ ] 8 departments: C-Suite, Sales, Marketing, Finance, Legal, HR, IT, Operations?
- [ ] Each has an icon and description?

### 1.6 Branding

```bash
# View current branding
curl -s http://127.0.0.1:5000/api/branding \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Change it
curl -s -X PUT http://127.0.0.1:5000/api/branding \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"org_name":"MV Transportation","primary_color":"#0066CC","tagline":"Smart Transit Operations"}'

# View the CSS variables it generates
curl -s http://127.0.0.1:5000/api/branding/css \
  -H "Authorization: Bearer $TOKEN"
```

- [ ] Does branding update persist?
- [ ] Does the CSS output contain your custom colors?
- [ ] Does reset restore defaults?

---

## Part 2: Stress Testing (What Breaks?)

### 2.1 Auth Edge Cases

```bash
# Wrong password (should fail)
curl -s -X POST http://127.0.0.1:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@localhost","password":"wrong"}'

# Missing fields
curl -s -X POST http://127.0.0.1:5000/api/auth/login \
  -H "Content-Type: application/json" -d '{}'

# Empty body
curl -s -X POST http://127.0.0.1:5000/api/auth/login

# SQL injection attempt in email
curl -s -X POST http://127.0.0.1:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@localhost\" OR 1=1 --","password":"x"}'
```

- [ ] Wrong password returns clear error, not a stack trace?
- [ ] Missing fields don't crash the server?
- [ ] SQL injection attempt is handled safely?

### 2.2 Account Lockout

```bash
# Hit the login 6 times with wrong password
for i in {1..6}; do
  echo "Attempt $i:"
  curl -s -X POST http://127.0.0.1:5000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@localhost","password":"wrong"}'
  echo ""
done

# Check lockout status
curl -s http://127.0.0.1:5000/api/security/lockout/admin@localhost \
  -H "Authorization: Bearer $TOKEN"

# Clear it (admin action)
curl -s -X POST http://127.0.0.1:5000/api/security/lockout/admin@localhost/clear \
  -H "Authorization: Bearer $TOKEN"
```

- [ ] After 5 failures, does lockout engage?
- [ ] Does lockout status show remaining time?
- [ ] Can admin clear the lockout?

### 2.3 DLP — Sensitive Data Blocking

```bash
# SSN (should BLOCK)
curl -s -X POST http://127.0.0.1:5000/api/security/dlp/scan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"My social security number is 123-45-6789"}'

# Credit card (should BLOCK)
curl -s -X POST http://127.0.0.1:5000/api/security/dlp/scan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Pay with 4111-1111-1111-1111"}'

# API key (should WARN)
curl -s -X POST http://127.0.0.1:5000/api/security/dlp/scan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Use key sk-ant-abcdefghijklmnop123456"}'

# AWS key (should BLOCK)
curl -s -X POST http://127.0.0.1:5000/api/security/dlp/scan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"AWS key: AKIAIOSFODNN7EXAMPLE"}'

# Clean text (should ALLOW)
curl -s -X POST http://127.0.0.1:5000/api/security/dlp/scan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Please schedule a meeting for Tuesday at 3pm"}'

# EDGE CASE: 9-digit number that looks like SSN but isn't
curl -s -X POST http://127.0.0.1:5000/api/security/dlp/scan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Our revenue was 123-45-6789 dollars last quarter"}'

# Test that DLP actually blocks chat (should return 422)
curl -s -X POST http://127.0.0.1:5000/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"My SSN is 123-45-6789"}'
```

- [ ] SSN and credit card return `"action": "block"`?
- [ ] API key returns `"action": "warn"`?
- [ ] Clean text returns `"action": "allow"`?
- [ ] The revenue edge case — does it false-positive? (Note this for improvement)
- [ ] Chat with SSN returns 422 with `dlp_blocked` error?

### 2.4 Password Policy

```bash
# Validate various passwords
for PW in "abc" "password123" "Short1!" "NoSpecialChar123" "Str0ng!Pass#2024" "aaaaaaaaaa1A!"; do
  echo "Testing: $PW"
  curl -s -X POST http://127.0.0.1:5000/api/security/validate-password \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"password\":\"$PW\"}"
  echo -e "\n"
done
```

- [ ] "abc" fails (too short, missing uppercase, digit, special)?
- [ ] "password123" fails (common password)?
- [ ] "Short1!" fails (too short)?
- [ ] "Str0ng!Pass#2024" passes?

### 2.5 Malformed Input Stress

```bash
# Huge payload
python3 -c "import requests; r=requests.post('http://127.0.0.1:5000/api/chat', headers={'Authorization':'Bearer $TOKEN','Content-Type':'application/json'}, json={'message':'A'*100000}); print(r.status_code, r.text[:200])"

# Wrong content type
curl -s -X POST http://127.0.0.1:5000/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: text/plain" \
  -d 'just plain text'

# Unicode/emoji flood
curl -s -X POST http://127.0.0.1:5000/api/security/dlp/scan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"🔥🔥🔥🎉🎊💯🚀 Hello 世界 مرحبا Привет"}'

# Expired/fake token
curl -s http://127.0.0.1:5000/api/agents \
  -H "Authorization: Bearer faketoken12345"

# No auth header at all
curl -s http://127.0.0.1:5000/api/agents
```

- [ ] Huge payload doesn't crash the server?
- [ ] Wrong content type returns a clean error?
- [ ] Unicode doesn't cause encoding errors?
- [ ] Fake token returns 401, not a stack trace?
- [ ] Missing auth returns 401?

### 2.6 Rapid-Fire Requests

```bash
# Hit the same endpoint 50 times quickly
python3 -c "
import requests, time, threading
url = 'http://127.0.0.1:5000/api/agents'
headers = {'Authorization': 'Bearer $TOKEN'}
results = []
def hit():
    try:
        r = requests.get(url, headers=headers, timeout=5)
        results.append(r.status_code)
    except Exception as e:
        results.append(str(e))

threads = [threading.Thread(target=hit) for _ in range(50)]
start = time.time()
for t in threads: t.start()
for t in threads: t.join()
elapsed = time.time() - start

ok = results.count(200)
rate_limited = results.count(429)
errors = len(results) - ok - rate_limited
print(f'{ok} OK, {rate_limited} rate-limited, {errors} errors in {elapsed:.2f}s')
"
```

- [ ] Does the server handle all 50 without crashing?
- [ ] Are some rate-limited (429)?
- [ ] No database lock errors?

---

## Part 3: Feature Validation (Every Feature Works)

### 3.1 Conversation Export

```bash
# Create a conversation
CONV_ID=$(curl -s -X POST http://127.0.0.1:5000/api/conversations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Export Test"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('conversation',{}).get('id',''))")

echo "Conversation: $CONV_ID"

# Export in each format
echo "--- CSV ---"
curl -s "http://127.0.0.1:5000/api/conversations/$CONV_ID/export/csv" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -10

echo "--- Markdown ---"
curl -s "http://127.0.0.1:5000/api/conversations/$CONV_ID/export/markdown" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -10

echo "--- JSON ---"
curl -s "http://127.0.0.1:5000/api/conversations/$CONV_ID/export/json" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -10

echo "--- Bulk Export ---"
curl -s "http://127.0.0.1:5000/api/conversations/export-all" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -10
```

- [ ] CSV export returns structured data?
- [ ] Markdown returns readable format?
- [ ] JSON returns complete conversation object?
- [ ] Bulk export includes all conversations?

### 3.2 Prompt Template Lifecycle

```bash
# Create
TMPL_ID=$(curl -s -X POST http://127.0.0.1:5000/api/templates \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Client Follow-Up",
    "category": "sales",
    "description": "Follow-up email after a client meeting",
    "content": "Write a follow-up email to {{client_name}} at {{company}} about our discussion on {{topic}}. Tone should be {{tone}}.",
    "variables": ["client_name", "company", "topic", "tone"],
    "is_shared": true
  }' | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))")

echo "Template: $TMPL_ID"

# List all templates
curl -s http://127.0.0.1:5000/api/templates \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -20

# Use it with variables
curl -s -X POST "http://127.0.0.1:5000/api/templates/$TMPL_ID/use" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "variables": {
      "client_name": "Sarah",
      "company": "TechCorp",
      "topic": "fleet automation",
      "tone": "professional but warm"
    }
  }'

# Update
curl -s -X PUT "http://127.0.0.1:5000/api/templates/$TMPL_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Client Follow-Up v2", "description": "Updated version"}'

# Categories
curl -s http://127.0.0.1:5000/api/templates/categories \
  -H "Authorization: Bearer $TOKEN"

# Delete
curl -s -X DELETE "http://127.0.0.1:5000/api/templates/$TMPL_ID" \
  -H "Authorization: Bearer $TOKEN"
```

- [ ] Template created with all variables?
- [ ] `use` endpoint replaces `{{variables}}` correctly?
- [ ] Update changes the name?
- [ ] Delete removes it?

### 3.3 Usage Quotas

```bash
# Set org-wide quota
curl -s -X PUT http://127.0.0.1:5000/api/quotas \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"org_monthly_tokens": 10000000, "org_monthly_cost": 500.00}'

# Set per-user quota
curl -s -X PUT http://127.0.0.1:5000/api/quotas/user/admin@localhost \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"monthly_tokens": 1000000, "monthly_cost": 50.00}'

# Check your quota status
curl -s http://127.0.0.1:5000/api/quotas/check \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Get org usage report
curl -s "http://127.0.0.1:5000/api/quotas/usage?scope=org" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

- [ ] Quotas set and return updated values?
- [ ] Check shows `allowed: true` with 0 usage?
- [ ] Usage report shows the period and quota limits?

### 3.4 MFA Setup Flow

```bash
# Check status (should be not enabled)
curl -s http://127.0.0.1:5000/api/security/mfa/status \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Start setup (returns secret + QR code)
curl -s -X POST http://127.0.0.1:5000/api/security/mfa/setup \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Secret: {d.get(\"secret\",\"?\")[:8]}...')
print(f'Has QR: {\"qr_code\" in d}')
print(f'Provisioning URI: {d.get(\"provisioning_uri\",\"?\")[:50]}...')
"

# Try verifying with wrong code
curl -s -X POST http://127.0.0.1:5000/api/security/mfa/verify-setup \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"code": "000000"}'

# Disable MFA
curl -s -X POST http://127.0.0.1:5000/api/security/mfa/disable \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{}'
```

- [ ] Status shows not enabled?
- [ ] Setup returns a secret and QR code (base64 PNG)?
- [ ] Wrong code returns `verified: false`?
- [ ] The provisioning URI starts with `otpauth://totp/`?

### 3.5 Encryption

```bash
# Check encryption status
curl -s http://127.0.0.1:5000/api/security/encryption/status \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Rotate the encryption key
curl -s -X POST http://127.0.0.1:5000/api/security/encryption/rotate \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Verify the .encryption_key file exists with restricted permissions
ls -la data/.encryption_key
```

- [ ] Encryption is active?
- [ ] Key rotation succeeds?
- [ ] Key file has 600 permissions (owner read/write only)?

### 3.6 Security Dashboard

```bash
curl -s http://127.0.0.1:5000/api/security/dashboard \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

- [ ] Shows password policy settings?
- [ ] Shows session policy?
- [ ] Shows MFA coverage percentage?
- [ ] Shows DLP detections in last 24 hours?
- [ ] Shows encryption status?

### 3.7 Recommendations Engine

```bash
# Generate recommendations
curl -s -X POST http://127.0.0.1:5000/api/recommendations/generate \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Get summary
curl -s http://127.0.0.1:5000/api/recommendations/summary \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

- [ ] Recommendations generate (may be empty with fresh data — that's expected)?
- [ ] Summary returns category counts?

### 3.8 Voice Chat API

```bash
# List providers
curl -s http://127.0.0.1:5000/api/voice/providers \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Get/set voice settings
curl -s http://127.0.0.1:5000/api/voice/settings \
  -H "Authorization: Bearer $TOKEN"

curl -s -X PUT http://127.0.0.1:5000/api/voice/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tts_provider":"browser","tts_speed":1.2,"stt_language":"en-US"}'

# Test TTS synthesis (will use browser fallback)
curl -s -X POST http://127.0.0.1:5000/api/voice/synthesize \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello, this is a test of the voice synthesis system."}'

# Start and end a voice session
SESSION_ID=$(curl -s -X POST http://127.0.0.1:5000/api/voice/session/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tts_provider":"browser"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))")

curl -s -X POST "http://127.0.0.1:5000/api/voice/session/$SESSION_ID/exchange" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stt_text":"What is our Q3 revenue?","tts_text":"Based on the latest reports, Q3 revenue was 2.4 million."}'

curl -s -X POST "http://127.0.0.1:5000/api/voice/session/$SESSION_ID/end" \
  -H "Authorization: Bearer $TOKEN"
```

- [ ] 4 providers listed (browser, openai, elevenlabs, google)?
- [ ] Settings save and return updated values?
- [ ] Synthesis returns with `provider: browser` (fallback)?
- [ ] Session lifecycle (start → exchange → end) completes?

---

## Part 4: Validation Walkthrough (The Chris Pitch)

If you were demoing this to Chris or a potential customer, here's the story you'd tell. Walk through it and see if it flows.

### The Pitch Script

**"Let me show you MyTeam360."**

1. **Login & Setup** — Show the first-run experience. Login, accept the AUP, run the setup wizard. "In 30 seconds, we've created 8 departments and 18 specialized AI agents."

2. **Agent Roster** — Pull up the agents list. "Every department has purpose-built agents. Sales has a Proposal Writer, Legal has a Contract Reviewer, Finance has a Budget Planner. Each one has its own AI model, temperature, and even voice."

3. **Voice Chat** — Open the voice chat page. "Users can talk to any agent by voice. The Sales Assistant sounds energetic, the Legal Advisor sounds deliberate. It's like having a real team."

4. **Security** — Show the security dashboard. "We have enterprise-grade security out of the box: encrypted API keys, MFA, password policies with breach detection, and DLP that blocks SSNs and credit cards from ever reaching the AI."

5. **DLP Demo** — Scan a message with an SSN. "Watch this — if someone accidentally pastes sensitive data, it's caught and blocked before it ever leaves the organization."

6. **Quotas** — Show the quota system. "Admins can set spending limits per user, per department, or org-wide. No surprise bills."

7. **Branding** — Change the org name and colors. "Everything white-labels. Your logo, your colors, your name."

8. **Templates** — Create and use a prompt template. "Teams can share reusable prompts. Fill in the variables, get consistent output every time."

9. **Analytics** — Show recommendations. "The platform watches usage patterns and proactively suggests optimizations — like switching an expensive model when a cheaper one would work."

10. **Export** — Export a conversation. "Full compliance support. Conversations export to CSV, JSON, or Markdown for auditors."

### Pitch Checklist

- [ ] Can you complete the full walkthrough in under 5 minutes?
- [ ] Does each step flow naturally into the next?
- [ ] Are there any points where you'd lose the audience?
- [ ] What questions would Chris ask that you can't answer yet?
- [ ] What would make a customer say "I need this"?

---

## Part 5: Known Limitations to Document

As you test, keep a running list. Here are the ones we already know:

| Area | Limitation | Impact |
|------|-----------|--------|
| Chat | No real AI responses without API key | Can't demo actual conversations |
| Voice | Browser TTS only without API keys | Voice quality is basic |
| DLP | Pattern-based, catches formats not context | False positives on 9-digit numbers |
| MFA | No backup codes or recovery flow | Locked out users need admin intervention |
| Frontend | Single HTML file, no SPA framework | Hard to extend the UI |
| Database | SQLite, no concurrent write safety | Not production-ready |
| Sessions | In-memory only, lost on restart | Restarting server logs everyone out |
| Encryption | Key rotation has no rollback | Interrupted rotation could corrupt data |
| Tests | Ad-hoc curl commands, no automated suite | Regressions could slip through |

### Bug Tracker

Use this format as you find issues:

```
BUG-001: [Feature] Short description
  Steps: What you did
  Expected: What should happen
  Actual: What happened
  Severity: Critical / High / Medium / Low
```

---

## Summary

| Test Area | Commands | What You're Validating |
|-----------|----------|----------------------|
| Demo (Part 1) | 6 sections | UI feel, flow, first impressions |
| Stress (Part 2) | 6 sections | Auth, DLP, passwords, bad input, load |
| Features (Part 3) | 8 sections | Every feature works end-to-end |
| Pitch (Part 4) | 10-step walkthrough | Can you sell this in 5 minutes? |
| Known Issues (Part 5) | Reference list | What to be honest about |

Total estimated time: 45-60 minutes for a thorough pass.

Good luck — and document everything you find.
