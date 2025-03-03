from setuptools import find_packages, setup

setup(
    name="rss-digest-tool",
    version="0.9.0",
    packages=find_packages(),
    install_requires=[
        "anthropic",
        "beautifulsoup4",
        "feedfinder2",
        "feedgen",
        "feedparser",
        "newspaper3k",
        "schedule",
        "pydantic",
        "nltk",
        "click",
        "requests",
        "lxml",
        "python-dateutil",
        "PyYAML",
        "tqdm",
        "httpx",
    ],
    python_requires=">=3.8",
    author="Hower He",
    author_email="hower@howerhe.xyz",
    description="RSS Digest Tool with AI summaries using Claude",
    keywords="rss, digest, ai, summary, claude",
    url="https://github.com/howerhe/rss-digest-tool",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content :: News/Diary",
    ],
)
