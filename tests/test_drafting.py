import copy
import unittest
from drafting import FIELDS, validate_request, validate_output, create_draft, load_research
from persistence import should_archive
from test_research import FakeDB

BEATS={k:'Current '+k for k in FIELDS}
BODY={'action':'options','episodeId':'episode-1','title':'A conscious week','blueprint':BEATS,'analysisIds':[]}


def options():
    return {'options':[{'title':'Title '+str(i),'hook':'Opening '+str(i),'rationale':'Contrast',
                        'keywords':['agency'],'sourceIds':[], 'blueprint':dict(BEATS,beat6='invented story',bridge_limit='removed caveat')}
                       for i in range(3)]}


def narration():
    return {'sections':[{'beat':i,'name':'Section','spoken':'Drafted narration','notes':'Camera note'} for i in range(1,8)],
            'reviewNotes':['Check factual claims.']}


class DraftTests(unittest.TestCase):
    def test_narration_needs_explicit_approval_and_current_schema(self):
        body=dict(BODY,action='narration')
        with self.assertRaises(ValueError): validate_request(body)
        body['approved']=True
        self.assertEqual(validate_request(body),BEATS)
        body['blueprint']={'hook05':'old schema'}
        with self.assertRaises(ValueError): validate_request(body)

    def test_missing_beats_and_invalid_references_rejected(self):
        body=copy.deepcopy(BODY);body['blueprint']['bridge_limit']=''
        with self.assertRaises(ValueError): validate_request(body)
        with self.assertRaises(ValueError): validate_request(dict(BODY,analysisIds=['unknown']))

    def test_options_preserve_story_and_limit(self):
        result=validate_output('options',options(),BEATS,[])
        for option in result['options']:
            self.assertEqual(option['blueprint']['beat6'],BEATS['beat6'])
            self.assertEqual(option['blueprint']['bridge_limit'],BEATS['bridge_limit'])
            self.assertEqual(option['blueprint']['beat1'],option['hook'])

    def test_fabricated_source_rejected(self):
        result=options();result['options'][0]['sourceIds']=['fake']
        with self.assertRaises(ValueError): validate_output('options',result,BEATS,[])

    def test_narration_preserves_opening_story_limit_and_separates_notes(self):
        result=validate_output('narration',narration(),BEATS,[])
        self.assertEqual(result['sections'][0]['spoken'],BEATS['beat1'])
        self.assertEqual(result['sections'][5]['spoken'],BEATS['beat6'])
        self.assertIn(BEATS['bridge_limit'],result['sections'][3]['spoken'])
        self.assertNotIn('Camera note',result['sections'][0]['spoken'])
        self.assertGreater(result['wordCount'],0)
        with self.assertRaises(ValueError): validate_output('narration',{'sections':[]},BEATS,[])

    def test_blank_story_requires_owner_placeholder(self):
        result=validate_output('narration',narration(),dict(BEATS,beat6=''),[])
        self.assertEqual(result['sections'][5]['spoken'],'[ADD YOUR OWN TRUE STORY HERE]')

    def test_cache_and_episode_safety(self):
        db=FakeDB();db.data['video_ideations/episode-1']={'stage3':'My manual script'}
        calls=[]
        def model(*args,**kwargs): calls.append(1);return options(),{'totalTokenCount':1}
        first=create_draft(db,BODY,model)
        second=create_draft(db,BODY,model)
        self.assertFalse(first['cached']);self.assertTrue(second['cached']);self.assertEqual(len(calls),1)
        self.assertEqual(db.data['video_ideations/episode-1']['stage3'],'My manual script')
        self.assertIn('No research supplied',first['researchStatus'])
        self.assertEqual(first['voiceVersion'],'voice-v1')

    def test_excluded_research_cannot_shape_script(self):
        db=FakeDB();key='a'*64
        db.data['research_analyses/'+key]={'videoId':'abcdefghijk'}
        db.data['trend_videos/abcdefghijk']={'title':'888 Hz'}
        with self.assertRaises(ValueError): load_research(db,[key])

    def test_cloud_revision_rules(self):
        self.assertTrue(should_archive({'stage3':['old']},{'stage3':['new']}))
        self.assertFalse(should_archive({'stage3':['old']},{'stage3':['old'],'lastUpdated':'now'}))
        self.assertFalse(should_archive(None,{'stage3':['new']}))


if __name__ == '__main__': unittest.main()
