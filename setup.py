import setuptools

setuptools.setup(
    name="magic online metagame crawler",
    version="0.1",
    author="yochi",
    author_email="pedrogush@gmail.com",
    description="get stats out of modo",
    packages=[],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Windows"
    ],
    python_requires=">=3.11",
    install_requires=[
        "opencv-python>=4.0",
        "tqdm",
        "numpy",
        "pyautogui",
        "pillow",
        'loguru',
        "pytesseract",
        "pynput",
        "keyboard",
        "curl_cffi",
        "pytesseract",
        "pymongo",
        "selenium"
    ]
)
