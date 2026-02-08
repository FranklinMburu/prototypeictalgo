#!/bin/bash
# Credential Verification Script
# Usage: bash scripts/security/verify-no-secrets.sh
# Purpose: Scan repository for accidentally exposed credentials

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔐 Credential Security Verification"
echo "===================================="
echo ""

# Patterns to search for
declare -A PATTERNS=(
    ["Google API Key"]="AIzaSy[A-Za-z0-9_-]"
    ["OpenAI Key"]="sk-[A-Za-z0-9]"
    ["Telegram Bot Token"]="[0-9]{10}:AA[A-Za-z0-9]"
    ["AWS Access Key"]="AKIA[0-9A-Z]{16}"
    ["GitHub Token"]="ghp_[A-Za-z0-9]"
    ["Hardcoded Secret"]="(secret|password|api_key|token)\\s*=\\s*['\"][^'\"]{20,}['\"]"
)

VIOLATIONS=0

echo "📋 Checking current repository..."
echo ""

# Check git history
echo "1️⃣  Git History Scan:"
for desc in "${!PATTERNS[@]}"; do
    PATTERN="${PATTERNS[$desc]}"
    
    # Search in git history
    if git log -p --all --regexp-ignore-case -S "$PATTERN" --diff-filter=M 2>/dev/null | \
       grep -iE "$PATTERN" | grep -v "example\|demo\|test" > /dev/null; then
        echo -e "   ${RED}❌ FOUND: $desc in git history${NC}"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
done

if [ $VIOLATIONS -eq 0 ]; then
    echo -e "   ${GREEN}✓ No credentials found in git history${NC}"
fi
echo ""

# Check .env file
echo "2️⃣  .env File Check:"
if [ -f .env ]; then
    if grep -qE "(AIzaSy|sk-|^[0-9]{10}:AA)" .env; then
        echo -e "   ${YELLOW}⚠️  .env contains credentials (expected for local development)${NC}"
        echo "   ✓ Ensure .env is in .gitignore"
    fi
else
    echo -e "   ${YELLOW}ℹ️  .env file not found (expected if not set up locally)${NC}"
fi

if git check-ignore .env > /dev/null 2>&1; then
    echo -e "   ${GREEN}✓ .env is properly in .gitignore${NC}"
else
    echo -e "   ${RED}❌ .env is NOT in .gitignore (CRITICAL)${NC}"
    VIOLATIONS=$((VIOLATIONS + 1))
fi
echo ""

# Check .example files
echo "3️⃣  Documentation Files (.example):"
EXAMPLE_FILES=$(find . -name "*.example" -o -name "*.sample" | head -20)
for file in $EXAMPLE_FILES; do
    if grep -iE "(AIzaSy|sk-[A-Za-z0-9]{40}|^[0-9]{10}:AA)" "$file" | grep -v "PLACEHOLDER\|_HERE\|<" > /dev/null; then
        echo -e "   ${RED}❌ Credentials in: $file${NC}"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
done
if [ $VIOLATIONS -eq 0 ]; then
    echo -e "   ${GREEN}✓ No real credentials in .example files${NC}"
fi
echo ""

# Check staged files (about to commit)
echo "4️⃣  Staged Changes Check:"
STAGED=$(git diff --cached 2>/dev/null)
if echo "$STAGED" | grep -iE "(AIzaSy|sk-|^[0-9]{10}:AA)" > /dev/null; then
    echo -e "   ${RED}❌ Credentials detected in staged changes!${NC}"
    VIOLATIONS=$((VIOLATIONS + 1))
else
    echo -e "   ${GREEN}✓ No credentials in staged changes${NC}"
fi
echo ""

# Check .gitignore
echo "5️⃣  .gitignore Configuration:"
IGNORED_PATTERNS=(
    ".env"
    ".env.local"
    "secrets/"
    "*.key"
    "*.pem"
)

for pattern in "${IGNORED_PATTERNS[@]}"; do
    if grep -q "^$pattern" .gitignore 2>/dev/null; then
        echo -e "   ${GREEN}✓ $pattern is ignored${NC}"
    else
        echo -e "   ${YELLOW}⚠️  $pattern may not be ignored${NC}"
    fi
done
echo ""

# Check pre-commit hook
echo "6️⃣  Pre-commit Hook:"
if [ -x .git/hooks/pre-commit ]; then
    echo -e "   ${GREEN}✓ Pre-commit hook is installed${NC}"
else
    echo -e "   ${YELLOW}⚠️  Pre-commit hook not installed${NC}"
fi
echo ""

# Results
echo "===================================="
if [ $VIOLATIONS -eq 0 ]; then
    echo -e "${GREEN}✅ SECURITY CHECK PASSED${NC}"
    echo "   No exposed credentials detected!"
    exit 0
else
    echo -e "${RED}❌ SECURITY CHECK FAILED${NC}"
    echo "   $VIOLATIONS violation(s) found"
    echo ""
    echo "   Actions:"
    echo "   1. Review findings above"
    echo "   2. Remove/rotate compromised credentials"
    echo "   3. Update git history if needed"
    echo "   4. Run this script again to verify"
    exit 1
fi
