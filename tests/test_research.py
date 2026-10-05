import copy
import unittest
from research import parse_captions, validate_analysis, analyze_video, generate_analysis, CaptionRateLimited

SEGMENTS = [{'id': 0, 'start': 0, 'end': 5, 'text': 'Your calendar reveals what your priorities really are.'}]
ANALYSIS = {'summary':'A practical opening', 'patterns':[{'kind':'hook', 'observation':'A contrast between intention and action',
            'segmentId':0, 'quote':'Your calendar reveals', 'adaptationIdea':'Ask about the gap between goals and the calendar.'}],
            'cautions':['One excerpt only.']}


class Snapshot:
    def __init__(self, data): self.data = copy.deepcopy(data); self.exists = data is not None
    def to_dict(self): return self.data


class FakeDB:
    def __init__(self): self.data = {}; self.path = ''
    def collection(self, name):
        db = self
        class Collection:
            def document(self, key):
                path = name + '/' + key
                class Ref:
                    def get(self): return Snapshot(db.data.get(path))
                    def set(self, value): db.data[path] = copy.deepcopy(value)
                return Ref()
        return Collection()


class ResearchTests(unittest.TestCase):
    def test_caption_parse(self):
        value = parse_captions({'events':[{'tStartMs':1250,'dDurationMs':1000,'segs':[{'utf8':'Hello  '},{'utf8':'world'}]},
                                          {'segs':[{'utf8':'[Music]'}]}]})
        self.assertEqual(value, [{'id':0,'start':1.25,'end':2.25,'text':'Hello world'}])

    def test_evidence_required(self):
        self.assertEqual(validate_analysis(copy.deepcopy(ANALYSIS), SEGMENTS)['patterns'][0]['start'], 0)
        for quote in ['', 'Invented quote']:
            invalid=copy.deepcopy(ANALYSIS); invalid['patterns'][0]['quote']=quote
            with self.assertRaises(ValueError): validate_analysis(invalid, SEGMENTS)

    def test_no_model_call_for_excluded_or_missing_caption(self):
        db=FakeDB(); vid='abcdefghijk'
        db.data['trend_videos/'+vid]={'title':'888 Hz', 'radarOverride':'exclude'}
        def forbidden(*args): raise AssertionError('Unexpected paid call')
        self.assertEqual(analyze_video(db,vid,forbidden,forbidden)['status'],'excluded')
        db.data['trend_videos/'+vid]={'title':'A talk'}
        self.assertEqual(analyze_video(db,vid,lambda _:None,forbidden)['status'],'needs_transcript')

    def test_cache_prevents_repeated_caption_and_model_calls(self):
        db=FakeDB();vid='abcdefghijk';db.data['trend_videos/'+vid]={'title':'A talk'}
        calls=[]
        def captions(_):
            calls.append('captions');return {'segments':SEGMENTS,'source':'publisher_captions','scope':'excerpt'}
        def model(_): calls.append('model');return copy.deepcopy(ANALYSIS),{'totalTokenCount':100}
        self.assertFalse(analyze_video(db,vid,captions,model)['cached'])
        self.assertTrue(analyze_video(db,vid,captions,model)['cached'])
        self.assertEqual(calls,['captions','model'])

    def test_failed_generation_does_not_cache_findings(self):
        db=FakeDB();vid='abcdefghijk';db.data['trend_videos/'+vid]={'title':'A talk'}
        def failure(_): raise ValueError('failed')
        with self.assertRaises(ValueError):
            analyze_video(db,vid,lambda _: {'segments':SEGMENTS,'source':'captions','scope':'excerpt'},failure)
        self.assertFalse(any(k.startswith('research_analyses/') for k in db.data))

    def test_caption_rate_limit_does_not_trigger_ai(self):
        db=FakeDB();vid='abcdefghijk';db.data['trend_videos/'+vid]={'title':'A talk'}
        def limited(_): raise CaptionRateLimited('Wait before retrying')
        def forbidden(_): raise AssertionError('Unexpected AI request')
        self.assertEqual(analyze_video(db,vid,limited,forbidden)['status'],'rate_limited')
        self.assertFalse(any(k.startswith('research_analyses/') for k in db.data))

    def test_provider_failure_does_not_retry(self):
        class Response: status_code=429
        class Session:
            calls=0
            def post(self,*args,**kwargs): self.calls+=1;return Response()
        session=Session()
        with self.assertRaises(RuntimeError): generate_analysis(SEGMENTS,session)
        self.assertEqual(session.calls,1)


if __name__ == '__main__': unittest.main()
