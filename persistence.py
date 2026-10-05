"""Archive the current cloud draft atomically before replacing it."""
from datetime import datetime, timezone
from uuid import uuid4


def should_archive(previous, incoming):
    keys=('title','stage2_signatureJourney','stage3','stage3_masterScript')
    return bool(previous) and any(k in incoming and previous.get(k)!=incoming[k] for k in keys)


def save_with_history(db, doc_id, payload):
    from google.cloud import firestore
    ref=db.collection('video_ideations').document(doc_id)
    revision=ref.collection('revisions').document(uuid4().hex)

    @firestore.transactional
    def save(transaction):
        snapshot=ref.get(transaction=transaction)
        previous=snapshot.to_dict() if snapshot.exists else None
        if should_archive(previous,payload):
            transaction.set(revision,dict(previous,archivedAt=datetime.now(timezone.utc).isoformat()))
        transaction.set(ref,payload,merge=True)

    save(db.transaction())
