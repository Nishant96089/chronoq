"""
Tests for the WebSocket ExecutionConsumer: auth, authorization, and that a
group message is forwarded to the connected client.

Uses Channels' WebsocketCommunicator to drive the consumer in-process (no real
socket). The in-memory channel layer is used so tests don't touch Redis.
"""

import pytest
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from chronoq.asgi import application
from jobs.tests.factories import JobFactory, UserFactory

# Use the in-memory channel layer for tests (no Redis dependency).
pytestmark = [pytest.mark.django_db(transaction=True)]


@pytest.fixture(autouse=True)
def inmemory_channel_layer(settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


@sync_to_async
def _make_user_job_token():
    from rest_framework.authtoken.models import Token

    user = UserFactory()
    job = JobFactory(owner=user)
    token = Token.objects.create(user=user)
    return user, job, token.key


@sync_to_async
def _make_other_users_job():
    return JobFactory()  # different owner


class TestExecutionConsumer:
    async def test_authenticated_owner_connects(self):
        user, job, token = await _make_user_job_token()
        url = f"/ws/jobs/{job.public_id}/executions/?token={token}"
        communicator = WebsocketCommunicator(application, url)
        connected, _ = await communicator.connect()
        assert connected is True

        # First message is the 'connected' hello.
        hello = await communicator.receive_json_from()
        assert hello["type"] == "connected"
        assert hello["job"] == str(job.public_id)

        await communicator.disconnect()

    async def test_bad_token_rejected(self):
        _user, job, _token = await _make_user_job_token()
        url = f"/ws/jobs/{job.public_id}/executions/?token=BOGUS"
        communicator = WebsocketCommunicator(application, url)
        connected, _ = await communicator.connect()
        assert connected is False
        await communicator.disconnect()

    async def test_missing_token_rejected(self):
        _user, job, _token = await _make_user_job_token()
        url = f"/ws/jobs/{job.public_id}/executions/"
        communicator = WebsocketCommunicator(application, url)
        connected, _ = await communicator.connect()
        assert connected is False
        await communicator.disconnect()

    async def test_non_owner_rejected(self):
        user, _job, token = await _make_user_job_token()
        other_job = await _make_other_users_job()  # user does NOT own this
        url = f"/ws/jobs/{other_job.public_id}/executions/?token={token}"
        communicator = WebsocketCommunicator(application, url)
        connected, _ = await communicator.connect()
        assert connected is False
        await communicator.disconnect()

    async def test_group_message_forwarded(self):
        user, job, token = await _make_user_job_token()
        url = f"/ws/jobs/{job.public_id}/executions/?token={token}"
        communicator = WebsocketCommunicator(application, url)
        connected, _ = await communicator.connect()
        assert connected is True
        await communicator.receive_json_from()  # consume the hello

        # Publish an execution.update to the job's group; consumer should forward it.
        layer = get_channel_layer()
        await layer.group_send(
            f"job_{job.public_id}",
            {
                "type": "execution.update",
                "data": {"type": "execution_update", "execution": {"status": "success"}},
            },
        )

        msg = await communicator.receive_json_from()
        assert msg["type"] == "execution_update"
        assert msg["execution"]["status"] == "success"

        await communicator.disconnect()
