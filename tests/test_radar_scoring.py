import unittest
from datetime import datetime,timezone
from radar_scoring import score_entries

NOW=datetime(2026,10,5,tzinfo=timezone.utc)


def entry(i,views=2000,**fields):
    return {'id':str(i),'title':'Practical teaching','duration':600,'upload_date':'20261002','view_count':views,**fields}


class ScoringTests(unittest.TestCase):
    def test_comparable_peer_group(self):
        entries=[entry(i) for i in range(5)]+[entry('hit',10000)]
        result=score_entries(entries,NOW)['hit']
        self.assertEqual(result['outlierScore'],5)
        self.assertEqual(result['baselineSampleSize'],6)
        self.assertEqual(result['scoreBasis'],'matched_age_duration_content')

    def test_short_and_old_videos_do_not_define_peer_baseline(self):
        entries=[entry(i) for i in range(5)]+[entry('short',1000000,duration=60),entry('old',1000000,upload_date='20260101')]
        self.assertEqual(score_entries(entries,NOW)['0']['baselineViews'],2000)

    def test_missing_metadata_and_sparse_sample_are_labeled_unadjusted(self):
        entries=[entry(i,upload_date='') for i in range(7)]
        self.assertEqual(score_entries(entries,NOW)['0']['scoreBasis'],'unadjusted_channel_sample')
        self.assertEqual(score_entries([entry(1)],NOW)['1']['scoreBasis'],'unadjusted_channel_sample')

    def test_music_and_manual_exclusion_are_not_baseline_peers(self):
        entries=[entry(i) for i in range(5)]+[entry('music',900000,title='888 Hz'),entry('manual',900000,radarOverride='exclude')]
        result=score_entries(entries,NOW)['0']
        self.assertEqual(result['baselineSampleSize'],5)
        self.assertEqual(result['baselineViews'],2000)


if __name__=='__main__':unittest.main()
