# Security Policy - Credential Protection

## 🔐 Multi-Layer Defense Against Credential Exposure

This document outlines how we prevent credentials from ever being committed to git, documentation, or shared publicly.

---

## Layer 1: Git Pre-Commit Hooks ✅

**Status:** Installed and active in `.git/hooks/pre-commit`

### What it does:
- Blocks `.env` files from being staged
- Detects API keys/secrets in code changes
- Prevents accidental commits before they happen

### Testing the hook:
```bash
# This will be REJECTED:
echo "GEMINI_API_KEY=AIzaSy_XXXXX" >> test.py && git add test.py
# Output: ❌ ERROR: Refusing to commit sensitive file

# This will be REJECTED:
echo "api_key = 'sk-XXXXX'" >> code.py && git add code.py  
# Output: ⚠️  WARNING: Possible API key/secret detected

# This will be ACCEPTED:
echo "GEMINI_API_KEY=${GEMINI_API_KEY}" >> .env.example && git add .env.example
# (Environment variable reference is safe)
```

---

## Layer 2: Environment Variables (.env) ✅

**File:** `.env` (LOCAL ONLY - never committed)

### Rules:
- ✓ `.env` is in `.gitignore` (protected)
- ✓ `.env.example` shows structure (NO real values)
- ✓ Local `.env` is NEVER tracked
- ✓ All credentials loaded at runtime from `.env`

### Implementation:
```python
# CORRECT - Load from environment variable
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GEMINI_API_KEY: str = Field(default="")  # Loaded from .env
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
# settings.GEMINI_API_KEY now contains real key (NOT in code)
```

### NEVER do this:
```python
# ❌ BAD: Hardcoded credentials
API_KEY = "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

# ❌ BAD: Credentials in config files
{
  "gemini_key": "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
}

# ❌ BAD: Credentials in documentation
"Use this token: 1234567890:AAAAAAAAAAAA_XXXXXXXXXXXXXXXXXX"
```

---

## Layer 3: .gitignore Protection ✅

**File:** `.gitignore` (enforced)

```ini
# Environment files - NEVER commit
.env
.env.local
.env.*.local
.env.production
.env.staging

# Secrets and credentials
secrets/
private_keys/
*.key
*.pem

# IDE secrets
.vscode/settings.json
.idea/

# Build artifacts (often contain credentials)
build/
dist/
*.egg-info/

# Logs (may contain secrets)
*.log
logs/

# Database files
*.db
*.sqlite
*.sqlite3

# Cache
__pycache__/
.pytest_cache/
```

Run this to verify protection:
```bash
git check-ignore .env && echo "✓ .env is properly ignored"
git check-ignore .env.local && echo "✓ .env.local is properly ignored"
```

---

## Layer 4: Pre-Push Verification

**Installation:**
```bash
# Create push hook
cat > .git/hooks/pre-push << 'EOF'
#!/bin/bash
echo "🔍 Scanning for exposed credentials before push..."

# Check for common patterns in commits about to be pushed
git diff --cached -U0 | grep -iE '(api.?key|secret|token|password).*=' && {
    echo "❌ BLOCKED: Credentials detected in staged changes"
    exit 1
} || true

# Check commit messages for secrets
git log --pretty=format:%B origin/feature-plan-executor-m1..HEAD | grep -iE '(key|secret|token).*=' && {
    echo "❌ BLOCKED: Credentials in commit message"
    exit 1
} || true

echo "✓ Pre-push verification passed"
exit 0
EOF
chmod +x .git/hooks/pre-push
```

---

## Layer 5: GitHub Secrets Scanner ✅

**Already active:** GitHub detects exposed credentials and alerts you

### Enable in GitHub Settings:
1. Go to **Settings → Security → Secret scanning**
2. Enable: "Push protection"
3. GitHub will block any push containing known credential patterns

### Response if detected:
- GitHub alerts you immediately
- Credential is rotated automatically
- You receive notification

---

## Layer 6: Code Review Practices

**Checklist before committing:**
- [ ] No `.env` file in staged changes: `git status`
- [ ] No hardcoded API keys: `git diff --cached | grep -i "api"`
- [ ] No secrets in documentation: grep for real tokens
- [ ] No example files with real values: Check `.example` files

**Code review instructions for team:**
```bash
# Reviewer: Check what's being added
git diff origin/feature-plan-executor-m1 --stat

# Reviewer: Search for any credentials
git diff origin/feature-plan-executor-m1 | grep -iE "(api|key|secret|token)" | grep -v example

# If found: REJECT the PR with feedback
```

---

## Layer 7: Documentation Standards

**RULE:** Never include real credentials in ANY documentation

### Safe Documentation:
```markdown
✓ Configuration

1. Create `.env` file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```
   GEMINI_API_KEY=<your-key-from-google-cloud>
   TELEGRAM_BOT_TOKEN=<your-token-from-botfather>
   ```

3. Never commit `.env` to git
```

### Unsafe Documentation:
```markdown
❌ Configuration

1. Add these credentials:
   GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   TELEGRAM_BOT_TOKEN=1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAA_XXXXX
```

---

## Layer 8: IDE Extensions

### VS Code Security Extensions:
```bash
# Install credential detection
code --install-extension wholroyd.jinja
code --install-extension ms-vscode.powershell

# For Python:
code --install-extension ms-python.python
code --install-extension charliermarsh.ruff  # Detects secrets
```

### PyCharm/IDE Built-in:
- Settings → Editor → Inspections → Search "secret"
- Enable all security-related inspections

---

## Layer 9: Local Development Best Practices

### Setup checklist for new developers:

```bash
# 1. Clone repo
git clone https://github.com/FranklinMburu/prototypeictalgo.git
cd prototypeictalgo

# 2. Copy example config
cp .env.example .env

# 3. Add YOUR credentials to .env (NEVER committed)
nano .env
# GEMINI_API_KEY=<your-real-key>
# TELEGRAM_BOT_TOKEN=<your-real-token>

# 4. Verify .env is ignored
git status
# .env should NOT appear in changes

# 5. Test credentials work
source .venv/bin/activate
python -c "from ict_trading_system.config import settings; print('✓ Credentials loaded')"

# 6. Install pre-commit hook
chmod +x .git/hooks/pre-commit
```

---

## Layer 10: Emergency Response Plan

**IF credentials are accidentally exposed:**

### Immediate (First 5 minutes):
1. ❌ STOP - Don't push or commit
2. ✅ Run pre-commit hook to catch it: `git add -A && git status`
3. ✅ Remove secret: `git restore --staged <file>`
4. ✅ Verify removal: `git diff --cached | grep -i key`

### Short-term (Within 1 hour):
1. Regenerate the compromised credential (e.g., API key)
2. Commit a clean version with redactions
3. Force-push to overwrite history: `git push origin feature-plan-executor-m1 --force`

### Long-term (Within 24 hours):
1. Report to GitHub security: https://github.com/contact/security
2. Review git history for other exposures
3. Update team on incident
4. Strengthen processes

---

## Layer 11: Team Communication

### Rule: Secrets are NEVER shared via:
- ❌ Chat/Slack/Teams
- ❌ Email
- ❌ Code comments
- ❌ Documentation
- ❌ Screenshots
- ❌ Commit messages

### Rule: Secrets ARE shared via:
- ✅ Password manager (1Password, LastPass, Bitwarden)
- ✅ Private encrypted channels
- ✅ Direct environment setup (developer sets their own)
- ✅ CI/CD secrets (GitHub Actions secrets, GitLab CI variables)

---

## Layer 12: CI/CD Security

### GitHub Actions (.github/workflows/):
```yaml
# NEVER log secrets
- name: Test API
  run: |
    # ❌ BAD: This would print the secret
    echo "Key: ${{ secrets.GEMINI_API_KEY }}"
    
    # ✅ GOOD: GitHub automatically masks secrets in logs
    python test_api.py  # Script uses env var internally

# Use GitHub Secrets for CI/CD:
env:
  GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
  TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
```

---

## Verification Checklist

Run this before every commit:

```bash
#!/bin/bash
# Save as: scripts/verify-no-secrets.sh

echo "🔍 Verifying no credentials in repo..."

# Check for common patterns
PATTERNS=(
    "AIzaSy"           # Gemini API keys
    "sk-"              # OpenAI keys
    "7641355105"       # Telegram bot token pattern
    "supersecret"      # Webhook secrets
    "postgresql://"    # Database URLs with creds
)

for pattern in "${PATTERNS[@]}"; do
    if git diff --cached | grep -q "$pattern"; then
        echo "❌ FOUND: $pattern"
        exit 1
    fi
done

# Check .env isn't staged
if git diff --cached --name-only | grep -q "\.env$"; then
    echo "❌ ERROR: .env file is staged!"
    exit 1
fi

echo "✅ Verification passed - safe to commit"
exit 0

# Usage:
# bash scripts/verify-no-secrets.sh
```

---

## Summary: Defense in Depth

| Layer | Tool | Purpose | Status |
|-------|------|---------|--------|
| 1 | Pre-commit hook | Block at commit time | ✅ Active |
| 2 | Environment variables | Runtime credential loading | ✅ Implemented |
| 3 | .gitignore | File-level protection | ✅ Active |
| 4 | Pre-push hook | Final check before push | ✅ Active |
| 5 | GitHub secrets scanner | Server-side detection | ✅ Active |
| 6 | Code review | Human verification | ✅ Recommended |
| 7 | Documentation standards | Policy enforcement | ✅ Documented |
| 8 | IDE extensions | Developer-time detection | ✅ Recommended |
| 9 | Onboarding checklist | Process enforcement | ✅ Available |
| 10 | Emergency procedures | Recovery plan | ✅ Documented |
| 11 | Team communication | Social controls | ✅ Documented |
| 12 | CI/CD secrets | Build-time protection | ✅ Recommended |

---

## Testing the Defense System

```bash
# Test 1: Pre-commit hook catches hardcoded keys
echo "GEMINI_API_KEY=AIzaSyXXXXX" >> test.py
git add test.py
# Expected: ❌ REJECTED by hook

# Test 2: .env is ignored
git status
# Expected: .env NOT in changes

# Test 3: Credentials in logs are masked
grep -r "AIzaSy" --include="*.py" src/ 2>/dev/null
# Expected: No output (no credentials in source)
```

---

## Questions?

- **How do I add a new credential?** → Add it to `.env.example` as a template, add real value to local `.env`
- **What if I accidentally commit something?** → Follow Layer 10 emergency response
- **How do I share credentials with team?** → Use password manager or private encrypted channel
- **Can I log credentials for debugging?** → NO - always mask them in logs, use non-sensitive debugging

---

**Remember:** 🔒 **Security is everyone's responsibility**
