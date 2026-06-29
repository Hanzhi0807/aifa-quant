# AIFA Quant Signals Web

Lightweight cloud dashboard for AIFA Quant daily paper-trading signals. It is a React + Vite frontend that reads Supabase tables directly with the anon key. Writes are performed only by `../scripts/push_to_supabase.py` using the Supabase service role key from the project root `.env`.

## Setup

1. Run `../supabase/schema.sql` in the Supabase SQL Editor.
2. Add invited readers to `public.allowed_emails`:

```sql
insert into public.allowed_emails (email, note)
values ('reader@example.com', 'friend');
```

3. Create `signals-web/.env` for local development:

```env
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbG...
```

4. Install and run:

```bash
npm install
npm run dev
```

## Deploy

Deploy this folder to Vercel with:

- Framework: Vite
- Build command: `npm run build`
- Output directory: `dist`

Only set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in Vercel. Never expose `SUPABASE_SERVICE_ROLE_KEY` to the frontend.

## Data Semantics

The signal table shows the current paper-trading holdings ordered by market value, not a full-market prediction universe.
