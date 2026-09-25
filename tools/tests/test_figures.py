"""Tests for the figure layout audit in tools/figures.py (house style: Times New Roman 11 pt, no hidden or clashing text)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import figures  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402


def problems_of(build):
    fig, ax = plt.subplots(figsize=(6.5, 3))
    build(ax)
    out = figures.audit(fig)
    plt.close(fig)
    return out


class TestAudit(unittest.TestCase):
    def test_clean_figure_passes(self):
        def build(ax):
            ax.barh([0, 1], [100, 50], color=figures.NAVY)
            ax.text(102, 0, "100", va="center")
            ax.text(52, 1, "50", va="center")
            ax.set_xlim(0, 130)
        self.assertEqual(problems_of(build), [])

    def test_white_text_running_off_a_narrow_bar_fails(self):
        def build(ax):
            ax.bar([0], [120], width=0.1, color=figures.RED)
            ax.set_xlim(-1, 1)
            ax.text(0, 60, "61% of households report lost income", ha="center", color="white")
        p = problems_of(build)
        self.assertTrue(any("white text" in s or "partly off" in s for s in p), p)

    def test_overlapping_text_fails(self):
        def build(ax):
            ax.text(0.5, 0.5, "First label here")
            ax.text(0.52, 0.5, "Second label here")
        self.assertTrue(any("overlaps" in s for s in problems_of(build)))

    def test_text_on_a_plotted_line_fails(self):
        def build(ax):
            ax.plot([0, 1], [0.5, 0.5], color=figures.BLUE)
            ax.set_ylim(0, 1)
            ax.text(0.4, 0.49, "Town name")
        self.assertTrue(any("plotted line" in s for s in problems_of(build)))

    def test_wrong_font_size_fails(self):
        def build(ax):
            ax.text(0.1, 0.5, "Too small", fontsize=8)
        self.assertTrue(any("pt, not" in s for s in problems_of(build)))

    def test_low_contrast_text_in_box_fails(self):
        def build(ax):
            ax.bar([0], [10], width=1.5, color=figures.NAVY)
            ax.set_xlim(-1, 1)
            ax.text(0, 5, "Dark", ha="center", color="black")
        self.assertTrue(any("low contrast" in s for s in problems_of(build)))


if __name__ == "__main__":
    unittest.main()
