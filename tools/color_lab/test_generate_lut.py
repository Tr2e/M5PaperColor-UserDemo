import tempfile
import unittest
from pathlib import Path

from evaluate_lut import evaluate
from generate_lut import LUT_SIZE, delta_e_2000, generate_lut, load_profile


PROFILE = Path(__file__).parent / "profiles" / "nominal.json"
LUT_ARTIFACT = Path(__file__).parents[2] / "artifacts" / "color_lut" / "nominal-5bit.lut"


class GenerateLutTests(unittest.TestCase):
    def test_ciede2000_reference_pairs(self) -> None:
        pairs = (
            ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
            ((50.0, 3.1571, -77.2803), (50.0, 0.0, -82.7485), 2.8615),
            ((50.0, 2.8361, -74.0200), (50.0, 0.0, -82.7485), 3.4412),
            ((50.0, -1.3802, -84.2814), (50.0, 0.0, -82.7485), 1.0000),
        )
        for first, second, expected in pairs:
            self.assertAlmostEqual(delta_e_2000(first, second), expected, places=4)

    def test_nominal_lut_shape_and_native_codes(self) -> None:
        lut = generate_lut(load_profile(PROFILE))
        self.assertEqual(len(lut), LUT_SIZE)
        self.assertEqual(set(lut), {0, 1, 2, 3, 5, 6})
        self.assertEqual(lut[0], 0)
        self.assertEqual(lut[-1], 1)

    def test_checked_in_lut_matches_profile(self) -> None:
        self.assertEqual(LUT_ARTIFACT.read_bytes(), generate_lut(load_profile(PROFILE)))

    def test_invalid_profile_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"grid_bits": 4, "colors": []}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_profile(path)

    def test_perceptual_lut_improves_nominal_grid(self) -> None:
        profile = load_profile(PROFILE)
        result = evaluate(profile, generate_lut(profile))
        self.assertEqual(result["sample_count"], LUT_SIZE)
        self.assertGreater(result["mapping_disagreements"], 0)
        self.assertGreater(result["mean_delta_e_reduction_percent"], 0.0)
        self.assertGreater(result["candidate_wins"], 0)
        self.assertEqual(result["candidate_losses"], 0)

    def test_evaluator_rejects_malformed_lut(self) -> None:
        with self.assertRaises(ValueError):
            evaluate(load_profile(PROFILE), b"too short")


if __name__ == "__main__":
    unittest.main()
