import unittest
from index_calendar import parse_metadata, clean_author_footer


def line(text, x=0.1, y=.953):
    return {"text": text, "confidence": 1, "x": x, "y": y}


class MetadataTests(unittest.TestCase):
    def test_early_author_without_role(self):
        r = parse_metadata({"attribution": [line("辛波斯卡 Wislawa Szymborska")]})
        self.assertEqual(r["author"], "辛波斯卡")

    def test_separate_fragments(self):
        r = parse_metadata({"attribution": [line("《唐顿庄园》"), line("编剧", .3), line("朱利安·费罗斯", .5)], "sources": [line("《唐顿庄园》")]})
        self.assertEqual(r["author"], "朱利安·费罗斯")
        self.assertEqual(r["source"], "唐顿庄园")

    def test_no_author_invented(self):
        self.assertIsNone(parse_metadata({})["author"])

    def test_prose_rejected(self):
        self.assertIsNone(parse_metadata({"attribution": [line("这是一个用于测试的句子。") ]})["author"])

    def test_folk_attribution(self):
        r = parse_metadata({"attribution": [line("英国民谣")]})
        self.assertEqual(r["source"], "英国民谣")
        self.assertIsNone(r["author"])

    def test_footer_noise(self):
        self.assertEqual(clean_author_footer('泰戈尔808'), '泰戈尔')
        self.assertEqual(clean_author_footer('史蒂夫·乔布斯 ）05'), '史蒂夫·乔布斯')
        self.assertIsNone(clean_author_footer('14'))
        self.assertIsNone(clean_author_footer('影像展上海长宁来福士钟楼'))
        self.assertEqual(clean_author_footer('Charles Dickens'), 'Charles Dickens')


if __name__ == "__main__":
    unittest.main()
