#!/usr/bin/env python3
"""Retired entry point: the submission docx is now built from the MDPI template.

This name used to render a plain pandoc docx. The journal supplies `foods-template.dot`
and the submission has to be that template filled in, so the build moved to
`build_docx_template.py` (styles, headers, first-page block and three-line tables all
come from the template package). This shim is kept only so that an old command line
still produces the correct artefact instead of quietly producing the wrong one.
"""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parent / "build_docx_template.py"), run_name="__main__")
