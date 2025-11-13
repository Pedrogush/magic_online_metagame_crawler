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
