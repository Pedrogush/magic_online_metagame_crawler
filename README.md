# MTGO Metagame Tools

A comprehensive desktop application for Magic: The Gathering Online (MTGO) players, providing metagame analysis, deck research, opponent tracking, and collection management.

![Version](https://img.shields.io/badge/version-0.2-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-orange)

## Features

### 🎯 Metagame Analysis
- **Live Metagame Data**: Fetch and analyze current metagame trends from MTGGoldfish
- **Archetype Browser**: Browse top decks by format with win rates and popularity metrics
- **Meta Statistics**: View archetype distribution over time with customizable date ranges
- **Daily Deck Averages**: Generate average decklists from top-performing archetypes

### 🃏 Deck Research & Builder
- **Deck Import**: Import decks from MTGGoldfish, MTGO, or paste directly
- **Visual Deck Builder**: Build and edit decks with full card search and filtering
- **Collection Integration**: See which cards you own and what you're missing
- **Mana Curve Analysis**: Visualize deck statistics including mana curve, land count, and color distribution
- **Card Inspector**: View high-quality card images with Scryfall integration

### 🎮 Match Tools
- **Opponent Tracking**: Automatically detect opponents and fetch their recent decklists
- **Match History**: Comprehensive match history with win rate statistics and game logs
- **Sideboard Guides**: Create and manage matchup-specific sideboarding strategies
- **Timer Alerts**: Get notified when MTGO challenge events are about to start

### 📦 Collection Management
- **MTGO Integration**: Import your collection directly from MTGO via the .NET Bridge
- **Deck Ownership Analysis**: Check which cards you need for any deck
- **Missing Cards Report**: Generate lists of cards needed for deck building

## Screenshots

*(Coming soon)*

## Installation

See [INSTALLATION.md](INSTALLATION.md) for detailed setup instructions.

### Quick Start (Windows)

1. **Prerequisites**:
   - Windows 10 or later
   - Python 3.11 or newer
   - MongoDB (optional, for deck persistence)
   - .NET 9.0 SDK (for MTGO Bridge)

2. **Clone the repository**:
   ```bash
   git clone https://github.com/Pedrogush/magic_online_metagame_crawler.git
   cd magic_online_metagame_crawler
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Run the application**:
   ```bash
   python main.py
   ```

For full setup including MTGO Bridge integration, see [INSTALLATION.md](INSTALLATION.md).

## Usage

### Launching the Application

```bash
python main.py
```

The main window provides access to all features through a tabbed interface:

- **Research**: Browse metagame archetypes and import decks
- **Builder**: Build and edit decks with full card search
- **Stats**: View deck statistics and mana curve analysis
- **Sideboard Guide**: Create matchup-specific boarding plans
- **Notes**: Add custom notes to your decks

### Menu Bar Features

- **File**:
  - Save/Load decks
  - Copy deck to clipboard
  - Import from collection export

- **Collection**:
  - Load MTGO collection
  - Refresh from bridge
  - Download card images

- **Tools**:
  - Opponent Deck Spy
  - Match History Viewer
  - Metagame Analysis
  - Challenge Timer Alerts

### Match History Win-Rate Stats

- **Data Source**: Stats are aggregated from MTGO `Match_GameLog_*.dat` files via the `MatchHistoryService`. Each log file counts as one match.
- **Perspective Detection**: The service first asks the MTGO bridge for the logged-in username; if unavailable it assumes the local player is listed first in the GameLog. Mirrors (both players on the same archetype) are still tracked because the opponent name is preserved.
- **Win/Loss Rules**: Winners reported by the log are authoritative. If the log omits a winner, scorelines such as `2-1` decide the outcome; matches with tied or missing scores are excluded from aggregates.
- **Per-Opponent Breakdown**: Opponent stats accumulate wins, losses, and last-played timestamps and are sorted by matches played so the most relevant rivals appear first in the deck selector.
- **Caching**: Parsed matches and computed aggregates are cached until you press **Refresh Win Rates**. This keeps the deck selector responsive even with large GameLog folders.

### Keyboard Shortcuts

- `Ctrl+S`: Save current deck
- `Ctrl+O`: Open deck from file
- `Ctrl+C`: Copy deck to clipboard (when deck list has focus)

## Architecture

This project follows a layered architecture pattern with clear separation of concerns. See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed information about:

- Project structure and module organization
- Service layer and repository pattern
- Widget architecture and UI components
- Data flow and state management

## Development

### Prerequisites

- Python 3.11+
- Black and Ruff for code formatting
- pytest for testing
- SSH access to Windows machine (for running tests)

### Development Workflow

```bash
# Run linters, tests, and commit (automated)
./lint_test_commit.sh

# Or manually:
black .
ruff check --fix .
pytest
```

See [WORKFLOW.md](WORKFLOW.md) for detailed development workflow including:
- Automated testing and CI
- Issue claiming system for multi-agent development
- Commit and push workflows

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_deck_service.py

# Run with verbose output
pytest -v

# Run UI tests (requires display)
pytest tests/ui/
```

### Code Quality

The project uses:
- **Black**: Code formatting (line length 100)
- **Ruff**: Fast Python linter
- **mypy**: Static type checking (permissive mode)
- **Bandit**: Security linting

Configuration is in `pyproject.toml`.

## Project Structure

```
magic_online_metagame_crawler/
├── main.py                 # Application entry point
├── widgets/                # UI components
│   ├── deck_selector.py    # Main application window
│   ├── panels/             # Reusable UI panels
│   ├── dialogs/            # Modal dialogs
│   └── buttons/            # Custom button widgets
├── services/               # Business logic layer
│   ├── deck_service.py
│   ├── collection_service.py
│   ├── search_service.py
│   └── image_service.py
├── repositories/           # Data access layer
│   ├── deck_repository.py
│   ├── card_repository.py
│   └── metagame_repository.py
├── navigators/             # External API integrations
│   ├── mtggoldfish.py      # MTGGoldfish scraper
│   └── mtgo_decklists.py   # MTGO.com parser
├── utils/                  # Utility modules
│   ├── card_data.py        # Card metadata management
│   ├── gamelog_parser.py   # Match history parsing
│   └── archetype_classifier.py
├── dotnet/MTGOBridge/      # .NET bridge for MTGO integration
├── tests/                  # Test suite
└── scripts/                # Utility scripts
```

## MTGO Bridge

The MTGO Bridge is a .NET component that interfaces with Magic Online to extract collection and match history data. See `dotnet/MTGOBridge/README.md` for:

- .NET SDK installation
- Building the bridge
- Running collection and history exports

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Follow the code style (Black + Ruff)
4. Add tests for new functionality
5. Submit a pull request

See [WORKFLOW.md](WORKFLOW.md) for the issue claiming system when multiple AI agents are contributing.

## Data Sources

- **Metagame Data**: [MTGGoldfish](https://www.mtggoldfish.com/)
- **Card Data**: [Scryfall API](https://scryfall.com/docs/api)
- **Card Images**: Scryfall bulk data
- **MTGO Data**: [MTGOSDK](https://github.com/videre-project/MTGOSDK)

## Known Limitations

- Windows only (due to wxPython and MTGO dependencies)
- MTGO Bridge requires Magic Online to be installed
- Collection import requires MTGO to be running
- Some features require internet connection for metagame data

## Troubleshooting

### Application won't start
- Ensure Python 3.11+ is installed
- Check all dependencies are installed: `pip install -r requirements-dev.txt`
- Verify wxPython is properly installed for Windows

### Card images not loading
- Run `python -m scripts.fetch_mana_assets` to download mana symbols
- Check internet connection for Scryfall API access
- Use "Download Missing Images" from the Collection menu

### MTGO Bridge not working
- Ensure .NET 9.0 SDK is installed
- Build the bridge: `cd dotnet/MTGOBridge && dotnet build`
- MTGO must be running when using the bridge

### Tests failing on Windows
- Ensure pytest is installed
- Some UI tests require a display (run locally, not over SSH)
- Check `tests/TESTING_GUIDE.md` for testing best practices

## License

MIT License - see LICENSE file for details

## Acknowledgments

- **MTGOSDK**: For providing MTGO integration capabilities
- **Scryfall**: For comprehensive card data and images
- **MTGGoldfish**: For metagame statistics and decklists
- **wxPython**: For the GUI framework

## Support

- **Issues**: [GitHub Issues](https://github.com/Pedrogush/magic_online_metagame_crawler/issues)
- **Discussions**: Use GitHub Discussions for questions and ideas

## Roadmap

See [TODO.txt](TODO.txt) for upcoming features and planned improvements.

---

**Version**: 0.2
**Author**: yochi (pedrogush@gmail.com)
**Status**: Active Development
