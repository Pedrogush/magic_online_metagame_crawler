import setuptools

setuptools.setup(
    name="mtg_metagame_tools",
    version="0.2",
    author="yochi",
    author_email="pedrogush@gmail.com",
    description="MTG Metagame Analysis: Opponent tracking and deck research tools for MTGO",
    packages=["widgets", "navigators", "utils"],
    classifiers=["Programming Language :: Python :: 3", "Operating System :: Windows"],
    python_requires=">=3.11",
    install_requires=[
        "pyautogui",  # Used for read-only window management and screenshots
        "loguru",
        "pillow",
        "pytesseract",
        "pynput",  # Used for opponent tracking configuration tool
        "curl_cffi",
        "beautifulsoup4",  # Web scraping MTGGoldfish
        "pymongo",  # Database for caching scraped data
    ],
)
