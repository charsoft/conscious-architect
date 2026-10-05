import base64
import io
import unittest
import wave
from transcription import wav_duration,parse_words,store_uploaded_transcript,MODEL
from test_research import FakeDB


def audio():
    target=io.BytesIO()
    with wave.open(target,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\0\0'*16000)
    return target.getvalue()


def response():
    return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'audioTranscription':{'words':[
        {'word':'Hello','startOffset':'0s','endOffset':'0.4s'},
        {'word':'there','startOffset':'0.5s','endOffset':'0.9s'}]}}]}}]}


class TranscriptionTests(unittest.TestCase):
    def test_wav_limits(self):
        self.assertEqual(wav_duration(audio()),1)
        for value in (b'',b'not a wav',audio()[:-2]):
            with self.assertRaises(ValueError):wav_duration(value)

    def test_timestamps_required(self):
        segments=parse_words(response(),1)
        self.assertEqual(segments[0],{'id':0,'text':'Hello there','start':0,'end':0.9})
        broken=response();del broken['candidates'][0]['content']['parts'][0]['audioTranscription']['words'][0]['startOffset']
        with self.assertRaises(ValueError):parse_words(broken,1)
        with self.assertRaises(ValueError):parse_words({'candidates':[]},1)

    def test_confirmation_required(self):
        with self.assertRaises(ValueError):store_uploaded_transcript(FakeDB(),{})

    def test_exclusion_prevents_transcription(self):
        db=FakeDB();vid='abcdefghijk';db.data['trend_videos/'+vid]={'title':'888 Hz'}
        def forbidden(_):raise AssertionError('Unexpected paid call')
        with self.assertRaises(ValueError):store_uploaded_transcript(db,{'videoId':vid,'confirmedSource':True},forbidden)

    def test_upload_cache_and_original_offset(self):
        db=FakeDB();vid='abcdefghijk';db.data['trend_videos/'+vid]={'title':'A teaching'}
        body={'videoId':vid,'confirmedSource':True,'audioBase64':base64.b64encode(audio()).decode(),'startSeconds':30}
        calls=[]
        def transcribe(_):
            calls.append(1);return {'segments':parse_words(response(),1),'model':MODEL,'source':'owner_uploaded_audio','scope':'excerpt'}
        self.assertFalse(store_uploaded_transcript(db,body,transcribe)['cached'])
        self.assertTrue(store_uploaded_transcript(db,body,transcribe)['cached'])
        self.assertEqual(calls,[1])
        self.assertEqual(db.data['research_transcripts/'+vid]['segments'][0]['start'],30)
        body['startSeconds']=40
        with self.assertRaises(ValueError):store_uploaded_transcript(db,body,transcribe)
        self.assertEqual(calls,[1])


if __name__ == '__main__':unittest.main()
