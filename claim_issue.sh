#!/bin/bash

# Issue Claiming System for Multiple AI Sessions
# Prevents Claude/Codex sessions from working on the same issue

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

# Determine current branch for metadata
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || git rev-parse --short HEAD 2>/dev/null)
CURRENT_BRANCH="${CURRENT_BRANCH:-unknown}"

# Generate or retrieve session hash
SESSION_FILE="${HOME}/.claude_session_id"
if [ ! -f "$SESSION_FILE" ]; then
    # Generate unique session ID
    SESSION_HASH=$(date +%s%N | sha256sum | head -c 16)
    echo "$SESSION_HASH" > "$SESSION_FILE"
else
    SESSION_HASH=$(cat "$SESSION_FILE")
fi

COMMAND="${1:-}"
ISSUE_NUMBER="${2:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 <command> [issue_number]"
    echo ""
    echo "Commands:"
    echo "  claim <number>    - Claim an issue for this session"
    echo "  release <number>  - Release an issue when done"
    echo "  check <number>    - Check if an issue is claimed"
    echo "  list              - List all claimed issues"
    echo "  session           - Show current session hash"
    echo "  available         - List available (unclaimed) issues"
    exit 1
}

get_issue_comments() {
    local issue=$1
    gh issue view "$issue" --json comments --jq '.comments[].body' 2>/dev/null || echo ""
}

is_issue_claimed() {
    local issue=$1
    local comments=$(get_issue_comments "$issue")

    # Check for claim markers
    if echo "$comments" | grep -q "🔧 CLAIMED"; then
        return 0  # Issue is claimed
    fi
    return 1  # Issue is not claimed
}

get_claiming_session() {
    local issue=$1
    local comments=$(get_issue_comments "$issue")

    echo "$comments" | grep -A 3 "🔧 CLAIMED" | grep "Session:" | head -1 | sed 's/Session: //' | tr -d ' '
}

claim_issue() {
    local issue=$1

    # Check if issue exists
    if ! gh issue view "$issue" &>/dev/null; then
        echo -e "${RED}Error: Issue #${issue} does not exist${NC}"
        exit 1
    fi

    # Check if already claimed
    if is_issue_claimed "$issue"; then
        claiming_session=$(get_claiming_session "$issue")
        if [ "$claiming_session" = "$SESSION_HASH" ]; then
            echo -e "${YELLOW}Issue #${issue} is already claimed by this session${NC}"
        else
            echo -e "${RED}Error: Issue #${issue} is already claimed by session: ${claiming_session}${NC}"
            echo -e "${YELLOW}Use './claim_issue.sh check ${issue}' for more details${NC}"
            exit 1
        fi
    else
        # Claim the issue
        local timestamp=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
        local hostname=$(hostname)
        local user=$(whoami)

        gh issue comment "$issue" --body "🔧 CLAIMED by AI Session

Branch: ${CURRENT_BRANCH}

Session: ${SESSION_HASH}
User: ${user}@${hostname}
Started: ${timestamp}

This issue is being worked on. Please check before making changes."

        echo -e "${GREEN}✓ Successfully claimed issue #${issue}${NC}"
        echo -e "${BLUE}Session: ${SESSION_HASH}${NC}"

        # Show issue details
        gh issue view "$issue" --json title,labels --jq '"Title: " + .title + "\nLabels: " + ([.labels[].name] | join(", "))'
    fi
}

release_issue() {
    local issue=$1

    # Check if issue exists
    if ! gh issue view "$issue" &>/dev/null; then
        echo -e "${RED}Error: Issue #${issue} does not exist${NC}"
        exit 1
    fi

    # Check if claimed by this session
    if is_issue_claimed "$issue"; then
        claiming_session=$(get_claiming_session "$issue")
        if [ "$claiming_session" != "$SESSION_HASH" ]; then
            echo -e "${RED}Error: Issue #${issue} is claimed by another session: ${claiming_session}${NC}"
            echo -e "${YELLOW}Cannot release an issue claimed by another session${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}Warning: Issue #${issue} is not claimed${NC}"
        exit 0
    fi

    # Release the issue
    local timestamp=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

    gh issue comment "$issue" --body "✅ RELEASED by AI Session

Branch: ${CURRENT_BRANCH}

Session: ${SESSION_HASH}
Completed: ${timestamp}

Issue is now available for other sessions to work on."

    echo -e "${GREEN}✓ Successfully released issue #${issue}${NC}"
}

check_issue() {
    local issue=$1

    if ! gh issue view "$issue" &>/dev/null; then
        echo -e "${RED}Error: Issue #${issue} does not exist${NC}"
        exit 1
    fi

    echo -e "${BLUE}Issue #${issue} Status:${NC}"
    gh issue view "$issue" --json title,state,labels --jq '"Title: " + .title + "\nState: " + .state + "\nLabels: " + ([.labels[].name] | join(", "))'
    echo ""

    if is_issue_claimed "$issue"; then
        claiming_session=$(get_claiming_session "$issue")
        echo -e "${YELLOW}Status: CLAIMED${NC}"
        echo -e "Claimed by session: ${claiming_session}"

        if [ "$claiming_session" = "$SESSION_HASH" ]; then
            echo -e "${GREEN}(This is YOUR session)${NC}"
        else
            echo -e "${RED}(Claimed by ANOTHER session)${NC}"
        fi
    else
        echo -e "${GREEN}Status: AVAILABLE${NC}"
    fi
}

list_claimed_issues() {
    echo -e "${BLUE}Scanning repository for claimed issues...${NC}"
    echo ""

    local found_any=false

    # Get all open issues
    local issues=$(gh issue list --limit 100 --json number --jq '.[].number')

    for issue in $issues; do
        if is_issue_claimed "$issue"; then
            found_any=true
            claiming_session=$(get_claiming_session "$issue")
            local title=$(gh issue view "$issue" --json title --jq '.title')

            if [ "$claiming_session" = "$SESSION_HASH" ]; then
                echo -e "${GREEN}#${issue}${NC} [YOUR SESSION] - ${title}"
            else
                echo -e "${YELLOW}#${issue}${NC} [${claiming_session}] - ${title}"
            fi
        fi
    done

    if [ "$found_any" = false ]; then
        echo -e "${GREEN}No claimed issues found${NC}"
    fi
}

list_available_issues() {
    echo -e "${BLUE}Available (unclaimed) issues:${NC}"
    echo ""

    # Get all open issues
    local issues=$(gh issue list --limit 100 --json number,title,labels --jq '.[] | "\(.number)|\(.title)|\([.labels[].name] | join(","))"')

    local found_any=false

    while IFS='|' read -r number title labels; do
        if ! is_issue_claimed "$number"; then
            found_any=true
            local priority=""
            if echo "$labels" | grep -qi "high"; then
                priority="${RED}[HIGH]${NC}"
            elif echo "$labels" | grep -qi "medium"; then
                priority="${YELLOW}[MEDIUM]${NC}"
            else
                priority="[LOW]"
            fi
            echo -e "${GREEN}#${number}${NC} ${priority} - ${title}"
        fi
    done <<< "$issues"

    if [ "$found_any" = false ]; then
        echo -e "${YELLOW}No available issues found (all are claimed)${NC}"
    fi
}

show_session() {
    echo -e "${BLUE}Current Session Information:${NC}"
    echo "Session Hash: ${SESSION_HASH}"
    echo "User: $(whoami)"
    echo "Hostname: $(hostname)"
    echo "Session File: ${SESSION_FILE}"
    echo "Branch: ${CURRENT_BRANCH}"
}

# Main command processing
case "$COMMAND" in
    claim)
        if [ -z "$ISSUE_NUMBER" ]; then
            echo -e "${RED}Error: Issue number required${NC}"
            usage
        fi
        claim_issue "$ISSUE_NUMBER"
        ;;
    release)
        if [ -z "$ISSUE_NUMBER" ]; then
            echo -e "${RED}Error: Issue number required${NC}"
            usage
        fi
        release_issue "$ISSUE_NUMBER"
        ;;
    check)
        if [ -z "$ISSUE_NUMBER" ]; then
            echo -e "${RED}Error: Issue number required${NC}"
            usage
        fi
        check_issue "$ISSUE_NUMBER"
        ;;
    list)
        list_claimed_issues
        ;;
    session)
        show_session
        ;;
    available)
        list_available_issues
        ;;
    *)
        usage
        ;;
esac
