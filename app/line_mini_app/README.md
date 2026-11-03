# Staff services LINE Mini App

Entry point: `/miniapp/`. Existing MIS staff sessions can use the menu directly.
Otherwise LIFF obtains an ID token and posts it, with a CSRF token, to
`/miniapp/auth`. The backend asks LINE to verify the ID token against
`LINE_MINI_APP_CHANNEL_ID` before looking up `StaffAccount.line_id`.
Only active internal staff may establish a session. Accounts are never linked
automatically: unlinked users are directed to the existing MIS account page.
Existing service routes retain their own permissions.

## Configuration

Set these environment variables on the server and restart the app:

- `LINE_MINI_APP_LIFF_ID`
- `LINE_MINI_APP_CHANNEL_ID`
- `LINE_MINI_APP_CHANNEL_SECRET` (reserved for future server API calls; not needed for ID-token verification)

Use all identifiers from the same Developing, Review, or Published environment.
In LINE Developers, set its HTTPS endpoint to `https://<MIS host>/miniapp/`.
Enable the `openid` scope for ID-token login (recommended). If no ID token is
returned, the app falls back to a server-verified access token with `profile`
scope; its channel ID and expiry are checked before retrieving the profile.
Use the same provider as the existing LINE Login channel so staff LINE IDs match.

## Manual acceptance check

1. Open the Developing Mini App URL in LINE as a linked active staff member.
2. Confirm the menu loads and each service opens with the staff session.
3. Check an unlinked LINE account receives account-linking guidance.
4. Check an inactive/external account is denied.
5. Check mobile layout, check-in location permissions, and returning to the menu.

The menu links to existing MIS screens; those screens have not been redesigned.
No channel access token or service messages are needed for this initial menu.

References:
- https://developers.line.biz/en/docs/liff/using-user-profile/
- https://developers.line.biz/en/reference/line-login/#verify-id-token
