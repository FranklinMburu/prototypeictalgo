# RELEASE TAGGING GUIDE

## Overview

This guide covers creating and pushing the `shadow-mode-v1.0` Git tag for the completed 10-phase shadow-mode decision intelligence system with Phase 10.1 semantic hardening.

**Two implementations provided:**
- `tag_release.sh` - Bash shell script
- `tag_release.py` - Python script

Both are functionally equivalent, idempotent, and production-safe.

---

## Features

✅ **Idempotent**: Safe to run multiple times  
✅ **Non-destructive**: No code modifications, no branch changes  
✅ **Comprehensive checks**: Pre-flight validation before execution  
✅ **Clear output**: Colored, formatted status messages  
✅ **Error handling**: Graceful failure with helpful messages  
✅ **Verification**: Confirms tag creation and remote push  
✅ **Confirmation prompts**: Interactive approval before changes (skip with flags)

---

## Quick Start

### Using the Bash Script

```bash
# Make script executable
chmod +x tag_release.sh

# Run the script
./tag_release.sh
```

### Using the Python Script

```bash
# Make script executable
chmod +x tag_release.py

# Run the script
python3 tag_release.py

# Or with options
python3 tag_release.py --dry-run              # See what would happen
python3 tag_release.py --tag-name my-tag      # Custom tag name
python3 tag_release.py --remote upstream      # Push to different remote
```

---

## What Gets Tagged

The tag includes a comprehensive annotated message containing:

- Release name and version
- All 10 phases with descriptions
- Key characteristics (shadow-mode, read-only, immutable, etc.)
- Governance documentation references
- Test status (653/653 passing)
- Production readiness status

---

## Safety Guarantees

### Pre-Flight Checks
✅ Verifies we're in a git repository  
✅ Checks for uncommitted changes (blocks if found)  
✅ Verifies current branch and commit state  
✅ Checks if tag already exists (idempotent handling)  

### Idempotency
- If tag exists locally and on remote: Shows warning and exits (no action)
- If tag exists locally but not on remote: Pushes existing tag
- If tag doesn't exist: Creates and pushes new tag

### No Code Modification
- No files are edited
- No branches are created or modified
- No commits are made
- Only Git metadata (tags) is affected

---

## Workflow

### Normal Workflow (First Time)
```
1. Pre-flight checks ✅
2. Display release info
3. Confirm with user (interactive)
4. Create annotated tag ✅
5. Push tag to remote ✅
6. Verify tag on remote ✅
7. Show completion summary
```

### Idempotent Workflow (Already Tagged)
```
1. Pre-flight checks ✅
2. Display release info
3. Detect tag already exists locally
4. Check if tag is on remote
5. If on remote: Show success message and exit
6. If not on remote: Push existing tag and verify
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (tag created/pushed or already exists) |
| 1 | Error (validation failed or command error) |

---

## Common Scenarios

### Scenario 1: First-Time Tagging

```bash
$ python3 tag_release.py

[Shows pre-flight checks - all pass]
[Shows release information]
Proceed with tagging? (y/n): y

[Creates tag]
[Pushes tag]
[Verifies on remote]
✅ Tag 'shadow-mode-v1.0' has been created and pushed successfully
```

**Result:** Tag created and pushed to remote ✅

### Scenario 2: Tag Already Exists (Idempotent)

```bash
$ python3 tag_release.py

[Shows pre-flight checks - all pass]
⚠️  Tag 'shadow-mode-v1.0' already exists locally
ℹ️  Tag already exists on remote
ℹ️  No action needed - tag is already created and pushed
```

**Result:** No action taken, warning shown ✅

### Scenario 3: Dry-Run (Preview Only)

```bash
$ python3 tag_release.py --dry-run

[Shows all checks and information]
ℹ️  [DRY-RUN] Would run: git tag -a shadow-mode-v1.0 ...
ℹ️  [DRY-RUN] Would run: git push origin shadow-mode-v1.0
```

**Result:** Shows what would happen, no changes made ✅

### Scenario 4: Different Tag Name

```bash
$ python3 tag_release.py --tag-name custom-tag-v1

[Creates tag named 'custom-tag-v1' instead of 'shadow-mode-v1.0']
```

**Result:** Custom tag created and pushed ✅

### Scenario 5: Uncommitted Changes Error

```bash
$ python3 tag_release.py

❌ Uncommitted changes detected. Please commit or stash changes.
```

**Result:** Script exits safely without making changes ✅

---

## Verification Commands

After running the script, verify the release tag:

```bash
# View the tag
git show shadow-mode-v1.0

# List all tags
git tag -l

# Check tag on remote
git ls-remote --tags origin shadow-mode-v1.0

# Clone a specific release
git clone --branch shadow-mode-v1.0 <repo-url>
```

---

## Tag Message Content

The tag includes:

**Title:**
```
Release: Shadow-Mode Decision Intelligence System v1.0
```

**Sections:**
1. Completion statement (10-phase system)
2. All phases listed with descriptions
3. Key characteristics (shadow-mode, read-only, etc.)
4. Governance references
5. Test status
6. Production readiness

**Example:**
```
Release: Shadow-Mode Decision Intelligence System v1.0

Completion: 10-phase shadow-mode decision intelligence system 
with Phase 10.1 semantic hardening

Phases Included:
- Phase 1: Reasoning Manager (multi-round LLM collaboration)
- Phase 2: Reasoning Manager Integration (signal intelligence extraction)
...
[10 total phases]

Key Characteristics:
✅ Completely shadow-mode (zero authority, zero enforcement)
✅ Read-only analysis...
...

Governance:
- AUTHORITY_BOUNDARY.md
- PHASE_10.1_COMPLETION_REPORT.md
- execution_boundary/

Testing: All 653 ecosystem tests passing
Status: PRODUCTION READY
```

---

## Troubleshooting

### Issue: "Not in a git repository"

**Solution:** Ensure you're in the project root directory:
```bash
cd /home/franklin/SOFTWARE_ENGENEERING/Development/code/se-prep/Webportfolio/MYAI-AGENT/prototypeictalgo
python3 tag_release.py
```

### Issue: "Uncommitted changes detected"

**Solution:** Commit or stash your changes:
```bash
git status                 # See what changed
git add .                  # Stage changes
git commit -m "Message"    # Commit
python3 tag_release.py     # Try again
```

### Issue: "Tag already exists but points to different commit"

**Solution:** Either:
1. Use a different tag name: `python3 tag_release.py --tag-name new-tag`
2. Or delete the existing tag: `git tag -d shadow-mode-v1.0` then retry
3. Or check which is correct and resolve manually

### Issue: "Failed to push tag to remote"

**Solution:** Check remote connectivity:
```bash
git ls-remote origin              # Verify remote access
git push --dry-run origin         # Test push
python3 tag_release.py            # Retry tagging
```

---

## Integration with CI/CD

### In GitHub Actions

```yaml
- name: Create Release Tag
  run: |
    python3 tag_release.py
    
- name: Verify Tag
  run: |
    git show shadow-mode-v1.0
    git ls-remote --tags origin shadow-mode-v1.0
```

### In GitLab CI

```yaml
create_tag:
  stage: release
  script:
    - python3 tag_release.py
  only:
    - main
```

---

## Security Considerations

✅ **No Credentials Required**: Uses local git configuration  
✅ **No External Dependencies**: Standard git commands only  
✅ **Idempotent**: Safe to re-run without consequences  
✅ **Non-Destructive**: Only creates tags, doesn't modify code  
✅ **Reversible**: Tag can be deleted if needed: `git tag -d shadow-mode-v1.0`  

---

## Cleanup (If Needed)

### Delete local tag
```bash
git tag -d shadow-mode-v1.0
```

### Delete remote tag
```bash
git push origin --delete shadow-mode-v1.0
```

### Delete both
```bash
git tag -d shadow-mode-v1.0
git push origin --delete shadow-mode-v1.0
```

---

## Command Reference

### Using tag_release.sh

```bash
# Standard execution
./tag_release.sh

# No special flags (bash only has basic options)
```

### Using tag_release.py

```bash
# Standard execution
python3 tag_release.py

# Dry-run (preview only)
python3 tag_release.py --dry-run

# Custom tag name
python3 tag_release.py --tag-name my-release-v1.0

# Custom remote
python3 tag_release.py --remote upstream

# Skip confirmation prompts
python3 tag_release.py --force

# Combination
python3 tag_release.py --tag-name v2.0 --remote upstream --dry-run
```

---

## Manual Alternative

If you prefer to do this manually:

```bash
# Create annotated tag
git tag -a shadow-mode-v1.0 -m "Release: Shadow-Mode Decision Intelligence System v1.0"

# Push tag to remote
git push origin shadow-mode-v1.0

# Verify
git show shadow-mode-v1.0
git ls-remote --tags origin shadow-mode-v1.0
```

---

## Related Documentation

- `AUTHORITY_BOUNDARY.md` - Authority constraint governance
- `PHASE_10.1_COMPLETION_REPORT.md` - Semantic hardening details
- `EXECUTION_BOUNDARY_DELIVERY_SUMMARY.md` - Execution boundary module

---

**Version:** 1.0  
**Created:** December 20, 2025  
**Status:** Production-Ready
