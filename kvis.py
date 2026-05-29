#!/usr/bin/env python3
"""KVIS Analyzer — YouTube content analysis for musical artists.

Analyze any artist's YouTube channel: extract transcripts, classify content,
analyze audio spectrums, read fan comments, and discover cross-audience insights.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kvis.cli import main
main()
