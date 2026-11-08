from pathlib import Path
import json,sqlite3,re,ast
import pandas as pd
r=Path(__file__).resolve().parents[1]
o=pd.read_csv(r/'data/Olist_Pesanan_Gabungan.csv');i=pd.read_csv(r/'data/Olist_Item_Gabungan.csv')
with sqlite3.connect(':memory:') as db:
 o.to_sql('order_fact',db,index=False)
 cube=pd.read_sql_query((r/'sql/cube.sql').read_text(),db)
 assert cube.orders.sum()==len(o)==99441
 assert cube.eligible.sum()==96470 and cube.late.sum()==6534
 assert cube.gmv_cents.sum()==1322149811
 core=cube[cube.month.between('2017-01','2018-08')]
 assert core.orders.sum()==99092 and core.eligible.sum()==96203 and core.late.sum()==6531
 assert core.gmv_cents.sum()==1318102713
print('PASS: SQL cube reconciliation against supplied analytical orders, full/core scopes.')
tables={}
for name,df in [('Orders',o),('Items',i)]:
 s=(r/f'Olist.SemanticModel/definition/tables/{name}.tmdl').read_text()
 columns=set(re.findall(r'^\tcolumn (\w+)',s,re.M))
 measures=set(re.findall(r"^\tmeasure '([^']+)'",s,re.M))
 src=re.findall(r'^\t\tsourceColumn: (\w+)',s,re.M)
 assert set(src)<=set(df.columns)|{'period_scope','delivery_group'}
 tables[name]=(columns,measures)
visuals=list((r/'Olist.Report/definition/pages').glob('*/visuals/*/visual.json'))
refs=[]
def walk(x):
 if isinstance(x,dict):
  for typ in ['Measure','Column']:
   if typ in x:
    f=x[typ];entity=f.get('Expression',{}).get('SourceRef',{}).get('Entity');prop=f.get('Property')
    if entity and prop:
     assert entity in tables,(entity,prop)
     assert prop in tables[entity][1 if typ=='Measure' else 0],(typ,entity,prop)
     refs.append((entity,prop))
  for v in x.values():walk(v)
 elif isinstance(x,list):
  for v in x:walk(v)
for p in visuals:walk(json.loads(p.read_text()))
for p in (r/'src').glob('*.py'):ast.parse(p.read_text())
print(f'PASS: {len(visuals)} visual JSON documents; {len(refs)} column/measure references; {sum(len(x[1]) for x in tables.values())} measures; imported columns present in CSVs.')
print('Not tested: Microsoft schema conformance, Power BI import/render/DAX/filter interactions; raw ZIP rebuild scripts.')
