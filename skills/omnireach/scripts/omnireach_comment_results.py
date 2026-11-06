"""Normalize comment reads without confusing missing data with a true empty result."""


def normalize_note_id(url):
    if "note_id=" in url:
        return url.split("note_id=", 1)[1].split("&", 1)[0]
    tail = url.split("/explore/")[-1] if "/explore/" in url else url.rstrip("/").split("/")[-1]
    return tail.split("?", 1)[0]


def aggregate(pages, url, failures=None, idle_stopped=False, page_limit_reached=False):
    comments, order = [], set()
    failures = failures or []
    last_has_more, cursor = None, None

    for body in pages:
        if not isinstance(body, dict):
            failures.append({"type": "invalid_response", "message": "Comment response is not an object"})
            continue
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        if not isinstance(data, dict) or not isinstance(data.get("comments"), list):
            failures.append({"type": "invalid_response", "message": "Comment response has no comments array"})
            continue
        if not isinstance(data.get("has_more"), (bool, int)) or data.get("has_more") not in (False, True, 0, 1):
            failures.append({"type": "invalid_response", "message": "Comment response has no boolean has_more value"})
            continue
        last_has_more = bool(data["has_more"])
        cursor = data.get("cursor") or cursor
        for comment in data["comments"]:
            if not isinstance(comment, dict):
                continue
            cid = comment.get("id")
            if cid and cid in order:
                continue
            if cid:
                order.add(cid)
            comments.append({
                "id": cid,
                "user": (comment.get("user_info") or {}).get("nickname"),
                "content": comment.get("content"),
                "like_count": comment.get("like_count"),
                "ip_location": comment.get("ip_location"),
                "create_time": comment.get("create_time"),
                "sub_comment_count": comment.get("sub_comment_count"),
            })

    complete = last_has_more is False
    if complete:
        stop_reason = "platform_exhausted"
    elif page_limit_reached:
        stop_reason = "page_limit"
    elif idle_stopped and last_has_more is True:
        stop_reason = "no_new_page_after_has_more"
    elif idle_stopped and not pages:
        stop_reason = "no_comment_response"
    elif idle_stopped:
        stop_reason = "pagination_not_confirmed"
    else:
        stop_reason = "pagination_not_confirmed"

    if not pages and failures:
        status = "access_blocked"
    elif complete and not failures:
        status = "success"
    else:
        status = "partial"

    return {
        "note_id": normalize_note_id(url),
        "url": url,
        "pages_fetched": len(pages),
        "comment_count": len(comments),
        "returned_comment_count": len(comments),
        "has_more": last_has_more,
        "cursor": cursor,
        "complete": complete,
        "status": status,
        "stop_reason": stop_reason,
        "errors": failures,
        "comments": comments,
    }
