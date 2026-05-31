# Specification: Unified Database Support in UI and Serve Scripts

## Objective
Enable the dashboard UI to correctly render broadcast episodes from both local SQLite and remote Supabase databases, and provide convenient npm scripts for serving both environments.

## Scope
- Update `package.json` with dedicated serve scripts.
- Refactor the dashboard UI (`app.js`, `index.html`, `style.css`) to handle local media artifacts (`local://` URIs).
- Ensure `config.js` generation is integrated into the serve workflow.

## Requirements
### 1. NPM Scripts
- `npm run serve:sqlite`: Runs `python sync_config.py --env local` followed by a local web server on port 8080.
- `npm run serve:supabase`: Runs `python sync_config.py --env production` followed by a local web server on port 8080.

### 2. UI Enhancements
- Support `local://` prefix for `audio_url` and `video_url`.
- Resolve `local://` URIs to the `output/` directory (or wherever local artifacts are stored).
- Improve the visual representation when in local mode (e.g., clear status indicator).
- Ensure stats (plays, likes) are handled gracefully if they are missing or different in local mode.

### 3. Backend Consistency
- Ensure `db_client.py` and `sync_config.py` remain the source of truth for database interaction.
