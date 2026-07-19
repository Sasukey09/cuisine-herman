"""AI assistant threads are private to their owner, even within one tenant.

Against a real PostgreSQL: two members of the SAME organization must not read,
list or delete each other's assistant conversations (intra-tenant IDOR). Skips
when no DATABASE_URL is set.
"""
import uuid

import pytest

from app.crud import crud_ai_conversation
from app.models.models import AIConversation, Organization, User


def _user(db, tenant_id, email):
    uid = str(uuid.uuid4())
    db.add(User(id=uid, tenant_id=tenant_id, email=email,
                password_hash="$2b$12$fakehashfakehashfakehashfakehashfakehashfake"))
    return uid


@pytest.fixture
def tenant_with_two_users(db):
    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Shared Org"))
    db.commit()
    alice = _user(db, tenant_id, "alice@shared.test")
    bob = _user(db, tenant_id, "bob@shared.test")
    db.commit()

    convo_id = str(uuid.uuid4())
    db.add(AIConversation(id=convo_id, tenant_id=tenant_id, user_id=alice,
                          title="Alice's confidential margin question"))
    db.commit()

    yield tenant_id, alice, bob, convo_id

    org = db.query(Organization).filter(Organization.id == tenant_id).first()
    if org is not None:
        db.delete(org)  # cascades to users + conversations
    db.commit()


def test_a_member_cannot_read_another_members_conversation(tenant_with_two_users, db):
    tenant_id, _alice, bob, convo_id = tenant_with_two_users
    assert crud_ai_conversation.get_conversation(db, tenant_id, convo_id, bob) is None


def test_a_member_does_not_see_another_members_conversation_in_the_list(tenant_with_two_users, db):
    tenant_id, alice, bob, convo_id = tenant_with_two_users
    bob_ids = [str(c.id) for c in crud_ai_conversation.list_conversations(db, tenant_id, bob)]
    alice_ids = [str(c.id) for c in crud_ai_conversation.list_conversations(db, tenant_id, alice)]
    assert convo_id not in bob_ids
    assert convo_id in alice_ids


def test_a_member_cannot_delete_another_members_conversation(tenant_with_two_users, db):
    tenant_id, _alice, bob, convo_id = tenant_with_two_users
    assert crud_ai_conversation.delete_conversation(db, tenant_id, convo_id, bob) is False
    # …and the thread is untouched.
    assert db.query(AIConversation).filter(AIConversation.id == convo_id).first() is not None


def test_the_owner_still_reads_and_deletes_their_own_conversation(tenant_with_two_users, db):
    tenant_id, alice, _bob, convo_id = tenant_with_two_users
    assert crud_ai_conversation.get_conversation(db, tenant_id, convo_id, alice) is not None
    assert crud_ai_conversation.delete_conversation(db, tenant_id, convo_id, alice) is True
    assert db.query(AIConversation).filter(AIConversation.id == convo_id).first() is None
