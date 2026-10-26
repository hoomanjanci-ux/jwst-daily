"""Read-only permission probe; never prints or uploads credentials."""
import os,json,urllib.request,urllib.error
account=os.environ['CF_ACCOUNT_ID'];token=os.environ['CF_API_TOKEN'];db=os.environ['CF_D1_DATABASE_ID']
checks={}
for label,path,body in [('workers',f'/accounts/{account}/workers/scripts',None),
                        ('subdomain',f'/accounts/{account}/workers/subdomain',None),
                        ('d1',f'/accounts/{account}/d1/database/{db}/query',{'sql':'SELECT 1 AS ok','params':[]})]:
    request=urllib.request.Request('https://api.cloudflare.com/client/v4'+path,
        data=json.dumps(body).encode() if body else None,
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=30) as response:
            data=json.load(response);status=response.status
    except urllib.error.HTTPError as exc:
        status=exc.code;data=json.load(exc)
    checks[label]={'http_status':status,'success':bool(data.get('success')),
                   'error_codes':[e.get('code') for e in data.get('errors',[])]}
print(json.dumps(checks))
open('infrastructure-probe.json','w').write(json.dumps(checks))
