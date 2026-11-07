from __future__ import annotations

import json
import logging
import uuid as uuid_mod
from datetime import UTC, datetime, timedelta
from typing import Any

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from .config import settings

log = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    global _pool
    _pool = AsyncConnectionPool(settings.pg_dsn, min_size=1, max_size=8, open=False)
    await _pool.open()
    await _pool.wait()


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def conn() -> AsyncConnection:
    assert _pool is not None, "pool PostgreSQL non initialisé"
    return _pool.connection()


# ---------- agent_state ----------

async def get_state(project_id: int) -> dict | None:
    async with conn() as c:
        cur = await c.execute(
            "SELECT project_id, status, current_focus, next_action, heartbeat_at, updated_at "
            "FROM agent_state WHERE project_id = %s", (project_id,))
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "project_id": row[0], "status": row[1], "current_focus": row[2],
            "next_action": row[3], "heartbeat_at": row[4], "updated_at": row[5],
        }


async def upsert_state(project_id: int, *, status: str | None = None,
                       current_focus: str | None = None,
                       next_action: dict | None = None,
                       heartbeat: bool = False) -> None:
    async with conn() as c:
        await c.execute(
            """
            INSERT INTO agent_state (project_id, status, current_focus, next_action)
            VALUES (%s, COALESCE(%s, 'IDLE'), %s, %s)
            ON CONFLICT (project_id) DO UPDATE SET
              status        = COALESCE(EXCLUDED.status, agent_state.status),
              current_focus = COALESCE(EXCLUDED.current_focus, agent_state.current_focus),
              next_action   = COALESCE(EXCLUDED.next_action, agent_state.next_action),
              updated_at    = now()
            """,
            (project_id, status, current_focus,
             json.dumps(next_action) if next_action is not None else None))
        if heartbeat:
            await c.execute(
                "UPDATE agent_state SET heartbeat_at = now() WHERE project_id = %s",
                (project_id,))


async def last_heartbeat() -> datetime | None:
    async with conn() as c:
        cur = await c.execute("SELECT max(heartbeat_at) FROM agent_state")
        row = await cur.fetchone()
        return row[0] if row else None


# ---------- agent_actions ----------

async def enqueue_action(project_id: int, action_type: str, payload: dict,
                         scheduled_at: datetime | None = None) -> int:
    async with conn() as c:
        cur = await c.execute(
            "INSERT INTO agent_actions (project_id, type, payload, scheduled_at) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (project_id, action_type, json.dumps(payload),
             scheduled_at or datetime.now(UTC)))
        row = await cur.fetchone()
        return int(row[0])


async def pending_actions(project_id: int | None = None) -> list[dict]:
    async with conn() as c:
        sql = ("SELECT id, project_id, type, payload, status, scheduled_at "
               "FROM agent_actions WHERE status = 'PENDING' AND scheduled_at <= now()")
        params: tuple = ()
        if project_id is not None:
            sql += " AND project_id = %s"
            params = (project_id,)
        sql += " ORDER BY scheduled_at LIMIT 20"
        cur = await c.execute(sql, params)
        rows = await cur.fetchall()
        return [{"id": r[0], "project_id": r[1], "type": r[2],
                 "payload": r[3], "status": r[4], "scheduled_at": r[5]} for r in rows]


async def complete_action(action_id: int, result: dict | None, ok: bool = True) -> None:
    async with conn() as c:
        await c.execute(
            "UPDATE agent_actions SET status = %s, result = %s WHERE id = %s",
            ("DONE" if ok else "FAILED", json.dumps(result or {}), action_id))


async def count_pending_actions() -> int:
    async with conn() as c:
        cur = await c.execute("SELECT count(*) FROM agent_actions WHERE status = 'PENDING'")
        return int((await cur.fetchone())[0])


# ---------- agent_memory ----------

async def write_memory(project_id: int, kind: str, content: str,
                       embedding: list[float] | None = None) -> int:
    async with conn() as c:
        cur = await c.execute(
            "INSERT INTO agent_memory (project_id, kind, content, embedding) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (project_id, kind, content, embedding))
        return int((await cur.fetchone())[0])


async def read_memory(project_id: int, *, query_embedding: list[float] | None = None,
                      query_text: str | None = None, limit: int = 10) -> list[dict]:
    async with conn() as c:
        if query_embedding is not None:
            vector_literal = "[" + ",".join(repr(x) for x in query_embedding) + "]"
            cur = await c.execute(
                "SELECT id, kind, content, created_at FROM agent_memory "
                "WHERE project_id = %s AND embedding IS NOT NULL "
                "ORDER BY embedding <=> %s::vector LIMIT %s",
                (project_id, vector_literal, limit))
        elif query_text:
            cur = await c.execute(
                "SELECT id, kind, content, created_at FROM agent_memory "
                "WHERE project_id = %s AND content ILIKE %s "
                "ORDER BY created_at DESC LIMIT %s",
                (project_id, f"%{query_text}%", limit))
        else:
            cur = await c.execute(
                "SELECT id, kind, content, created_at FROM agent_memory "
                "WHERE project_id = %s ORDER BY created_at DESC LIMIT %s",
                (project_id, limit))
        rows = await cur.fetchall()
        return [{"id": r[0], "kind": r[1], "content": r[2], "created_at": r[3]} for r in rows]


# ---------- subagent_jobs ----------

async def create_job(project_id: int, role: str, provider: str, prompt: str,
                     task_id: int | None = None) -> str:
    job_id = str(uuid_mod.uuid4())
    async with conn() as c:
        await c.execute(
            "INSERT INTO subagent_jobs (id, project_id, role, provider, task_id, prompt, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'CREATED')",
            (job_id, project_id, role, provider, task_id, prompt))
    return job_id


async def update_job(job_id: str, **fields: Any) -> None:
    allowed = {"status", "result", "attempts", "started_at", "last_checked_at", "provider"}
    sets, params = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k} = %s")
        params.append(json.dumps(v) if k == "result" else v)
    if not sets:
        return
    params.append(job_id)
    async with conn() as c:
        # Approved SAST exception EXC-05 (false positive): column names come only
        # from the hard-coded `allowed` set above; values are bound parameters.
        await c.execute(f"UPDATE subagent_jobs SET {', '.join(sets)} WHERE id = %s", params)  # nosemgrep


async def get_job(job_id: str) -> dict | None:
    async with conn() as c:
        cur = await c.execute(
            "SELECT id, project_id, role, provider, task_id, prompt, status, result, "
            "attempts, started_at, last_checked_at FROM subagent_jobs WHERE id = %s",
            (job_id,))
        r = await cur.fetchone()
        if not r:
            return None
        return {"id": str(r[0]), "project_id": r[1], "role": r[2], "provider": r[3],
                "task_id": r[4], "prompt": r[5], "status": r[6], "result": r[7],
                "attempts": r[8], "started_at": r[9], "last_checked_at": r[10]}


async def active_jobs() -> list[dict]:
    async with conn() as c:
        cur = await c.execute(
            "SELECT id, project_id, role, provider, task_id, prompt, status, result, "
            "attempts, started_at, last_checked_at FROM subagent_jobs "
            "WHERE status IN ('CREATED','RUNNING','WAITING')")
        rows = await cur.fetchall()
        return [{"id": str(r[0]), "project_id": r[1], "role": r[2], "provider": r[3],
                 "task_id": r[4], "prompt": r[5], "status": r[6], "result": r[7],
                 "attempts": r[8], "started_at": r[9], "last_checked_at": r[10]}
                for r in rows]


async def count_active_jobs() -> int:
    async with conn() as c:
        cur = await c.execute(
            "SELECT count(*) FROM subagent_jobs WHERE status IN ('CREATED','RUNNING','WAITING')")
        return int((await cur.fetchone())[0])


async def count_failed_jobs_24h() -> int:
    async with conn() as c:
        cur = await c.execute(
            "SELECT count(*) FROM subagent_jobs "
            "WHERE status IN ('FAILED','TIMEOUT') AND last_checked_at > %s",
            (datetime.now(UTC) - timedelta(hours=24),))
        return int((await cur.fetchone())[0])


async def mark_job_checked(job_id: str) -> None:
    await update_job(job_id, last_checked_at=datetime.now(UTC))
