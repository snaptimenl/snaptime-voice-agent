"""Snaptime-specific layer on top of AIReceptionist.

Everything here talks to the Snaptime web app over its `/api/ai/*` HTTP API. The tools
(`toolkit.py`) are plain async functions that know nothing about LiveKit or OpenAI, so the
voice engine can be swapped later without touching Snaptime logic. `agent.py` is the thin
LiveKit wrapper that exposes them as function tools.
"""
