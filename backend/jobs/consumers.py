"""
WebSocket consumer for live job execution updates.

A browser connects to ws://.../ws/jobs/<job_public_id>/executions/?token=<token>
- Authenticates via the token in the query string (browsers can't set custom
  headers on the WebSocket handshake, so query-string is the standard workaround).
- Authorizes: the token's user must own the job.
- Subscribes to the job's group; when the executor publishes an execution
  update to that group, this consumer pushes it to the browser.
"""

import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer


class ExecutionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.job_public_id = self.scope["url_route"]["kwargs"]["job_public_id"]
        self.group_name = f"job_{self.job_public_id}"

        # --- Authenticate via token in query string ---
        token_key = self._token_from_query()
        user = await self._user_for_token(token_key)
        if user is None:
            # Reject unauthenticated connections.
            await self.close(code=4001)
            return

        # --- Authorize: user must own this job ---
        owns = await self._user_owns_job(user, self.job_public_id)
        if not owns:
            await self.close(code=4003)
            return

        # --- Subscribe to the job's group and accept the connection ---
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # Send a hello so the client knows the connection is live.
        await self.send(text_data=json.dumps({"type": "connected", "job": self.job_public_id}))

    async def disconnect(self, close_code):
        # Leave the group on disconnect (if we ever joined).
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def execution_update(self, event):
        """
        Handler for messages of type 'execution.update' sent to the group.
        Channels maps the dotted type 'execution.update' to this method name
        'execution_update'. We forward the payload to the browser.
        """
        await self.send(text_data=json.dumps(event["data"]))

    # ---- helpers ----

    def _token_from_query(self):
        query = parse_qs(self.scope.get("query_string", b"").decode())
        tokens = query.get("token", [])
        return tokens[0] if tokens else None

    @database_sync_to_async
    def _user_for_token(self, token_key):
        if not token_key:
            return None
        from rest_framework.authtoken.models import Token

        try:
            return Token.objects.select_related("user").get(key=token_key).user
        except Token.DoesNotExist:
            return None

    @database_sync_to_async
    def _user_owns_job(self, user, job_public_id):
        from jobs.models import Job

        return Job.objects.filter(public_id=job_public_id, owner=user).exists()
