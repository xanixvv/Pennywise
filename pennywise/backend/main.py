from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pathlib import Path
from datetime import date, datetime
from io import StringIO
import csv, json, sqlite3
from database import init_db, connect, DB_PATH
from schemas import TransactionIn, AccountIn, BudgetIn, GoalIn, GoalContribution, CategoryIn, ImportIn

app = FastAPI(title='Pennywise API', version='1.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://frontend-guke.vercel.app",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event('startup')
def startup(): init_db()

def rows(sql, args=()):
    with connect() as c: return [dict(r) for r in c.execute(sql,args).fetchall()]
def one(sql,args=()):
    data=rows(sql,args); return data[0] if data else None
def valid_date(value):
    try: datetime.strptime(value[:10], '%Y-%m-%d')
    except Exception: raise HTTPException(400, 'Date must use YYYY-MM-DD format.')
    return value[:10]
def month_bounds(month):
    try: datetime.strptime(month,'%Y-%m')
    except Exception: raise HTTPException(400,'Month must use YYYY-MM format.')
    return month+'-01', month+'-31'

@app.get('/api/health')
def health(): return {'status':'ok','database':str(DB_PATH.name)}

@app.get('/api/accounts')
def get_accounts():
    accounts=rows('SELECT * FROM accounts ORDER BY id')
    for a in accounts:
        a['balance']=a['opening_balance'] + (one("SELECT COALESCE(SUM(CASE WHEN kind='income' THEN amount WHEN kind='expense' THEN -amount WHEN kind='transfer' AND to_account_id=? THEN amount WHEN kind='transfer' AND account_id=? THEN -amount ELSE 0 END),0) v FROM transactions WHERE account_id=? OR to_account_id=?",(a['id'],a['id'],a['id'],a['id'])) or {}).get('v',0)
    return accounts
@app.post('/api/accounts')
def create_account(data: AccountIn):
    with connect() as c:
        cur=c.execute('INSERT INTO accounts(name,type,opening_balance) VALUES(?,?,?)',(data.name.strip(),data.type,data.opening_balance))
        return dict(c.execute('SELECT * FROM accounts WHERE id=?',(cur.lastrowid,)).fetchone())
@app.delete('/api/accounts/{account_id}')
def delete_account(account_id:int):
    if one('SELECT id FROM transactions WHERE account_id=? OR to_account_id=?',(account_id,account_id)): raise HTTPException(400,'This account has transactions. Move or delete them before removing the account.')
    with connect() as c: c.execute('DELETE FROM accounts WHERE id=?',(account_id,))
    return {'ok':True}

@app.get('/api/categories')
def get_categories(): return rows('SELECT * FROM categories ORDER BY kind,name')
@app.post('/api/categories')
def create_category(data:CategoryIn):
    try:
        with connect() as c:
            cur=c.execute('INSERT INTO categories(name,kind,color,icon) VALUES(?,?,?,?)',(data.name.strip(),data.kind,data.color,data.icon))
            return dict(c.execute('SELECT * FROM categories WHERE id=?',(cur.lastrowid,)).fetchone())
    except sqlite3.IntegrityError: raise HTTPException(409,'A category with that name already exists.')

@app.get('/api/transactions')
def get_transactions(month:str|None=None, kind:str|None=None, category:str|None=None, q:str|None=None, start:str|None=None, end:str|None=None, limit:int=Query(500,ge=1,le=5000)):
    sql='SELECT t.*, a.name AS account_name, b.name AS to_account_name FROM transactions t LEFT JOIN accounts a ON a.id=t.account_id LEFT JOIN accounts b ON b.id=t.to_account_id WHERE 1=1'; args=[]
    if month: sql+=' AND substr(t.date,1,7)=?'; args.append(month)
    if kind: sql+=' AND t.kind=?'; args.append(kind)
    if category: sql+=' AND t.category=?'; args.append(category)
    if start: sql+=' AND t.date>=?'; args.append(start)
    if end: sql+=' AND t.date<=?'; args.append(end)
    if q: sql+=' AND (t.description LIKE ? OR t.merchant LIKE ? OR t.source LIKE ? OR t.category LIKE ? OR t.notes LIKE ?)'; args += [f'%{q}%']*5
    sql+=' ORDER BY t.date DESC,t.id DESC LIMIT ?'; args.append(limit)
    return rows(sql,args)
@app.post('/api/transactions')
def create_transaction(data:TransactionIn):
    d=valid_date(data.date)
    if data.kind=='transfer':
        if not data.account_id or not data.to_account_id or data.account_id==data.to_account_id: raise HTTPException(400,'Choose two different accounts for a transfer.')
        if not one('SELECT id FROM accounts WHERE id=?',(data.account_id,)) or not one('SELECT id FROM accounts WHERE id=?',(data.to_account_id,)): raise HTTPException(400,'Selected account not found.')
    elif data.account_id and not one('SELECT id FROM accounts WHERE id=?',(data.account_id,)): raise HTTPException(400,'Selected account not found.')
    with connect() as c:
        cur=c.execute('INSERT INTO transactions(kind,amount,date,category,source,merchant,description,payment_method,account_id,to_account_id,tags,notes,goal_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(data.kind,data.amount,d,data.category,data.source,data.merchant,data.description,data.payment_method,data.account_id,data.to_account_id,data.tags,data.notes,data.goal_id))
        return dict(c.execute('SELECT * FROM transactions WHERE id=?',(cur.lastrowid,)).fetchone())
@app.put('/api/transactions/{transaction_id}')
def update_transaction(transaction_id:int,data:TransactionIn):
    if not one('SELECT id FROM transactions WHERE id=?',(transaction_id,)): raise HTTPException(404,'Transaction not found.')
    d=valid_date(data.date)
    if data.kind=='transfer' and (not data.account_id or not data.to_account_id or data.account_id==data.to_account_id): raise HTTPException(400,'Transfers need two different accounts.')
    with connect() as c:
        c.execute('UPDATE transactions SET kind=?,amount=?,date=?,category=?,source=?,merchant=?,description=?,payment_method=?,account_id=?,to_account_id=?,tags=?,notes=?,goal_id=? WHERE id=?',(data.kind,data.amount,d,data.category,data.source,data.merchant,data.description,data.payment_method,data.account_id,data.to_account_id,data.tags,data.notes,data.goal_id,transaction_id))
    return one('SELECT * FROM transactions WHERE id=?',(transaction_id,))
@app.delete('/api/transactions/{transaction_id}')
def delete_transaction(transaction_id:int):
    with connect() as c: c.execute('DELETE FROM transactions WHERE id=?',(transaction_id,))
    return {'ok':True}
@app.post('/api/transactions/{transaction_id}/duplicate')
def duplicate_transaction(transaction_id:int):
    t=one('SELECT * FROM transactions WHERE id=?',(transaction_id,))
    if not t: raise HTTPException(404,'Transaction not found.')
    with connect() as c:
        cur=c.execute('INSERT INTO transactions(kind,amount,date,category,source,merchant,description,payment_method,account_id,to_account_id,tags,notes,goal_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(t['kind'],t['amount'],date.today().isoformat(),t['category'],t['source'],t['merchant'],t['description'],t['payment_method'],t['account_id'],t['to_account_id'],t['tags'],t['notes'],t['goal_id']))
    return one('SELECT * FROM transactions WHERE id=?',(cur.lastrowid,))

@app.get('/api/budgets')
def get_budgets(month:str):
    start,end=month_bounds(month)
    budgets=rows('SELECT * FROM budgets WHERE month=? ORDER BY category',(month,))
    for b in budgets:
        if b['category']=='All expenses': sql='SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE kind=\'expense\' AND date BETWEEN ? AND ?'; args=(start,end)
        else: sql='SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE kind=\'expense\' AND category=? AND date BETWEEN ? AND ?'; args=(b['category'],start,end)
        b['spent']=(one(sql,args) or {}).get('n',0); b['remaining']=b['amount']-b['spent']; b['percent']=round(b['spent']/b['amount']*100,1)
    return budgets
@app.post('/api/budgets')
def save_budget(data:BudgetIn):
    with connect() as c:
        c.execute('INSERT INTO budgets(month,category,amount,recurring) VALUES(?,?,?,?) ON CONFLICT(month,category) DO UPDATE SET amount=excluded.amount,recurring=excluded.recurring',(data.month,data.category,data.amount,int(data.recurring)))
    return one('SELECT * FROM budgets WHERE month=? AND category=?',(data.month,data.category))
@app.delete('/api/budgets/{budget_id}')
def delete_budget(budget_id:int):
    with connect() as c: c.execute('DELETE FROM budgets WHERE id=?',(budget_id,))
    return {'ok':True}

@app.get('/api/goals')
def get_goals():
    goals=rows('SELECT * FROM goals ORDER BY CASE priority WHEN \'High\' THEN 1 WHEN \'Medium\' THEN 2 ELSE 3 END,id DESC')
    for g in goals: g['remaining']=max(0,g['target_amount']-g['saved_amount']); g['percent']=min(100,round(g['saved_amount']/g['target_amount']*100,1))
    return goals
@app.post('/api/goals')
def create_goal(data:GoalIn):
    with connect() as c:
        cur=c.execute('INSERT INTO goals(name,target_amount,saved_amount,target_date,priority,icon,notes) VALUES(?,?,?,?,?,?,?)',(data.name,data.target_amount,data.saved_amount,data.target_date,data.priority,data.icon,data.notes))
    return one('SELECT * FROM goals WHERE id=?',(cur.lastrowid,))
@app.put('/api/goals/{goal_id}')
def update_goal(goal_id:int,data:GoalIn):
    with connect() as c: c.execute('UPDATE goals SET name=?,target_amount=?,saved_amount=?,target_date=?,priority=?,icon=?,notes=? WHERE id=?',(data.name,data.target_amount,data.saved_amount,data.target_date,data.priority,data.icon,data.notes,goal_id))
    return one('SELECT * FROM goals WHERE id=?',(goal_id,))
@app.post('/api/goals/{goal_id}/contribute')
def contribute(goal_id:int,data:GoalContribution):
    goal=one('SELECT * FROM goals WHERE id=?',(goal_id,))
    if not goal: raise HTTPException(404,'Goal not found.')
    amount=goal['saved_amount']+data.amount if data.action=='add' else goal['saved_amount']-data.amount
    if amount<0: raise HTTPException(400,'You cannot withdraw more than the goal currently holds.')
    with connect() as c: c.execute('UPDATE goals SET saved_amount=? WHERE id=?',(amount,goal_id))
    return one('SELECT * FROM goals WHERE id=?',(goal_id,))
@app.delete('/api/goals/{goal_id}')
def delete_goal(goal_id:int):
    with connect() as c: c.execute('DELETE FROM goals WHERE id=?',(goal_id,))
    return {'ok':True}

@app.get('/api/dashboard')
def dashboard(month:str):
    start,end=month_bounds(month)
    income=(one("SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE kind='income' AND date BETWEEN ? AND ?",(start,end)) or {})['n']
    expenses=(one("SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE kind='expense' AND date BETWEEN ? AND ?",(start,end)) or {})['n']
    prev=datetime.strptime(month+'-01','%Y-%m-%d').date().replace(day=1)
    prev_month=(prev.replace(day=1)-__import__('datetime').timedelta(days=1)).strftime('%Y-%m')
    ps,pe=month_bounds(prev_month)
    prev_income=(one("SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE kind='income' AND date BETWEEN ? AND ?",(ps,pe)) or {})['n']
    prev_expenses=(one("SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE kind='expense' AND date BETWEEN ? AND ?",(ps,pe)) or {})['n']
    accounts=get_accounts()
    opening_total=(one('SELECT COALESCE(SUM(opening_balance),0) n FROM accounts') or {})['n']
    all_income=(one("SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE kind='income'") or {})['n']
    all_expenses=(one("SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE kind='expense'") or {})['n']
    balance=opening_total+all_income-all_expenses
    budgets=get_budgets(month); budget_total=sum(b['amount'] for b in budgets if b['category']=='All expenses')
    cats=rows("SELECT category,SUM(amount) amount FROM transactions WHERE kind='expense' AND date BETWEEN ? AND ? GROUP BY category ORDER BY amount DESC",(start,end))
    recent=rows('SELECT * FROM transactions ORDER BY date DESC,id DESC LIMIT 6')
    goals=get_goals()
    return {'month':month,'balance':balance,'income':income,'expenses':expenses,'net_savings':income-expenses,'savings_rate':round((income-expenses)/income*100,1) if income>0 else None,'previous':{'income':prev_income,'expenses':prev_expenses,'net_savings':prev_income-prev_expenses},'budget_remaining':budget_total-(expenses if budget_total else 0) if budget_total else None,'categories':cats,'recent':recent,'goals':goals,'accounts':accounts,'transaction_count':(one('SELECT COUNT(*) n FROM transactions') or {})['n']}
@app.get('/api/analytics')
def analytics(months:int=12):
    allmonths=rows("SELECT substr(date,1,7) month, SUM(CASE WHEN kind='income' THEN amount ELSE 0 END) income, SUM(CASE WHEN kind='expense' THEN amount ELSE 0 END) expenses FROM transactions WHERE kind IN ('income','expense') GROUP BY substr(date,1,7) ORDER BY month DESC LIMIT ?",(months,))
    allmonths=list(reversed(allmonths))
    for m in allmonths: m['net_savings']=m['income']-m['expenses']; m['savings_rate']=round(m['net_savings']/m['income']*100,1) if m['income']>0 else None
    return {'months':allmonths}
@app.get('/api/coach')
def coach(month:str):
    start,end=month_bounds(month); messages=[]
    inc=(one("SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE kind='income' AND date BETWEEN ? AND ?",(start,end)) or {})['n']
    exp=(one("SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE kind='expense' AND date BETWEEN ? AND ?",(start,end)) or {})['n']
    count=(one("SELECT COUNT(*) n FROM transactions WHERE kind='expense' AND date BETWEEN ? AND ?",(start,end)) or {})['n']
    cats=rows("SELECT category,SUM(amount) amount FROM transactions WHERE kind='expense' AND date BETWEEN ? AND ? GROUP BY category ORDER BY amount DESC",(start,end))
    if count==0: messages.append({'type':'start','title':'Your story starts with one entry','body':'Add a few real transactions and Pennywise will find patterns without guessing.'})
    else:
        if inc>0: messages.append({'type':'good' if exp<inc else 'notice','title':f'Net cash flow: ₹{inc-exp:,.0f}','body':f'Based on recorded income of ₹{inc:,.0f} and expenses of ₹{exp:,.0f} for {month}.'})
        if cats:
            share=cats[0]['amount']/exp*100 if exp else 0
            messages.append({'type':'insight','title':f'{cats[0]["category"]} is your largest category','body':f'₹{cats[0]["amount"]:,.0f}, or {share:.0f}% of recorded spending this month. If you want to save more, choose a realistic limit for this category.'})
        if len(cats)>=2: messages.append({'type':'tip','title':'Pick one small adjustment','body':f'Try reducing {cats[0]["category"]} by 10% next month. That would free up about ₹{cats[0]["amount"]*0.1:,.0f}, if the same spending pattern repeats.'})
    budgets=get_budgets(month)
    for b in budgets:
        if b['percent']>=80: messages.append({'type':'notice','title':f'{b["category"]} budget at {b["percent"]:.0f}%','body':f'You have spent ₹{b["spent"]:,.0f} of ₹{b["amount"]:,.0f}. Remaining: ₹{b["remaining"]:,.0f}. This is based on transactions recorded so far.'})
    return {'month':month,'insights':messages,'data_points':count}

@app.get('/api/export/json')
def export_json():
    with connect() as c:
        data={table:[dict(r) for r in c.execute(f'SELECT * FROM {table}').fetchall()] for table in ['accounts','categories','transactions','budgets','goals','settings']}
    data['format']='pennywise-backup-v1'; data['exported_at']=datetime.now().isoformat(timespec='seconds')
    return data
@app.get('/api/export/csv')
def export_csv():
    data=rows('SELECT * FROM transactions ORDER BY date DESC,id DESC'); output=StringIO(); fields=list(data[0].keys()) if data else ['id','kind','amount','date','category','source','merchant','description','payment_method','account_id','to_account_id','tags','notes','goal_id']
    writer=csv.DictWriter(output,fieldnames=fields); writer.writeheader(); writer.writerows(data)
    return StreamingResponse(iter([output.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=pennywise-transactions.csv'})
@app.post('/api/import/json')
def import_json(data:ImportIn):
    backup=data.backup
    if backup.get('format')!='pennywise-backup-v1': raise HTTPException(400,'This file is not a supported Pennywise backup.')
    required={'accounts','categories','transactions','budgets','goals','settings'}
    if not required.issubset(backup): raise HTTPException(400,'Backup is missing one or more required data sections.')
    try:
        with connect() as c:
            if not data.replace_existing and c.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]>0: raise HTTPException(409,'Existing transactions were found. Confirm replace-existing to restore this backup.')
            if data.replace_existing:
                for table in ['transactions','budgets','goals','categories','accounts','settings']: c.execute(f'DELETE FROM {table}')
            for table in ['accounts','categories','transactions','budgets','goals','settings']:
                cols=[r[1] for r in c.execute(f'PRAGMA table_info({table})').fetchall()]
                for item in backup[table]:
                    valid={k:v for k,v in item.items() if k in cols}
                    if valid:
                        keys=list(valid); c.execute(f"INSERT INTO {table} ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",[valid[k] for k in keys])
    except HTTPException: raise
    except Exception as e: raise HTTPException(400,f'Backup could not be imported: {e}')
    return {'ok':True,'message':'Backup restored.'}
@app.get('/api/settings')
def get_settings(): return {r['key']:r['value'] for r in rows('SELECT * FROM settings')}
@app.put('/api/settings/{key}')
def set_setting(key:str,value:str=Body(...)):
    if key not in {'currency','theme','minimum_balance'}: raise HTTPException(400,'Unsupported setting.')
    with connect() as c: c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))
    return {'key':key,'value':value}
