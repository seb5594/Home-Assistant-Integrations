name: Home Assistant CI

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  catalog:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
      - uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6
        with:
          python-version: '3.14'
      - run: pip install ruff
      - run: ruff check .
      - run: python -m unittest discover -s tests -p 'test_*.py' -v
      - run: python scripts/build_release.py
      - name: Check reproducible README
        run: |
          python scripts/sync_catalog.py --from-lock
          git diff --exit-code -- README.md catalog-feed.json assets/brands/README.md
  home-assistant:
    name: Home Assistant ${{ matrix.ha }}
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        include:
          - python: '3.11'
            ha: '2024.1.2'
            test-plugin: '0.13.88' # Home Assistant 2024.1.2, minimum supported version
            zeroconf: '0.131.0'
          - python: '3.12'
            ha: '2024.12.4'
            test-plugin: '0.13.194' # Home Assistant 2024.12.4, options API transition
            zeroconf: '0.136.2'
          - python: '3.13'
            ha: '2025.1.0'
            test-plugin: '0.13.201' # Home Assistant 2025.1.0
            zeroconf: '0.136.2' # Requirement of this HA version's zeroconf integration
          - python: '3.13'
            ha: '2025.12.4'
            test-plugin: '0.13.301' # Home Assistant 2025.12.4
            zeroconf: '0.148.0'
          - python: '3.14'
            ha: '2026.10.4'
            test-plugin: '0.13.375' # Home Assistant 2026.10.4
            zeroconf: '0.151.5'
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
      - uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6
        with:
          python-version: ${{ matrix.python }}
      - run: pip install pytest-homeassistant-custom-component==${{ matrix.test-plugin }} zeroconf==${{ matrix.zeroconf }}
      - run: pytest -q tests_ha
