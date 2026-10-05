import unittest
from datetime import datetime, timezone
from content_policy import classify, excluded, annotate


class PolicyTests(unittest.TestCase):
    def test_clear_music(self):
        for title in ['Fascial Sound Bath: Drone Tones', '888 Hz Frequency', 'Focus with Binaural Beats']:
            self.assertTrue(classify(title)['autoExcluded'])

    def test_ambiguous_music_is_review_not_exclusion(self):
        for title in ['The Wiggly Wonder of Music | TED', 'Cleaning Affirmations to House Music',
                      'The science of binaural beats explained', 'Guided Meditation for Clarity']:
            self.assertFalse(classify(title)['autoExcluded'])

    def test_human_override(self):
        self.assertFalse(excluded({'title': '888 Hz', 'radarOverride': 'include'}))
        self.assertTrue(excluded({'title': 'A talk', 'radarOverride': 'exclude'}))

    def test_freshness_and_format(self):
        now = datetime(2026, 10, 5, tzinfo=timezone.utc)
        old = annotate({'lastUpdated':'2026-09-19T10:00:00', 'durationSeconds':400}, now)
        self.assertTrue(old['stale'])
        self.assertEqual(old['formatGroup'], 'long_form')
        fresh = annotate({'lastUpdated':'2026-10-05T00:00:00Z','durationSeconds':60}, now)
        self.assertFalse(fresh['stale'])
        self.assertEqual(fresh['formatGroup'], 'short')
        self.assertTrue(annotate({}, now)['stale'])


if __name__ == '__main__':
    unittest.main()
