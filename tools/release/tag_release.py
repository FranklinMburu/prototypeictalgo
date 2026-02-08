#!/usr/bin/env python3

"""
SHADOW-MODE RELEASE TAGGING SCRIPT (Python)

Purpose: Create and push Git tag for shadow-mode-v1.0 release
Safety: Idempotent, non-destructive, comprehensive error handling
Status: Production-ready

Usage:
    python3 tag_release.py
    
    Optional arguments:
    --tag-name NAME         (default: shadow-mode-v1.0)
    --remote REMOTE         (default: origin)
    --dry-run              (show what would be done, don't execute)
    --force                (skip confirmation prompts)
"""

import subprocess
import sys
from typing import Tuple, Optional
from datetime import datetime
import argparse


class ColorOutput:
    """ANSI color output for terminal."""

    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

    @staticmethod
    def header(text: str) -> None:
        """Print formatted header."""
        print(f"\n{ColorOutput.BOLD}{ColorOutput.CYAN}{'═' * 72}{ColorOutput.RESET}")
        print(f"{ColorOutput.BOLD}{ColorOutput.CYAN}  {text}{ColorOutput.RESET}")
        print(f"{ColorOutput.BOLD}{ColorOutput.CYAN}{'═' * 72}{ColorOutput.RESET}\n")

    @staticmethod
    def success(text: str) -> None:
        """Print success message."""
        print(f"{ColorOutput.GREEN}✅ {text}{ColorOutput.RESET}")

    @staticmethod
    def warning(text: str) -> None:
        """Print warning message."""
        print(f"{ColorOutput.YELLOW}⚠️  {text}{ColorOutput.RESET}")

    @staticmethod
    def error(text: str) -> None:
        """Print error message."""
        print(f"{ColorOutput.RED}❌ {text}{ColorOutput.RESET}")

    @staticmethod
    def info(text: str) -> None:
        """Print info message."""
        print(f"{ColorOutput.BLUE}ℹ️  {text}{ColorOutput.RESET}")


class GitReleaseTagging:
    """Safe, idempotent Git release tagging."""

    TAG_NAME = "shadow-mode-v1.0"
    TAG_MESSAGE = """Release: Shadow-Mode Decision Intelligence System v1.0

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
Status: PRODUCTION READY"""

    def __init__(self, tag_name: str = TAG_NAME, remote: str = "origin", dry_run: bool = False):
        """Initialize tagging manager."""
        self.tag_name = tag_name
        self.remote = remote
        self.dry_run = dry_run
        self.current_commit = None
        self.branch = None

    def run_cmd(self, cmd: list, capture: bool = False) -> Tuple[int, str]:
        """
        Run a shell command safely.

        Args:
            cmd: Command as list of strings
            capture: If True, capture stdout

        Returns:
            (exit_code, output) tuple
        """
        try:
            if self.dry_run:
                ColorOutput.info(f"[DRY-RUN] Would run: {' '.join(cmd)}")
                return 0, ""

            if capture:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False
                )
                return result.returncode, result.stdout.strip()
            else:
                result = subprocess.run(
                    cmd,
                    timeout=10,
                    check=False
                )
                return result.returncode, ""

        except subprocess.TimeoutExpired:
            ColorOutput.error(f"Command timed out: {' '.join(cmd)}")
            return 1, ""
        except Exception as e:
            ColorOutput.error(f"Command failed: {str(e)}")
            return 1, ""

    def check_git_repo(self) -> bool:
        """Check if we're in a valid git repository."""
        code, _ = self.run_cmd(["git", "rev-parse", "--git-dir"], capture=True)
        if code != 0:
            ColorOutput.error("Not in a git repository")
            return False

        ColorOutput.success("In git repository")
        return True

    def check_uncommitted_changes(self) -> bool:
        """Check for uncommitted changes."""
        code, _ = self.run_cmd(
            ["git", "diff-index", "--quiet", "HEAD", "--"],
            capture=True
        )

        if code != 0:
            ColorOutput.error("Uncommitted changes detected. Please commit or stash changes.")
            return False

        ColorOutput.success("No uncommitted changes")
        return True

    def get_current_state(self) -> bool:
        """Get current branch and commit info."""
        code, branch = self.run_cmd(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture=True
        )
        if code != 0:
            ColorOutput.error("Failed to get current branch")
            return False

        code, commit_short = self.run_cmd(
            ["git", "rev-parse", "--short", "HEAD"],
            capture=True
        )
        if code != 0:
            ColorOutput.error("Failed to get current commit")
            return False

        code, commit_full = self.run_cmd(
            ["git", "rev-parse", "HEAD"],
            capture=True
        )
        if code != 0:
            ColorOutput.error("Failed to get full commit hash")
            return False

        self.branch = branch
        self.current_commit = commit_full

        return True

    def tag_exists_locally(self) -> bool:
        """Check if tag exists in local repository."""
        code, _ = self.run_cmd(
            ["git", "rev-parse", self.tag_name],
            capture=True
        )
        return code == 0

    def tag_exists_remotely(self) -> bool:
        """Check if tag exists on remote."""
        code, output = self.run_cmd(
            ["git", "ls-remote", "--tags", self.remote, self.tag_name],
            capture=True
        )
        return code == 0 and self.tag_name in output

    def get_tag_commit(self) -> Optional[str]:
        """Get commit hash that tag points to."""
        code, commit = self.run_cmd(
            ["git", "rev-list", "-n", "1", self.tag_name],
            capture=True
        )
        return commit if code == 0 else None

    def get_remote_url(self) -> Optional[str]:
        """Get remote repository URL."""
        code, url = self.run_cmd(
            ["git", "config", "--get", f"remote.{self.remote}.url"],
            capture=True
        )
        return url if code == 0 else None

    def create_tag(self) -> bool:
        """Create annotated tag."""
        if self.tag_exists_locally():
            ColorOutput.success("Tag already exists locally (will push to remote)")
            return True

        ColorOutput.info(f"Creating annotated tag: {self.tag_name}")

        code, _ = self.run_cmd([
            "git", "tag", "-a", self.tag_name,
            "-m", self.TAG_MESSAGE
        ])

        if code != 0:
            ColorOutput.error("Failed to create tag")
            return False

        ColorOutput.success("Tag created successfully")
        return True

    def push_tag(self) -> bool:
        """Push tag to remote repository."""
        ColorOutput.info(f"Pushing tag to {self.remote}...")

        code, _ = self.run_cmd([
            "git", "push", self.remote, self.tag_name
        ])

        if code != 0:
            ColorOutput.error("Failed to push tag to remote")
            return False

        ColorOutput.success("Tag pushed to remote successfully")
        return True

    def verify_tag(self) -> bool:
        """Verify tag exists on remote."""
        if not self.tag_exists_remotely():
            ColorOutput.error("Tag not found on remote after push")
            return False

        ColorOutput.success("Tag verified on remote")

        # Show remote tag info
        code, output = self.run_cmd(
            ["git", "ls-remote", "--tags", self.remote, self.tag_name],
            capture=True
        )

        if code == 0:
            ColorOutput.info(f"Remote tag details:\n{output}")

        return True

    def validate_tag_state(self) -> bool:
        """Validate tag points to correct commit."""
        if not self.tag_exists_locally():
            return True  # Tag will be created

        tag_commit = self.get_tag_commit()
        if tag_commit != self.current_commit:
            ColorOutput.error("Tag already exists but points to different commit")
            ColorOutput.error(f"  Tag commit:     {tag_commit}")
            ColorOutput.error(f"  Current commit: {self.current_commit}")
            return False

        if self.tag_exists_remotely():
            ColorOutput.info("Tag already exists on remote (idempotent - no action needed)")
            return True

        return True

    def execute(self) -> bool:
        """Execute complete tagging workflow."""
        try:
            # Pre-flight checks
            ColorOutput.header("PRE-FLIGHT CHECKS")

            if not self.check_git_repo():
                return False

            if not self.check_uncommitted_changes():
                return False

            if not self.get_current_state():
                return False

            # Validate tag state
            ColorOutput.header("VALIDATING TAG STATE")

            if not self.validate_tag_state():
                return False

            # Display information
            ColorOutput.header("RELEASE INFORMATION")

            remote_url = self.get_remote_url()
            ColorOutput.info(f"Repository: {remote_url or 'unknown'}")
            ColorOutput.info(f"Branch: {self.branch}")
            ColorOutput.info(f"Commit: {self.current_commit[:7]}")
            ColorOutput.info(f"Tag: {self.tag_name}")

            if self.dry_run:
                ColorOutput.warning("DRY-RUN MODE: No changes will be made")

            # Confirm before proceeding
            if not self.dry_run:
                response = input(f"\n{ColorOutput.BOLD}Proceed with tagging? (y/n): {ColorOutput.RESET}").lower()
                if response != 'y':
                    ColorOutput.warning("Tagging cancelled by user")
                    return False

            # Create tag
            ColorOutput.header("CREATING/VERIFYING TAG")

            if not self.create_tag():
                return False

            # Push tag
            ColorOutput.header("PUSHING TAG")

            if not self.push_tag():
                return False

            # Verify
            ColorOutput.header("VERIFICATION")

            if not self.verify_tag():
                return False

            # Complete
            ColorOutput.header("RELEASE TAGGING COMPLETE")

            ColorOutput.success(f"Tag '{self.tag_name}' has been created and pushed successfully")
            ColorOutput.info("Repository is now tagged for release")

            print(f"\n{ColorOutput.BOLD}To view tag details, run:{ColorOutput.RESET}")
            print(f"  git show {self.tag_name}\n")

            print(f"{ColorOutput.BOLD}To clone this specific release, run:{ColorOutput.RESET}")
            print(f"  git clone --branch {self.tag_name} <repository-url>\n")

            print(f"{ColorOutput.BOLD}To list all tags, run:{ColorOutput.RESET}")
            print(f"  git tag -l\n")

            return True

        except KeyboardInterrupt:
            ColorOutput.warning("Interrupted by user")
            return False
        except Exception as e:
            ColorOutput.error(f"Unexpected error: {str(e)}")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create and push Git tag for shadow-mode-v1.0 release"
    )
    parser.add_argument(
        "--tag-name",
        default="shadow-mode-v1.0",
        help="Tag name (default: shadow-mode-v1.0)"
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Remote name (default: origin)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts"
    )

    args = parser.parse_args()

    tagger = GitReleaseTagging(
        tag_name=args.tag_name,
        remote=args.remote,
        dry_run=args.dry_run
    )

    success = tagger.execute()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
