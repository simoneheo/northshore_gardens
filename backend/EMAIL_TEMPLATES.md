# Email Templates and Preview

This backend keeps email copy in JSON template files under:

- `backend/email_templates/`

Each template file has:

- `subject`: email subject text
- `html`: HTML body text

Use `{placeholder_name}` values in both fields. Placeholders are filled in by `main.py`.

## Current templates

- `admin_intake_notification`
- `client_intake_confirmation`
- `admin_contact_notification`
- `client_contact_confirmation`
- `designer_followup`
- `admin_payment_confirmation`
- `client_payment_confirmation`

## Preview templates locally

Run backend:

- `python -m uvicorn main:app --reload --port 8001`

Open preview route:

- `http://localhost:8001/dev/email-preview/<template_name>`

Examples:

- `http://localhost:8001/dev/email-preview/admin_intake_notification`
- `http://localhost:8001/dev/email-preview/client_intake_confirmation`
- `http://localhost:8001/dev/email-preview/admin_contact_notification`
- `http://localhost:8001/dev/email-preview/client_contact_confirmation`
- `http://localhost:8001/dev/email-preview/designer_followup`
- `http://localhost:8001/dev/email-preview/admin_payment_confirmation`
- `http://localhost:8001/dev/email-preview/client_payment_confirmation`

If the template name is invalid, the endpoint returns 404.
