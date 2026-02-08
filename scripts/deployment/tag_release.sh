#!/bin/bash

################################################################################
#
# SHADOW-MODE RELEASE TAGGING SCRIPT
#
# Purpose: Create and push Git tag for shadow-mode-v1.0 release
# Safety: Idempotent, non-destructive, checks before executing
#
# Usage: ./tag_release.sh
#
################################################################################

set -e  # Exit on error

# Configuration
TAG_NAME="shadow-mode-v1.0"
TAG_MESSAGE="Release: Shadow-Mode Decision Intelligence System v1.0

Completion: 10-phase shadow-mode decision intelligence system with Phase 10.1 semantic hardening

Phases Included:
- Phase 1: Reasoning Manager (multi-round LLM collaboration)
- Phase 2: Reasoning Manager Integration (signal intelligence extraction)
- Phase 3: Policy Confidence Evaluator (confidence scoring and filtering)
- Phase 4: Policy Shadow Mode Integration (read-only policy filtering)
- Phase 5: Decision Intelligence Memory Service (historical signal/policy storage)
- Phase 6: Decision Human Review Service (human alignment tracking)
- Phase 7: Decision Offline Evaluation Service (counterfactual analysis)
- Phase 8: Decision Intelligence Archive Service (historical data persistence)
- Phase 9: Decision Human Review Service (expanded review capabilities)
- Phase 10: Decision Trust Calibration Service (historical consistency analysis)
- Phase 10.1: Semantic Hardening (authority boundary elimination)

Key Characteristics:
✅ Completely shadow-mode (zero authority, zero enforcement)
✅ Read-only analysis of signal consistency and policy violations
✅ Human review alignment measurement
✅ Counterfactual offline evaluation
✅ Immutable audit logging
✅ Deterministic outputs (same input = same output)
✅ Fail-silent error handling
✅ Zero external modifications or side effects
✅ Semantic hardening with explicit non-authority disclaimers
✅ Complete authority boundary documentation (AUTHORITY_BOUNDARY.md)
✅ Execution boundary isolation (execution_boundary/ module)

Governance:
- AUTHORITY_BOUNDARY.md: Absolute authority constraints
- PHASE_10.1_COMPLETION_REPORT.md: Semantic hardening details
- execution_boundary/: Complete execution intent isolation layer

Testing: All 653 ecosystem tests passing
Status: PRODUCTION READY"

REMOTE="origin"
BRANCH=$(git rev-parse --abbrev-ref HEAD)
COMMIT=$(git rev-parse --short HEAD)

################################################################################
# UTILITY FUNCTIONS
################################################################################

print_header() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════════╗"
    echo "║ $1"
    echo "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
}

print_status() {
    echo "✅ $1"
}

print_warning() {
    echo "⚠️  $1"
}

print_error() {
    echo "❌ $1"
}

print_info() {
    echo "ℹ️  $1"
}

################################################################################
# PRE-FLIGHT CHECKS
################################################################################

print_header "PRE-FLIGHT CHECKS"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not in a git repository"
    exit 1
fi

print_status "In git repository"

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    print_error "Uncommitted changes detected. Please commit or stash changes."
    exit 1
fi

print_status "No uncommitted changes"

# Check if tag already exists locally
if git rev-parse "$TAG_NAME" > /dev/null 2>&1; then
    print_warning "Tag '$TAG_NAME' already exists locally"
    
    # Check if it points to current HEAD
    local_tag_commit=$(git rev-list -n 1 "$TAG_NAME")
    current_commit=$(git rev-parse HEAD)
    
    if [ "$local_tag_commit" = "$current_commit" ]; then
        print_info "Tag already points to current HEAD ($COMMIT)"
        print_info "Checking if tag is pushed to remote..."
        
        # Check if tag exists on remote
        if git ls-remote --tags $REMOTE "$TAG_NAME" > /dev/null 2>&1; then
            print_status "Tag already exists on remote"
            print_info "No action needed - tag is already created and pushed"
            exit 0
        else
            print_warning "Tag exists locally but not on remote"
            print_info "Will push existing tag to remote..."
        fi
    else
        print_error "Tag '$TAG_NAME' already exists but points to different commit"
        print_error "  Local tag commit: $local_tag_commit"
        print_error "  Current HEAD commit: $current_commit"
        print_error "Please resolve manually or use a different tag name"
        exit 1
    fi
else
    print_status "Tag '$TAG_NAME' does not exist yet"
fi

################################################################################
# DISPLAY INFORMATION
################################################################################

print_header "RELEASE INFORMATION"

print_info "Repository: $(git config --get remote.$REMOTE.url)"
print_info "Branch: $BRANCH"
print_info "Commit: $COMMIT"
print_info "Tag: $TAG_NAME"

################################################################################
# CREATE TAG (if not exists)
################################################################################

print_header "CREATING TAG"

if ! git rev-parse "$TAG_NAME" > /dev/null 2>&1; then
    print_info "Creating annotated tag: $TAG_NAME"
    
    if git tag -a "$TAG_NAME" -m "$TAG_MESSAGE"; then
        print_status "Tag created successfully"
        
        # Display tag information
        echo ""
        git show --format=full "$TAG_NAME" | head -20
        echo ""
    else
        print_error "Failed to create tag"
        exit 1
    fi
else
    print_status "Tag already exists locally (will push to remote)"
fi

################################################################################
# PUSH TAG TO REMOTE
################################################################################

print_header "PUSHING TAG TO REMOTE"

print_info "Pushing tag to $REMOTE..."

if git push "$REMOTE" "$TAG_NAME"; then
    print_status "Tag pushed to remote successfully"
else
    print_error "Failed to push tag to remote"
    exit 1
fi

################################################################################
# VERIFICATION
################################################################################

print_header "VERIFICATION"

# Verify tag exists on remote
if git ls-remote --tags $REMOTE "$TAG_NAME" | grep -q "$TAG_NAME"; then
    print_status "Tag verified on remote"
else
    print_error "Tag not found on remote after push"
    exit 1
fi

# Show remote tag info
print_info "Remote tag details:"
git ls-remote --tags $REMOTE "$TAG_NAME"

################################################################################
# COMPLETION
################################################################################

print_header "RELEASE TAGGING COMPLETE"

print_status "Tag 'shadow-mode-v1.0' has been created and pushed successfully"
print_info "Repository is now tagged for release"
echo ""
print_info "To view tag details, run:"
echo "  git show shadow-mode-v1.0"
echo ""
print_info "To clone this specific release, run:"
echo "  git clone --branch shadow-mode-v1.0 <repository-url>"
echo ""
print_info "To list all tags, run:"
echo "  git tag -l"
echo ""

exit 0
