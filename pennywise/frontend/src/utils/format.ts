export const money = (n:number) => new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits: n%1===0?0:2}).format(n||0);
export const monthNow = () => { const d=new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`; };
export const monthLabel = (m:string) => { if(!m) return ''; const [y,mo]=m.split('-').map(Number); return new Date(y,mo-1,1).toLocaleDateString('en-IN',{month:'long',year:'numeric'}); };
export const dateLabel = (d:string) => d ? new Date(`${d.slice(0,10)}T12:00:00`).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'}) : '—';
