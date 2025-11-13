## Development Workflow Scripts

This project includes automated workflow scripts to streamline development, testing, and deployment.

### Quick Reference

```bash
# Run the complete workflow (lint + test + commit)
ltc

# Or use the full path
./lint_test_commit.sh

# Run just pytest on the host machine
./run_pytest_on_host.sh

# Run pytest with specific arguments
./run_pytest_on_host.sh -v -k test_specific_function
```

### Lint, Test, Commit Workflow (`ltc` alias)

The `lint_test_commit.sh` script automates the complete development workflow:

**Step 1: Linting**
- Runs Black to format code
- Runs Ruff to check and fix linting issues
- Auto-applies fixes when possible

**Step 2: Testing**
- Executes pytest on the Windows host machine via SSH
- Captures full test output for analysis

**Step 3: Smart Handling**
- **If tests pass**: Creates a commit with linting changes and pushes to remote
- **If tests fail**: Spawns a new Claude Code session with `--dangerously-skip-permissions` to automatically analyze failures, fix the code, verify the fixes, and commit

### Setup Requirements

**For pytest on host machine:**
Create `~/.ssh/pytest_host.conf` with:
```bash
HOST_USER="your_windows_username"
HOST_IP="192.168.x.x"
PYTEST_PATH="C:/path/to/pytest.exe"
PROJECT_PATH="C:/path/to/project"
SSH_KEY="${HOME}/.ssh/id_ed25519"  # optional, defaults to id_ed25519
```

**SSH key authentication:**
Ensure your SSH key is set up for password-less login to the Windows host.

**Python dependencies:**
```bash
pip install black ruff pytest
```

### How It Works

The workflow is designed for development on Linux while the application (wxPython) runs on Windows:

1. Make code changes on Linux machine
2. Run `ltc` to lint, test on Windows host, and commit
3. If tests fail, Claude Code automatically fixes issues
4. Changes are pushed to remote repository
5. Repeat

This enables a tight feedback loop while maintaining proper test coverage on the target platform.

### Manual Override

If you want to skip the automatic fixing and handle test failures yourself:

```bash
# Run just the linters
python3 -m black .
python3 -m ruff check --fix .

# Run tests manually
./run_pytest_on_host.sh -v

# Commit manually if needed
git add -A
git commit -m "Your message"
git push
```

### CI/CD Integration

The `run_pytest_on_host.sh` script can be integrated into CI pipelines that have access to the Windows test machine via SSH.

## Issue Claiming System

When working with multiple AI sessions (Claude Code, Codex, etc.), the issue claiming system prevents conflicts by tracking which session is working on which issue.

### Quick Reference

```bash
# List available (unclaimed) issues
issues-available

# Claim an issue to work on it
claim 9

# Check status of an issue
check-issue 9

# See all claimed issues
issues-claimed

# Release an issue when done
unclaim 9
```

### How It Works

Each AI session gets a unique session hash stored in `~/.claude_session_id`. When you claim an issue:

1. The system checks if the issue is already claimed by another session
2. If available, it adds a comment to the issue with your session hash
3. Other sessions will see the issue is claimed and won't work on it
4. When you're done, release the issue so others can work on it

### Session Management

**View current session info:**
```bash
./claim_issue.sh session
```

**Before starting work on an issue:**
```bash
# Check what's available
issues-available

# Claim the issue
claim 11
```

**When finished:**
```bash
# Release the issue
unclaim 11
```

### Commands

All commands are available via the `claim_issue.sh` script:

```bash
./claim_issue.sh claim <number>     # Claim an issue
./claim_issue.sh release <number>   # Release an issue
./claim_issue.sh check <number>     # Check issue status
./claim_issue.sh list               # List all claimed issues
./claim_issue.sh available          # List unclaimed issues
./claim_issue.sh session            # Show session info
```

### Workflow Integration

The typical workflow with issue claiming:

```bash
# 1. See what's available
issues-available

# 2. Claim an issue
claim 11

# 3. Work on the issue (make changes, test, commit)
# ... make your changes ...

# 4. Run the lint-test-commit workflow
ltc

# 5. Release the issue when done
unclaim 11
```

### Multi-Session Safety

The system prevents conflicts when multiple AI sessions are running:

- ✅ Claims are checked before allowing work
- ✅ Each session has a unique identifier
- ✅ You can see which session owns which issue
- ✅ Cannot release issues claimed by other sessions
- ✅ Works across Claude Code and Codex sessions

### Example Output

```bash
$ issues-available
Available (unclaimed) issues:

#9 [HIGH] - Fix broken tests after refactoring
#11 [HIGH] - Address thread safety in loading flags
#14 [MEDIUM] - Extract large complex methods in deck_selector

$ claim 11
✓ Successfully claimed issue #11
Session: a1b2c3d4e5f6g7h8
Title: Address thread safety in loading flags
Labels: bug, concurrency

$ issues-claimed
Scanning repository for claimed issues...

#11 [YOUR SESSION] - Address thread safety in loading flags
#9 [x9y8z7w6v5u4t3s2] - Fix broken tests after refactoring
```
