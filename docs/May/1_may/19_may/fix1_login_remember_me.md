# Fix 1 — Login Password Reset + Remember Me Checkbox

**Date:** 2026-05-19
**Author:** Vidhi
**Branch:** Vidhi
**Status:** Done (uncommitted)

---

## What type of task is this?

**Frontend + Backend — authentication improvement.**

---

## What was the problem?

Two problems with login:

**Problem 1 — Unknown password:** The admin account password was auto-generated on first startup and stored as a bcrypt hash. Nobody knew what it was. Every session started with "Invalid credentials."

**Problem 2 — No remember me:** Even after logging in successfully, the session lasted only 8 hours. There was no way to stay signed in longer. Users had to log in again every day.

---

## How does this relate to the existing codebase?

Login is handled by `backend/modules/auth/routes.py`. Tokens are created in `backend/modules/auth/security.py`. The login page is `frontend/src/app/(auth)/login/page.tsx`.

The backend already had `ACCESS_TOKEN_EXPIRE_MINUTES = 480` (8 hours). It just needed a longer option and a way for the user to choose it.

---

## What changed and why

### Fix 1 — Password reset (one-time DB operation)

Reset the admin password directly in PostgreSQL using a known bcrypt hash of `admin123`:

```sql
UPDATE users SET hashed_password = '<bcrypt hash>' WHERE email = 'admin@apihub.com';
```

This is a one-time setup step, not a code change.

---

### Fix 2 — Remember me duration

**File:** `backend/modules/auth/security.py`

```python
# Added
REMEMBER_TOKEN_EXPIRE_MINUTES = 1080    # 18 hours
```

---

### Fix 3 — Login request accepts remember_me flag

**File:** `backend/modules/auth/schemas.py`

```python
class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False   # ← added
```

---

### Fix 4 — Login route uses correct expiry

**File:** `backend/modules/auth/routes.py`

```python
expire = REMEMBER_TOKEN_EXPIRE_MINUTES if body.remember_me else ACCESS_TOKEN_EXPIRE_MINUTES
_set_auth_cookie(response, create_access_token(payload, expire_minutes=expire), max_age_minutes=expire)
```

When the user checks "Remember me", the cookie lives for 18 hours. Otherwise 8 hours.

---

### Fix 5 — Checkbox on login page

**File:** `frontend/src/app/(auth)/login/page.tsx`

Added a checkbox (checked by default) that sends `remember_me: true` in the POST body:

```tsx
<label>
  <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} />
  Keep me signed in for 18 hours
</label>
```

---

## Files changed

| File | Change |
|------|--------|
| `backend/modules/auth/security.py` | Added `REMEMBER_TOKEN_EXPIRE_MINUTES = 1080` |
| `backend/modules/auth/schemas.py` | Added `remember_me: bool = False` to `LoginRequest` |
| `backend/modules/auth/routes.py` | Login route picks correct expiry based on `remember_me` |
| `frontend/src/app/(auth)/login/page.tsx` | Added remember me checkbox (default checked) |

---

## Manual Test Steps

1. Go to `http://localhost:3000/login`
2. Enter `admin@apihub.com` / `admin123`
3. "Keep me signed in for 18 hours" checkbox should be visible and checked by default
4. Click Sign in → should land on dashboard
5. Check browser devtools → Application → Cookies → `auth_token` cookie `Max-Age` should be `64800` (18 hours in seconds)
