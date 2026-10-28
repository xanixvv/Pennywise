# Pennywise — Personal Finance & Savings

A local-first personal finance app with a React + TypeScript PWA frontend, FastAPI backend, and SQLite database.

## Requirements
- Python 3.11 or newer
- Node.js 20 or newer (LTS recommended)
- VS Code

## Run on Windows (PowerShell)
Open two terminals in VS Code.

### Terminal 1 — backend
```powershell
cd pennywise
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again. SQLite is created automatically at `backend\data\pennywise.db`.

### Terminal 2 — frontend
```powershell
cd pennywise\frontend
npm install
npm run dev
```
Open the Vite URL printed in the terminal, normally `http://localhost:5173`.

## Main features
- Income, expenses, transfers, edit, delete, duplicate, search, and month filtering
- Multiple accounts with opening balances
- Monthly budgets and savings goals
- Actual-data dashboard, category breakdown, and monthly analytics
- Local rule-based Money Coach (no external AI API)
- CSV transaction export and full JSON backup/restore
- Dark/light theme and responsive PWA shell

## Accounting rules
- Account balance = opening balance + recorded income − recorded expenses + incoming transfers − outgoing transfers.
- Transfers do not count as income or expenses.
- Net savings = recorded income − recorded expenses for the selected month.
- Goal contributions change the goal tracker only; they do not change account balances. A goal allocation is not a bank transfer.
- A zero-income month has an unavailable savings rate.

## iPhone 17
A PWA must be served from HTTPS to install reliably on iPhone. `localhost` on the phone refers to the phone, not your PC. For testing on the same Wi-Fi, the Vite server binds to `0.0.0.0`; use your Windows PC's LAN IPv4 address, e.g. `http://192.168.1.20:5173`, and allow the ports through Windows Firewall. However, that plain HTTP LAN address does not meet iOS's normal secure-context requirement for service workers/PWA installation. For proper installation, expose the site through a trusted HTTPS address on your own network or use a private HTTPS tunnel you control. The API must also be reachable over HTTPS from the phone; set `VITE_API_URL` in `frontend/.env` to the HTTPS API origin plus `/api`, then rebuild. Do not expose this personal finance API to the public internet without authentication and TLS.

Once served over HTTPS: open the site in Safari on the iPhone → Share → Add to Home Screen → Add. The service worker caches the app shell, not live financial API responses. If the backend is offline, cached interface resources may load but financial data operations will not work. Laptop and phone access the same database only while the backend is running and reachable; there is no automatic cloud sync.

## Privacy and backups
The database is stored locally at `backend/data/pennywise.db`. This app does not encrypt that file. Use a protected Windows account and export JSON backups to a safe location. JSON backups contain sensitive financial data.

## Test checklist
1. Add an income transaction with source Parents and verify dashboard income and account balance increase.
2. Add an expense and verify expense total increases and balance decreases.
3. Edit, duplicate, search, filter, and delete a transaction.
4. Transfer between two accounts and verify total balance stays the same and income/expense totals do not change.
5. Create an overall and category budget; verify spend, remaining, and warning percentage.
6. Create a savings goal, contribute and withdraw; verify the goal changes but account balance does not.
7. Add transactions in different months and compare charts/month selector.
8. Export CSV and JSON, then restore the JSON backup into an empty database.
9. Restart both servers and verify records persist.
10. Test narrow mobile layout and install the PWA from Safari over HTTPS.

## Important limitations in this starter release
- Recurring income/expense scheduling and automatic recurring budget carry-forward are not implemented yet; the recurring budget checkbox is currently a stored preference only.
- No transaction-level split payments, scheduled pending income, or automated goal-to-account transfers.
- No login or multi-user authentication. Keep the API on a trusted device/network.
- PWA offline support caches the app shell only, not an offline write queue or SQLite data.
