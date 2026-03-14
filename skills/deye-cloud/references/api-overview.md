# Deye Cloud API Overview

## Base URLs

| Region | Base URL |
|--------|----------|
| EU | `https://eu1-developer.deyecloud.com/v1.0` |
| US | `https://us1-developer.deyecloud.com/v1.0` |
| CN | `https://api.deye.com.cn/v1` |

## Authentication Flow

1. **SHA256 hash** the password: `hashlib.sha256(password.encode()).hexdigest()`
2. **POST** `/account/token?appId={appId}` with body:
   ```json
   {
     "appSecret": "...",
     "email": "...",
     "password": "<sha256_hash>",
     "companyId": "0"
   }
   ```
3. Response includes `accessToken` (valid ~60 days) and `expiresIn` (seconds)
4. Use token in all subsequent requests: `Authorization: bearer <token>`

## Token Lifecycle

- Valid for ~60 days from issuance
- Re-requesting does NOT invalidate the previous token
- CLI caches token and expiry in `~/.deye/.env` (auto-refreshes with 1-hour margin)

## Response Envelope

All API responses follow this structure:

```json
{
  "success": true|false,
  "code": "optional_error_code",
  "msg": "optional_message",
  "requestId": "uuid",
  ...data fields...
}
```

## Rate Limits

- No documented official rate limits
- Recommend ≤1 request/second for batch operations
- History endpoints: max 1-year span per request
- Alert endpoints: max 30-day span (device), 180-day (station)

## Common Error Codes

| Code | Meaning |
|------|---------|
| `1000001` | Invalid or expired token |
| `1000002` | Invalid parameter |
| `1000003` | Device not found |
| `1000004` | Permission denied |
