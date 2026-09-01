"""
Unified Dropbox Test Data Extractor entry point.
"""

try:
    from .test_dropbox_fetch import main
except ImportError:
    from test_dropbox_fetch import main

if __name__ == "__main__":
    main()
