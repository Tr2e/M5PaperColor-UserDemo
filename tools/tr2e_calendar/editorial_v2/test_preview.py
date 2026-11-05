"""Integrity checks on a complete generated year, including negative cases."""
import copy
import json
import unittest
from pathlib import Path

from PIL import Image
import build_preview as b


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = b.read(b.DEFAULT_OUT/'2027.json')
        cls.catalog = {r['id']: r for r in b.read(b.CATALOG)['records']}

    def test_reproduction_from_frozen_inputs(self):
        generated, _ = b.make_plan()
        self.assertEqual(self.plan, generated)
        for path, sha in self.plan['inputs'].items():
            self.assertEqual(b.digest(b.ROOT/path), sha, path)

    def test_full_year_constraints(self):
        result = b.verify(self.plan, self.catalog)
        self.assertEqual(result['days'], 365)
        self.assertEqual(result['repeat_groups_vs_2026'], 0)
        self.assertEqual(result['author_pairs_within_21_days'], [])

    def test_duplicate_and_history_leak_rejected(self):
        duplicate = copy.deepcopy(self.plan)
        for k in ('record_id', 'content_group', 'title_key'):
            duplicate['days'][10][k] = duplicate['days'][11][k]
        with self.assertRaises(AssertionError):
            b.verify(duplicate, self.catalog)
        leak = copy.deepcopy(self.plan)
        for k in ('record_id', 'content_group', 'title_key'):
            leak['days'][10][k] = b.read(b.HISTORY)['days'][0][k]
        with self.assertRaises(AssertionError):
            b.verify(leak, self.catalog)

    def test_calendar_metadata_corruption_rejected(self):
        corrupt = copy.deepcopy(self.plan)
        corrupt['days'][0]['weekday'] = 1
        with self.assertRaises(AssertionError):
            b.verify(corrupt, self.catalog)

    def test_all_images_complete_binary_and_audited(self):
        audits = b.read(b.DEFAULT_OUT/'render_audit.json')
        self.assertEqual(len(audits), 365)
        self.assertEqual(len(list((b.DEFAULT_OUT/'days').glob('*.png'))), 365)
        self.assertFalse(list(b.DEFAULT_OUT.rglob('*.bin')))
        for audit in audits:
            p = b.DEFAULT_OUT/'days'/(audit['date']+'.png')
            with Image.open(p) as im:
                self.assertEqual(im.size, (400, 600))
                self.assertEqual(im.mode, 'RGB')
                self.assertTrue(set(im.convert('L').getdata()) <= {0, 255})
            self.assertEqual(b.digest(p), audit['image_sha256'])
            self.assertTrue(audit['text_preserved'] and audit['bounds_checked'])

    def test_no_private_occasion_labels_in_gallery(self):
        gallery = (b.DEFAULT_OUT/'index.html').read_text()
        for word in ('结婚纪念日', '妻子生日', '儿子生日'):
            self.assertNotIn(word, gallery)

    def test_firmware_and_v1_inputs_unchanged(self):
        verified = b.read(b.DEFAULT_OUT/'verification.json')
        self.assertEqual(verified['protected_sha256'], b.protected_hashes())


if __name__ == '__main__':
    unittest.main()
