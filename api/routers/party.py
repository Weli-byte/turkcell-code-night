from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from api.auth_utils import verify_token
from api.notifications_store import push_notification
from database.setup import get_db
from datetime import datetime
import uuid

router = APIRouter(tags=["Watch Party"])


class CreateBody(BaseModel):
    content_id: str


class CodeBody(BaseModel):
    room_code: str = Field(..., min_length=4, max_length=8)


def _room_payload(db, party) -> dict:
    """Oda + içerik + üye listesi. Üye parti dakikaları bugünün DB verisinden."""
    today   = datetime.now().strftime("%Y-%m-%d")
    content = db.execute(
        "SELECT id, title, genre, duration_minutes FROM content_catalog WHERE id=?",
        (party["content_id"],),
    ).fetchone()
    members = db.execute("""
        SELECT wpm.user_id, wpm.joined_at, wpm.left_at, u.username,
               COALESCE((
                   SELECT SUM(ua.watch_party_minutes) FROM user_activities ua
                   WHERE ua.user_id = wpm.user_id AND ua.activity_date = ?
               ), 0) AS party_minutes_today
        FROM watch_party_members wpm
        JOIN users u ON u.id = wpm.user_id
        WHERE wpm.party_id = ?
        ORDER BY wpm.joined_at ASC
    """, (today, party["id"])).fetchall()

    return {
        "party_id":   party["id"],
        "room_code":  party["room_code"],
        "host_user_id": party["host_user_id"],
        "content_id": party["content_id"],
        "content_title": content["title"] if content else "?",
        "is_active":  bool(party["is_active"]),
        "created_at": party["created_at"],
        "ended_at":   party["ended_at"],
        "members": [
            {
                "user_id":  m["user_id"],
                "username": m["username"],
                "is_host":  m["user_id"] == party["host_user_id"],
                "joined_at": m["joined_at"],
                "left":     m["left_at"] is not None,
                "party_minutes_today": round(float(m["party_minutes_today"]), 1),
            }
            for m in members
        ],
    }


def _end_party(db, party_id: str) -> None:
    now_iso = datetime.now().isoformat()
    db.execute(
        "UPDATE watch_parties SET is_active=0, ended_at=? WHERE id=? AND is_active=1",
        (now_iso, party_id),
    )
    db.execute(
        "UPDATE watch_party_members SET left_at=? WHERE party_id=? AND left_at IS NULL",
        (now_iso, party_id),
    )


@router.post("/create")
def create_party(body: CreateBody, token: dict = Depends(verify_token)):
    """Parti odası kur. Önceki aktif host partisi varsa kapatılır."""
    db      = get_db()
    user_id = token["sub"]
    now_iso = datetime.now().isoformat()

    content = db.execute(
        "SELECT id, title FROM content_catalog WHERE id=?", (body.content_id,)
    ).fetchone()
    if not content:
        db.close()
        raise HTTPException(404, "İçerik bulunamadı")

    # Kullanıcının önceki aktif partilerini kapat (host olarak)
    old = db.execute(
        "SELECT id FROM watch_parties WHERE host_user_id=? AND is_active=1", (user_id,)
    ).fetchall()
    for o in old:
        _end_party(db, o["id"])

    party_id  = "wp_" + uuid.uuid4().hex[:12]
    room_code = uuid.uuid4().hex[:6].upper()
    db.execute(
        "INSERT INTO watch_parties (id, room_code, host_user_id, content_id, is_active, created_at) "
        "VALUES (?, ?, ?, ?, 1, ?)",
        (party_id, room_code, user_id, body.content_id, now_iso),
    )
    db.execute(
        "INSERT INTO watch_party_members (party_id, user_id, joined_at) VALUES (?, ?, ?)",
        (party_id, user_id, now_iso),
    )
    db.commit()

    party = db.execute("SELECT * FROM watch_parties WHERE id=?", (party_id,)).fetchone()
    payload = _room_payload(db, party)
    db.close()
    return payload


@router.post("/join")
def join_party(body: CodeBody, token: dict = Depends(verify_token)):
    """Oda koduyla partiye katıl. Tekrar katılım left_at'i sıfırlar."""
    db      = get_db()
    user_id = token["sub"]
    code    = body.room_code.strip().upper()
    now_iso = datetime.now().isoformat()

    party = db.execute(
        "SELECT * FROM watch_parties WHERE room_code=? AND is_active=1", (code,)
    ).fetchone()
    if not party:
        db.close()
        raise HTTPException(404, "Aktif parti bulunamadı — kodu kontrol et")

    existing = db.execute(
        "SELECT id, left_at FROM watch_party_members WHERE party_id=? AND user_id=?",
        (party["id"], user_id),
    ).fetchone()

    is_new = existing is None
    if existing:
        db.execute(
            "UPDATE watch_party_members SET left_at=NULL WHERE id=?", (existing["id"],)
        )
    else:
        db.execute(
            "INSERT INTO watch_party_members (party_id, user_id, joined_at) VALUES (?, ?, ?)",
            (party["id"], user_id, now_iso),
        )
    db.commit()

    # Host'a gerçek zamanlı bildirim (kendine katılımda değil)
    if is_new and party["host_user_id"] != user_id:
        username = db.execute(
            "SELECT username FROM users WHERE id=?", (user_id,)
        ).fetchone()
        push_notification(party["host_user_id"], {
            "type":    "party",
            "message": f"{username['username'] if username else '?'} partine katıldı 🎉",
        })

    payload = _room_payload(db, party)
    db.close()
    return payload


@router.post("/leave")
def leave_party(body: CodeBody, token: dict = Depends(verify_token)):
    """Partiden ayrıl. Host ayrılırsa parti biter."""
    db      = get_db()
    user_id = token["sub"]
    code    = body.room_code.strip().upper()
    now_iso = datetime.now().isoformat()

    party = db.execute(
        "SELECT * FROM watch_parties WHERE room_code=? AND is_active=1", (code,)
    ).fetchone()
    if not party:
        db.close()
        raise HTTPException(404, "Aktif parti bulunamadı")

    if party["host_user_id"] == user_id:
        _end_party(db, party["id"])
        db.commit()
        members = db.execute(
            "SELECT user_id FROM watch_party_members WHERE party_id=? AND user_id != ?",
            (party["id"], user_id),
        ).fetchall()
        db.close()
        for m in members:
            push_notification(m["user_id"], {
                "type": "party", "message": "Parti sona erdi 👋",
            })
        return {"ok": True, "ended": True, "message": "Parti sonlandırıldı"}

    db.execute(
        "UPDATE watch_party_members SET left_at=? WHERE party_id=? AND user_id=? AND left_at IS NULL",
        (now_iso, party["id"], user_id),
    )
    db.commit()
    db.close()
    return {"ok": True, "ended": False, "message": "Partiden ayrıldın"}


@router.post("/end")
def end_party(body: CodeBody, token: dict = Depends(verify_token)):
    """Partiyi bitir — sadece host."""
    db    = get_db()
    code  = body.room_code.strip().upper()
    party = db.execute(
        "SELECT * FROM watch_parties WHERE room_code=? AND is_active=1", (code,)
    ).fetchone()
    if not party:
        db.close()
        raise HTTPException(404, "Aktif parti bulunamadı")
    if party["host_user_id"] != token["sub"]:
        db.close()
        raise HTTPException(403, "Sadece parti kurucusu bitirebilir")

    members = db.execute(
        "SELECT user_id FROM watch_party_members WHERE party_id=? AND user_id != ?",
        (party["id"], token["sub"]),
    ).fetchall()
    _end_party(db, party["id"])
    db.commit()
    db.close()

    for m in members:
        push_notification(m["user_id"], {
            "type": "party", "message": "Parti sona erdi 👋",
        })
    return {"ok": True, "ended": True, "message": "Parti sonlandırıldı"}


@router.get("/room/{room_code}")
def room_status(room_code: str, token: dict = Depends(verify_token)):
    """Oda durumu — üye listesi polling'i için."""
    db    = get_db()
    party = db.execute(
        "SELECT * FROM watch_parties WHERE room_code=?", (room_code.strip().upper(),)
    ).fetchone()
    if not party:
        db.close()
        raise HTTPException(404, "Parti bulunamadı")
    payload = _room_payload(db, party)
    db.close()
    return payload


@router.get("/mine")
def my_party(token: dict = Depends(verify_token)):
    """Kullanıcının aktif partisi (üye veya host)."""
    db    = get_db()
    party = db.execute("""
        SELECT wp.* FROM watch_parties wp
        JOIN watch_party_members wpm ON wpm.party_id = wp.id
        WHERE wpm.user_id = ? AND wpm.left_at IS NULL AND wp.is_active = 1
        ORDER BY wp.created_at DESC LIMIT 1
    """, (token["sub"],)).fetchone()
    if not party:
        db.close()
        return {"active": False, "party": None}
    payload = _room_payload(db, party)
    db.close()
    return {"active": True, "party": payload}
