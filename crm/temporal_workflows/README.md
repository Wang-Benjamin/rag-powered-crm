# Temporal Workflows for CRM Schedulers

This directory contains Temporal workflows and activities that replace Google Cloud Scheduler + Cloud Run Jobs for automated CRM tasks.

## Architecture

### Before (Google Cloud Scheduler)
```
Cloud Scheduler → Cloud Run Job (prelude/scripts/) → HTTP POST → CRM Service
```

### After (Temporal)
```
Temporal Schedule → Temporal Workflow (inside CRM service) → Direct function calls
```

Prelude currently uses **one Temporal namespace**. Isolation is encoded with
environment-prefixed queues, schedule IDs, and workflow IDs. Because
local/dev/main share the same database, `APP_ENV=main` is the only environment
that should own recurring summary/signal schedules. Local Temporal workers are
disabled by default.

## Components

### Workflows
- **MultiTenantSummaryWorkflow**: Generates interaction summaries for ALL tenant databases
- **MultiTenantSignalWorkflow**: Evaluates CRM signals for ALL tenant databases

### Activities
- **discover_all_tenants**: Queries `user_profiles` table to find all tenant databases
- **generate_summaries_for_tenant**: Generates summaries for one tenant database
- **evaluate_signals_for_tenant**: Evaluates signals for one tenant database

### Worker
- Runs inside the CRM service process (started in `main.py`)
- Scheduler worker listens on `<env>-crm-schedulers` (main only)
- Mass-email worker listens on `<env>-crm-mass-email`
- Executes workflows and activities

## Schedules

| Schedule | Workflow | Cron | Description |
|----------|----------|------|-------------|
| `main-crm-summary-generation-daily` | MultiTenantSummaryWorkflow | `0 2 * * *` | Generate summaries at 2 AM UTC |
| `main-crm-signal-evaluation-daily` | MultiTenantSignalWorkflow | `0 3 * * *` | Evaluate signals at 3 AM UTC |

## Setup

### 1. Install Dependencies
```bash
cd prelude/prelude-crm
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Ensure `.env` contains Temporal Cloud credentials:
```bash
TEMPORAL_HOST=us-central1.gcp.api.temporal.io:7233
TEMPORAL_NAMESPACE=quickstart-prelude-email-sync.xtjsl
TEMPORAL_API_KEY=eyJhbGciOiJFUzI1NiIsImtpZCI6Ild2dHdhQSJ9...
```

Recommended worker flags:

```bash
# local: no Temporal workers
APP_ENV=local
ENABLE_TEMPORAL_SCHEDULER_WORKER=false
ENABLE_TEMPORAL_MASS_EMAIL_WORKER=false

# dev: email worker only, with safe email-provider/recipient controls
APP_ENV=dev
ENABLE_TEMPORAL_SCHEDULER_WORKER=false
ENABLE_TEMPORAL_MASS_EMAIL_WORKER=true

# main: scheduler owner + email worker
APP_ENV=main
TEMPORAL_SCHEDULER_OWNER=true
ENABLE_TEMPORAL_SCHEDULER_WORKER=true
ENABLE_TEMPORAL_MASS_EMAIL_WORKER=true
```

Legacy `ENABLE_TEMPORAL_WORKER=true` is still recognized for migration, but the
split worker flags should be preferred.

### 3. Start CRM Service
The Temporal worker starts automatically when the CRM service starts:
```bash
python main.py
```

When workers are enabled, you should see:
```
✅ Temporal worker thread started
   App env: main
   Scheduler worker enabled: True
   Mass email worker enabled: True
   Scheduler queue: main-crm-schedulers
   Mass email queue: main-crm-mass-email
```

### 4. Register Schedules (One-time setup)
```bash
cd prelude/prelude-crm
python -m temporal_workflows.register_schedules
```

This creates the daily schedules in Temporal Cloud.

Schedule registration is fail-closed outside `APP_ENV=main`.

If old schedules still exist (`crm-summary-generation-daily`,
`crm-signal-evaluation-daily`), pause them **before** registering the new
`main-*` schedules. Otherwise both will fire against the shared database on
the next cron tick. Recommended order: pause old → register new → verify a
manual run → delete old (or unpause old to roll back).

## Testing

### Manual Workflow Execution
You can trigger workflows manually using the Temporal CLI or Web UI:

**Via Temporal CLI:**
```bash
temporal workflow start \
  --task-queue main-crm-schedulers \
  --type MultiTenantSummaryWorkflow \
  --workflow-id main-test-summary-$(date +%s) \
  --input 'true'  # test_mode=true
```

**Via Temporal Web UI:**
1. Go to https://cloud.temporal.io
2. Navigate to your namespace
3. Click "Start Workflow"
4. Select workflow type: `MultiTenantSummaryWorkflow`
5. Set task queue: `main-crm-schedulers`
6. Set input: `[true]` for test mode

### View Workflow Execution
- **Temporal Web UI**: https://cloud.temporal.io
- **Logs**: Check CRM service logs for activity execution details

## Migration from Google Cloud Scheduler

### What Changed
1. **Scheduler Logic**: Moved from `prelude/scripts/crm_schedulers/` to `prelude/prelude-crm/temporal_workflows/`
2. **Deployment**: No longer need to deploy separate Cloud Run Jobs
3. **Orchestration**: Temporal handles scheduling instead of Google Cloud Scheduler
4. **Communication**: Direct function calls instead of HTTP requests

### What Stayed the Same
1. **Multi-tenant processing**: Still processes ALL tenant databases
2. **Database routing**: Still uses `get_database_for_user(email)` pattern
3. **Business logic**: Same summary generation and deal stage progression services
4. **Timing**: Same schedule (2 AM and 3 AM UTC)

### Benefits
- ✅ Better observability (Temporal Web UI shows workflow execution history)
- ✅ Automatic retries with configurable policies
- ✅ No separate deployment needed (runs inside CRM service)
- ✅ Easier testing (can trigger workflows manually)
- ✅ Durable execution (workflows survive service restarts)

## Troubleshooting

### Worker Not Starting
Check logs for:
```
❌ [Temporal Worker] Missing Temporal configuration in .env
```
Solution: Ensure `TEMPORAL_HOST`, `TEMPORAL_NAMESPACE`, `TEMPORAL_API_KEY` are set in `.env`

### Workflows Not Executing
1. Check worker is running: Look for `✅ Temporal worker started` in logs
2. Check schedules are registered: Run `python -m temporal_workflows.register_schedules`
3. Check Temporal Web UI for workflow execution history

### Activity Failures
- Activities automatically retry on failure (up to 2 attempts)
- Check CRM service logs for detailed error messages
- View workflow execution in Temporal Web UI for retry history

## File Structure
```
temporal_workflows/
├── __init__.py
├── README.md                    # This file
├── worker.py                    # Temporal worker (runs in CRM service)
├── register_schedules.py        # Schedule registration script
├── activities/
│   ├── __init__.py
│   ├── tenant_discovery.py      # Discover all tenant databases
│   ├── summary_generation.py    # Generate summaries for one tenant
│   └── deal_stage_progression.py # Process deal stages for one tenant
└── workflows/
    ├── __init__.py
    ├── multi_tenant_summary_workflow.py      # Summary generation workflow
    └── multi_tenant_deal_stage_workflow.py   # Deal stage progression workflow
```
