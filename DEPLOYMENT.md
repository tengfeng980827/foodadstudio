# Food AI Studio Deployment

## Railway variables

Set these in Railway Project > Service > Variables:

```env
OPENAI_API_KEY=your_openai_key
OPENAI_IMAGE_MODEL=gpt-image-2
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
SUPABASE_STORAGE_BUCKET=generated-images
```

Do not commit real keys to GitHub.

## Supabase setup

1. Open Supabase SQL Editor.
2. Run `supabase_setup.sql`.
3. Confirm Storage has a public bucket named `generated-images`.
4. In Authentication settings, enable Email/Password sign-in.

## Railway setup

1. Create a Railway project from the GitHub repo.
2. Select this repo: `tengfeng980827/foodadstudio`.
3. Railway should use the `Procfile`:

```text
web: gunicorn app:app --bind 0.0.0.0:$PORT --timeout 300 --workers 1
```

4. Add the variables above.
5. Deploy and open `/health`.

Expected `/health`:

```json
{
  "success": true,
  "openai_configured": true,
  "supabase_configured": true,
  "supabase_service_configured": true
}
```
