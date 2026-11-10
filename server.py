"""Small dependency-free web application for coursework. Run: python server.py"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from datetime import date, datetime
from zoneinfo import ZoneInfo
import json, os, re, secrets, threading

BASE=Path(__file__).resolve().parent
DATA=BASE/'data'/'bookings.jsonl'
LOCK=threading.Lock()
ROSTER=[{'day':'Monday','person':'Owner 1 + Employee 1','hours':'9:00–17:00'}, {'day':'Tuesday','person':'Owner 2 + Employee 2','hours':'9:00–17:00'}, {'day':'Wednesday','person':'Owner 1 + Employee 2','hours':'9:00–17:00'}, {'day':'Thursday','person':'Owner 2 + Employee 1','hours':'9:00–17:00'}, {'day':'Friday','person':'Both owners + Employees','hours':'9:00–17:00'}, {'day':'Saturday','person':'Owner 1 + Employee 1','hours':'9:00–17:00'}]
SERVICES={'Bath and brush','Haircut','Nail trim','Ear cleaning','Teeth brushing','De-shedding treatment','Flea and tick treatment','Spa package','Express service','Medicated bath','Special-breed cuts','Puppy package','Senior dog package','Full grooming package'}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(BASE/'site'),**kwargs)
    def send_json(self,status,value):
        raw=json.dumps(value).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if urlparse(self.path).path=='/api/roster':
            secret=os.environ.get('STAFF_ACCESS_CODE')
            if not secret:return self.send_json(503,{'error':'Staff access has not been configured.'})
            if not secrets.compare_digest(self.headers.get('X-Staff-Code',''),secret):return self.send_json(403,{'error':'Invalid staff access code.'})
            return self.send_json(200,{'roster':ROSTER})
        return super().do_GET()
    def do_POST(self):
        if urlparse(self.path).path!='/api/bookings':return self.send_json(404,{'error':'Not found'})
        try:
            n=int(self.headers.get('Content-Length','0'))
            if n<2 or n>6000:return self.send_json(413,{'error':'Invalid submission size'})
            body=json.loads(self.rfile.read(n))
            if not isinstance(body,dict):raise ValueError('Invalid data')
            required=('name','email','phone','dog','service','date','time','consent')
            if any(not isinstance(body.get(k),str) or not body[k].strip() for k in required):raise ValueError('Complete all required fields')
            limits={'name':80,'email':120,'phone':30,'dog':60,'breed':80,'notes':500}
            for k,maxlen in limits.items():
                if len(str(body.get(k,'')))>maxlen:raise ValueError('One of your answers is too long')
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',body['email']):raise ValueError('Enter a valid email address')
            if body['service'] not in SERVICES:raise ValueError('Choose a listed service')
            if body['time'] not in {f'{h:02d}:00' for h in range(9,17)}:raise ValueError('Choose a valid time')
            day=date.fromisoformat(body['date']); today=datetime.now(ZoneInfo('Pacific/Auckland')).date()
            if day<today or day.weekday()==6:raise ValueError('Choose a future Monday to Saturday')
            if day>(today.replace(year=today.year+1) if today.month!=2 or today.day!=29 else date(today.year+1,2,28)):raise ValueError('Date is too far in advance')
            if body['consent']!='on':raise ValueError('Consent is required')
            reference='SP-'+secrets.token_hex(4).upper()
            clean={k:str(body.get(k,'')).strip() for k in (*required,'breed','notes') if k!='consent'}
            clean.update(reference=reference,submitted_at=datetime.now(ZoneInfo('Pacific/Auckland')).isoformat(),status='pending')
            DATA.parent.mkdir(exist_ok=True)
            with LOCK, DATA.open('a',encoding='utf-8') as f:f.write(json.dumps(clean,ensure_ascii=False)+'\n')
            return self.send_json(201,{'reference':reference})
        except (ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:return self.send_json(400,{'error':str(exc)[:130]})
        except OSError:return self.send_json(500,{'error':'Could not save your booking request'})

if __name__=='__main__':
    host=os.environ.get('HOST','127.0.0.1');port=int(os.environ.get('PORT','8000'))
    print(f'Snazzy Paws on http://{host}:{port}');ThreadingHTTPServer((host,port),Handler).serve_forever()
