"""Score graph content separately from strict JSON format; no new model calls."""
import argparse,json
from pathlib import Path

def evaluate(document):
    rows=[]
    for row in document['turns']:
        answer=row['answer'].strip();data=None;error=None
        try:
            if answer.startswith('```'):answer=answer.split('\n',1)[1].rsplit('```',1)[0].strip()
            data=json.loads(answer)
            if not isinstance(data,dict):raise ValueError('Object required')
            for field in row['expected']:
                if field not in data:raise ValueError('Missing field: '+field)
            if any(type(data[k]) is not bool for k in ('married','partners','siblings')):raise ValueError('Boolean required')
            if type(data['debt_eur']) not in (int,float):raise ValueError('Numeric debt required')
        except Exception as exc:error=str(exc)
        projection={k:data[k] for k in row['expected']} if error is None else None
        content=projection==row['expected']
        schema=error is None and set(data)==set(row['expected'])
        rows.append({'turn':row['turn'],'expected':row['expected'],'observed_fields':projection,
                     'graph_fields_match':content,'strict_schema_match':schema,
                     'combined_pass':content and schema,'extra_fields':sorted(set(data)-set(row['expected'])) if isinstance(data,dict) else [],'parse_error':error})
    return {'graph_field_matches':sum(r['graph_fields_match'] for r in rows),
            'strict_schema_matches':sum(r['strict_schema_match'] for r in rows),
            'combined_passes':sum(r['combined_pass'] for r in rows),'turns':rows}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('output');args=p.parse_args()
    result=evaluate(json.loads(Path(args.input).read_text(encoding='utf-8')))
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='turns'}))
