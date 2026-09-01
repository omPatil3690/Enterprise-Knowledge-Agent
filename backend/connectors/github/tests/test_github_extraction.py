"""
Unified GitHub Test Data Extractor entry point.
"""

try:
    from .test_github_fetch import main
except ImportError:
    from test_github_fetch import main

if __name__ == "__main__":
    main()
