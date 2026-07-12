"""MS1001 机构权限 — 错题网 JSON 存储（与家教/相亲同一套 owner + admin_usernames 模型）。"""
from __future__ import annotations

import json
import re
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "institutions.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_store() -> dict:
    return {"institutions": [], "members": []}


def load_store() -> dict:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        save_store(_default_store())
        return _default_store()
    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        if "institutions" not in data:
            data["institutions"] = []
        if "members" not in data:
            data["members"] = []
        return data
    except Exception:
        return _default_store()


def save_store(store: dict) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_admins(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [x.strip() for x in re.split(r"[,，;；\s]+", str(raw or "")) if x.strip()]


def slugify(name: str) -> str:
    base = re.sub(r"[\s_]+", "-", name.strip().lower())
    base = re.sub(r"[^a-z0-9\u4e00-\u9fff-]", "", base)
    base = re.sub(r"-+", "-", base).strip("-")
    return base or f"org-{secrets.token_hex(3)}"


def public_institution(inst: dict) -> dict:
    return {
        "id": inst.get("id"),
        "name": inst.get("name"),
        "slug": inst.get("slug"),
        "city": inst.get("city") or "",
        "intro": inst.get("intro") or "",
        "contact_name": inst.get("contact_name") or "",
        "contact_phone": inst.get("contact_phone") or "",
        "owner": inst.get("owner"),
        "admin_usernames": inst.get("admin_usernames") or [],
        "status": inst.get("status") or "active",
        "class_count": int(inst.get("class_count") or 0),
        "member_count": int(inst.get("member_count") or 0),
        "student_count": int(inst.get("student_count") or 0),
        "teacher_count": int(inst.get("teacher_count") or 0),
        "created_at": inst.get("created_at"),
        "updated_at": inst.get("updated_at"),
    }


def public_member(member: dict, inst: dict | None = None) -> dict:
    return {
        "id": member.get("id"),
        "username": member.get("username") or "",
        "name": member.get("name") or "",
        "role": member.get("role") or "student",
        "grade": member.get("grade") or "",
        "class_name": member.get("class_name") or "",
        "phone": member.get("phone") or "",
        "note": member.get("note") or "",
        "institution_id": member.get("institution_id"),
        "institution_name": member.get("institution_name") or (inst or {}).get("name") or "",
        "institution_badge": member.get("institution_badge") or (inst or {}).get("name") or "",
        "status": member.get("status") or "active",
        "created_at": member.get("created_at"),
        "updated_at": member.get("updated_at"),
    }


def is_institution_admin(user: dict | None, inst: dict | None) -> bool:
    if not user or not inst:
        return False
    username = str(user.get("username") or "").strip()
    if not username:
        return False
    if inst.get("owner") == username:
        return True
    return username in (inst.get("admin_usernames") or [])


def get_institution_for_user(store: dict, user: dict | None) -> dict | None:
    if not user:
        return None
    for inst in store.get("institutions") or []:
        if is_institution_admin(user, inst):
            return inst
    return None


def get_institution_by_id(store: dict, inst_id: str) -> dict | None:
    for inst in store.get("institutions") or []:
        if inst.get("id") == inst_id:
            return inst
    return None


def list_institutions(store: dict) -> list[dict]:
    return [public_institution(x) for x in store.get("institutions") or []]


def ensure_unique_slug(store: dict, base: str) -> str:
    used = {x.get("slug") for x in store.get("institutions") or [] if x.get("slug")}
    slug = base
    n = 1
    while slug in used:
        slug = f"{base}-{n}"
        n += 1
    return slug


def create_institution(store: dict, payload: dict, owner: str, created_by: str = "self") -> dict:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("机构名称不能为空")
    owner_name = str(owner or payload.get("owner") or "").strip()
    if not owner_name:
        raise ValueError("须指定机构负责人账号")
    inst_id = str(payload.get("id") or f"org_{uuid.uuid4().hex[:10]}")
    slug = ensure_unique_slug(store, str(payload.get("slug") or slugify(name)))
    admins = parse_admins(payload.get("admin_usernames") or payload.get("admins") or "")
    admin_set = {owner_name, *admins}
    inst = {
        "id": inst_id,
        "name": name,
        "slug": slug,
        "city": str(payload.get("city") or "深圳").strip(),
        "intro": str(payload.get("intro") or "").strip(),
        "contact_name": str(payload.get("contact_name") or "").strip(),
        "contact_phone": str(payload.get("contact_phone") or "").strip(),
        "owner": owner_name,
        "admin_usernames": sorted(admin_set),
        "status": "inactive" if payload.get("status") == "inactive" else "active",
        "class_count": int(payload.get("class_count") or 0),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "created_by": created_by,
    }
    store.setdefault("institutions", []).append(inst)
    return inst


def update_institution(store: dict, inst_id: str, payload: dict, actor: dict | None = None) -> dict:
    inst = get_institution_by_id(store, inst_id)
    if not inst:
        raise ValueError("机构不存在")
    if actor and not is_institution_admin(actor, inst):
        raise PermissionError("无权修改该机构")
    for key in ("name", "city", "intro", "contact_name", "contact_phone"):
        if key in payload and payload[key] is not None:
            inst[key] = str(payload[key]).strip()
    if payload.get("status") in ("active", "inactive"):
        inst["status"] = payload["status"]
    if payload.get("class_count") is not None:
        inst["class_count"] = int(payload.get("class_count") or 0)
    if payload.get("admin_usernames") is not None or payload.get("admins") is not None:
        if actor and inst.get("owner") != str(actor.get("username") or ""):
            raise PermissionError("仅机构负责人可调整协作账号")
        admins = parse_admins(payload.get("admin_usernames") or payload.get("admins") or "")
        inst["admin_usernames"] = sorted({inst.get("owner"), *admins})
    inst["updated_at"] = now_iso()
    return inst


def _refresh_member_counts(store: dict, inst: dict) -> None:
    members = [m for m in store.get("members") or [] if m.get("institution_id") == inst.get("id") and m.get("status") != "deleted"]
    inst["member_count"] = len(members)
    inst["student_count"] = len([m for m in members if m.get("role") == "student"])
    inst["teacher_count"] = len([m for m in members if m.get("role") == "teacher"])
    inst["updated_at"] = now_iso()


def list_members(store: dict, inst: dict) -> list[dict]:
    return [
        public_member(m, inst)
        for m in sorted(
            [x for x in store.get("members") or [] if x.get("institution_id") == inst.get("id") and x.get("status") != "deleted"],
            key=lambda x: x.get("updated_at") or x.get("created_at") or "",
            reverse=True,
        )
    ]


def find_member_by_username(store: dict, username: str) -> dict | None:
    value = str(username or "").strip()
    if not value:
        return None
    aliases = {value, value.lower()}
    if "@" in value:
        aliases.add(value.split("@", 1)[0].lower())
    for member in store.get("members") or []:
        candidate = str(member.get("username") or "").strip()
        if candidate and (candidate in aliases or candidate.lower() in aliases):
            if member.get("status") != "deleted":
                return member
    return None


def upsert_member(store: dict, inst: dict, payload: dict, actor: dict | None = None) -> dict:
    username = str(payload.get("username") or "").strip()
    name = str(payload.get("name") or payload.get("real_name") or username).strip()
    if not username and not name:
        raise ValueError("成员姓名或用户名不能为空")
    member_id = str(payload.get("id") or "").strip()
    member = None
    for item in store.setdefault("members", []):
        if member_id and item.get("id") == member_id and item.get("institution_id") == inst.get("id"):
            member = item
            break
        if username and item.get("username") == username and item.get("institution_id") == inst.get("id"):
            member = item
            break
    now = now_iso()
    if not member:
        member = {
            "id": f"mem_{uuid.uuid4().hex[:10]}",
            "institution_id": inst.get("id"),
            "created_at": now,
        }
        store.setdefault("members", []).append(member)
    member.update({
        "username": username,
        "name": name,
        "role": str(payload.get("role") or "student").strip(),
        "grade": str(payload.get("grade") or "").strip(),
        "class_name": str(payload.get("class_name") or "").strip(),
        "phone": str(payload.get("phone") or "").strip(),
        "note": str(payload.get("note") or "").strip(),
        "institution_name": inst.get("name"),
        "institution_badge": payload.get("institution_badge") or inst.get("name"),
        "status": "inactive" if payload.get("status") == "inactive" else "active",
        "updated_by": (actor or {}).get("username") or "",
        "updated_at": now,
    })
    _refresh_member_counts(store, inst)
    return member


def delete_member(store: dict, inst: dict, member_id: str) -> None:
    for member in store.get("members") or []:
        if member.get("id") == member_id and member.get("institution_id") == inst.get("id"):
            member["status"] = "deleted"
            member["updated_at"] = now_iso()
            _refresh_member_counts(store, inst)
            return
    raise ValueError("成员不存在或不属于本机构")


def unified_user_from_headers(headers) -> dict | None:
    """由 server.py 注入 verify 函数，避免循环导入。"""
    return None


def set_unified_auth_resolver(resolver) -> None:
    global _UNIFIED_AUTH_RESOLVER
    _UNIFIED_AUTH_RESOLVER = resolver


_UNIFIED_AUTH_RESOLVER = None


def resolve_unified_user(headers) -> dict | None:
    if _UNIFIED_AUTH_RESOLVER:
        return _UNIFIED_AUTH_RESOLVER(headers)
    return unified_user_from_headers(headers)


def handle_org_api(method: str, path: str, headers, read_json, require_platform_admin) -> tuple[int, dict] | None:
    """机构 API 分发；返回 (status, payload) 或 None。"""
    user = resolve_unified_user(headers)
    store = load_store()

    if path == "/api/org/me" and method == "GET":
        if not user:
            return 401, {"error": "请先登录统一账号"}
        inst = get_institution_for_user(store, user)
        if not inst:
            return 404, {"error": "尚未注册机构", "need_register": True}
        return 200, {"ok": True, "institution": public_institution(inst), "user": {"username": user["username"]}}

    if path == "/api/org/institutions" and method == "GET":
        visible = [
            public_institution(inst)
            for inst in store.get("institutions") or []
            if inst.get("status") != "inactive"
        ]
        return 200, {"ok": True, "institutions": visible}

    if path == "/api/org/members" and method == "GET":
        if not user:
            return 401, {"error": "请先登录统一账号"}
        inst = get_institution_for_user(store, user)
        if not inst:
            return 404, {"error": "尚未注册机构"}
        return 200, {"ok": True, "members": list_members(store, inst)}

    if path == "/api/org/members" and method == "POST":
        if not user:
            return 401, {"error": "请先登录统一账号"}
        inst = get_institution_for_user(store, user)
        if not inst:
            return 404, {"error": "尚未注册机构"}
        data = read_json()
        member = upsert_member(store, inst, data, user)
        save_store(store)
        return 200, {"ok": True, "member": public_member(member, inst), "members": list_members(store, inst), "institution": public_institution(inst)}

    match = re.fullmatch(r"/api/org/members/([^/]+)/delete", path)
    if match and method == "POST":
        if not user:
            return 401, {"error": "请先登录统一账号"}
        inst = get_institution_for_user(store, user)
        if not inst:
            return 404, {"error": "尚未注册机构"}
        delete_member(store, inst, match.group(1))
        save_store(store)
        return 200, {"ok": True, "members": list_members(store, inst), "institution": public_institution(inst)}

    if path == "/api/org/register" and method == "POST":
        if not user:
            return 401, {"error": "请先登录统一账号"}
        if get_institution_for_user(store, user):
            return 400, {"error": "您已绑定机构，无需重复注册"}
        data = read_json()
        inst = create_institution(store, data, user["username"])
        save_store(store)
        return 201, {"ok": True, "institution": public_institution(inst)}

    if path == "/api/org/me" and method == "POST":
        if not user:
            return 401, {"error": "请先登录统一账号"}
        inst = get_institution_for_user(store, user)
        if not inst:
            return 404, {"error": "尚未注册机构"}
        data = read_json()
        update_institution(store, inst["id"], data, user)
        save_store(store)
        inst = get_institution_by_id(store, inst["id"])
        return 200, {"ok": True, "institution": public_institution(inst)}

    if path == "/api/admin/institutions" and method == "GET":
        if not require_platform_admin():
            return 403, {"error": "需要平台管理员"}
        return 200, {"institutions": list_institutions(store)}

    if path == "/api/admin/institutions" and method == "POST":
        if not require_platform_admin():
            return 403, {"error": "需要平台管理员"}
        data = read_json()
        owner = str(data.get("owner") or data.get("owner_username") or "").strip()
        if not owner:
            return 400, {"error": "须指定 owner 负责人账号"}
        inst = create_institution(store, data, owner, created_by="platform")
        save_store(store)
        return 201, {"ok": True, "institution": public_institution(inst)}

    match = re.fullmatch(r"/api/admin/institutions/([^/]+)", path)
    if match and method == "POST":
        if not require_platform_admin():
            return 403, {"error": "需要平台管理员"}
        data = read_json()
        inst = update_institution(store, match.group(1), data)
        save_store(store)
        return 200, {"ok": True, "institution": public_institution(inst)}

    return None
