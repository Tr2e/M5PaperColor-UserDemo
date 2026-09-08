#!/usr/bin/env python3

import io
import unittest

from collect_display_metrics import parse_lines, parse_pipeline, percentile, summarize, write_csv


SAMPLE_LOG = """\
PaperColorPipeline: mode=photo-balanced prepare_us=247000 workspace_bytes=9696
I (123) DisplayMetrics: source=home_full success=1 total_us=12000000 render_us=20000 render_to_refresh_us=10 panel_us=11979990 internal_before=200000 internal_after=198000 internal_largest=150000 psram_before=6000000 psram_after=5999000 psram_largest=5000000
I (456) OtherTag: ignored=true
I (789) DisplayMetrics: source=home_full success=1 total_us=14000000 render_us=21000 render_to_refresh_us=20 panel_us=13978980 internal_before=198000 internal_after=197000 internal_largest=149000 psram_before=5999000 psram_after=5998000 psram_largest=4999000
I (999) DisplayMetrics: source=local_photo success=0 total_us=1000 render_us=1000 render_to_refresh_us=0 panel_us=0 internal_before=197000 internal_after=196000 internal_largest=148000 psram_before=5998000 psram_after=5997000 psram_largest=4998000
"""


class DisplayMetricsParserTest(unittest.TestCase):
    def test_parse_pipeline(self) -> None:
        pipeline = parse_pipeline(SAMPLE_LOG.splitlines())
        self.assertEqual(
            {"mode": "photo-balanced", "prepare_us": 247_000, "workspace_bytes": 9_696},
            pipeline,
        )

    def test_parse_and_summarize(self) -> None:
        records = parse_lines(SAMPLE_LOG.splitlines())
        self.assertEqual(3, len(records))
        self.assertEqual("home_full", records[0]["source"])
        self.assertEqual(14_000_000, records[1]["total_us"])

        summary = summarize(records)
        self.assertEqual(3, summary["record_count"])
        home = summary["sources"]["home_full"]
        self.assertEqual(2, home["success_count"])
        self.assertEqual(12_000_000, home["total_us_p50"])
        self.assertEqual(14_000_000, home["total_us_p95"])
        self.assertEqual(197_000, home["min_internal_after"])

        local = summary["sources"]["local_photo"]
        self.assertEqual(1, local["failure_count"])
        self.assertIsNone(local["panel_us_p50"])

    def test_csv_schema(self) -> None:
        records = parse_lines(SAMPLE_LOG.splitlines())
        output = io.StringIO()
        write_csv(records, output)
        self.assertTrue(output.getvalue().startswith("source,success,total_us"))
        self.assertIn("local_photo,0,1000", output.getvalue())

    def test_nearest_rank_percentile(self) -> None:
        self.assertEqual(1, percentile([1, 2, 3, 4], 0.25))
        self.assertEqual(4, percentile([1, 2, 3, 4], 0.95))


if __name__ == "__main__":
    unittest.main()
