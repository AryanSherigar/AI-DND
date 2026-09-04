# TRS Architecture — Session & Real-Time State

This document details the in-memory pub/sub dispatchers and access validation utilities in `apps/turn-resolution-service/app/session/`.

---

## 1. Overview & Single-Process Scope

To enable real-time multiplayer coordination and live spectator streaming without introducing an external message broker (e.g. Redis) during initial deployment, TRS implements high-performance in-memory async queues (`asyncio.Queue`) keyed by playthrough and participant identifiers.

```mermaid
flowchart TD
    subgraph TRSInProcess["TRS Process Memory"]
        Pipeline["app/turn/pipeline.py"]
        SpectatorMgr["spectator_manager.py<br/>dict[playthrough_id, list[Queue]]"]
        NotificationMgr["notification_manager.py<br/>dict[(playthrough_id, participant_id), Queue]"]
    end

    subgraph ClientConnections["SSE Client Connections"]
        Spectator1["Spectator Browser 1<br/>GET /session/{id}/spectate"]
        Spectator2["Spectator Browser 2<br/>GET /session/{id}/spectate"]
        PlayerTurn["Next Participant<br/>GET /session/{id}/notifications"]
    end

    Pipeline -->|publish() turn tokens & events| SpectatorMgr
    Pipeline -->|notify_next_turn() / notify_ended()| NotificationMgr

    SpectatorMgr -->|Relays event tuples| Spectator1
    SpectatorMgr -->|Relays event tuples| Spectator2
    NotificationMgr -->|Relays 'your_turn' event| PlayerTurn
```

---

## 2. File Profiles

### `apps/turn-resolution-service/app/session/spectator_manager.py`
- **Purpose & Layer:** Live spectator broadcasting manager.
- **Key Functions:**
  - `subscribe(playthrough_id: UUID) -> asyncio.Queue`: Registers a new spectator listener queue for a game session.
  - `unsubscribe(playthrough_id: UUID, queue: asyncio.Queue) -> None`: Removes queue upon client disconnection to prevent memory leaks.
  - `publish(playthrough_id: UUID, event_name: str, data: str) -> None`: Asynchronously fans out live narration chunks and game outcomes to all active spectator queues for that session.
- **Architecture Rules & Invariants:** Ephemeral in-memory pub/sub. Spectator dropouts do not impede the turn pipeline.

### `apps/turn-resolution-service/app/session/notification_manager.py`
- **Purpose & Layer:** Participant turn alerts and session termination broadcast manager.
- **Key Functions:**
  - `subscribe(playthrough_id, participant_id) -> asyncio.Queue`: Enrolls a player's long-lived notification channel.
  - `unsubscribe(playthrough_id, participant_id) -> None`: Cleanup handler.
  - `notify_next_turn(playthrough_id, next_participant_id) -> None`: Pushes `"your_turn"` alert when turn order advances.
  - `notify_playthrough_ended(playthrough_id, outcome_title) -> None`: Broadcasts `"playthrough_ended"` to all active participants.
- **Architecture Rules & Invariants:** Safe no-op if a participant is not connected; players synchronize state on next fetch.

### `apps/turn-resolution-service/app/session/access.py`
- **Purpose & Layer:** Permission verification for session SSE streaming.
- **Key Functions:**
  - `validate_spectate_access(playthrough_id, share_token, session) -> None`: Validates share token against `ShareRepo`. Verifies token matches `mode == "spectate"` and has not expired.
  - `validate_notification_access(playthrough_id, participant_id, user_id, session) -> None`: Validates via `ParticipantRepo` that the participant record belongs to the calling user.
- **Dependencies & Interactions:** Instantiates `ShareRepo` and `ParticipantRepo`. Routers never invoke repositories directly.

### `apps/turn-resolution-service/app/session/turn_counter.py`
- **Purpose & Layer:** Turn tracking placeholder; milestone counter logic is consolidated directly in `app/turn/steps/state_writer.py` to maintain atomic transactional guarantees when writing turns to PostgreSQL.
