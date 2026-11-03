import io
import os
import secrets
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
import requests

from flask import Flask, render_template, request, send_file

from analysis import METHODS, TOTAL, analyze, read_source, split_series
from charts import chart_png
from report import make_report

app=Flask(__name__)
snapshots=OrderedDict()
snapshot_lock=threading.Lock()


def parameters():
    settings={
        'iqr':float(request.args.get('iqr',1.5)),
        'z':float(request.args.get('z',3)),
        'window':int(request.args.get('window',7)),
        'percent':float(request.args.get('percent',40)),
        'alpha':float(request.args.get('alpha',.05)),
        'degree':int(request.args.get('degree',1)),
        'chart':request.args.get('chart','line'),
        'method':request.args.get('method','Any test'),
    }
    if not (.1<=settings['iqr']<=10 and .1<=settings['z']<=10 and 1<=settings['window']<=180
            and 0<settings['percent']<=1000 and .0001<=settings['alpha']<=.2
            and settings['degree'] in (1,2,3,4) and settings['chart'] in ('line','bar','stacked')
            and settings['method'] in ('Any test',*METHODS)):
        raise ValueError('Some analysis parameters are outside their supported range.')
    return settings


def load(use_snapshot=False):
    token=request.args.get('snapshot','')
    if use_snapshot and token:
        with snapshot_lock:
            cached=snapshots.get(token)
        if not cached or time.monotonic()-cached[0]>1800:
            raise ValueError('This report snapshot expired. Refresh the dashboard first.')
        return cached[1]
    settings=parameters()
    url=request.args.get('sheet','').strip() or os.getenv('SHEET_URL','')
    records,source=read_source(url)
    series=split_series(records)
    results={name:analyze(days,values,settings) for name,(days,values) in series.items()}
    return settings,url,source,records,series,results


@app.get('/')
def index():
    try:
        settings,url,source,records,series,results=load()
        selected=request.args.get('mine',TOTAL)
        if selected not in series:
            selected=TOTAL
        args=dict(request.args)
        args['mine']=selected
        args['snapshot']=secrets.token_urlsafe(18)
        with snapshot_lock:
            snapshots[args['snapshot']]=(time.monotonic(),(settings,url,source,records,series,results))
            while len(snapshots)>32:
                snapshots.popitem(last=False)
        return render_template('index.html',settings=settings,sheet=url,source=source,series=series,
            results=results,selected=selected,total=TOTAL,methods=METHODS,args=args,
            fetched=datetime.now(timezone.utc).strftime('%H:%M:%S UTC'),error=None)
    except (ValueError, OSError, requests.RequestException) as error:
        # Log the technical exception; the page must never quietly fall back to old sample data.
        app.logger.warning('Cannot load analysis: %s',error)
        return render_template('error.html',error=str(error)),400


@app.get('/chart.png')
def chart():
    try:
        settings,_,_,_,series,results=load(use_snapshot=True)
        name=request.args.get('mine',TOTAL)
        if name not in series:
            return 'Unknown mine',400
        response=send_file(io.BytesIO(chart_png(name,series,results,settings)),mimetype='image/png')
        response.headers['Cache-Control']='no-store'
        return response
    except (ValueError,OSError,requests.RequestException) as error:
        return str(error),400


@app.get('/report.pdf')
def report():
    try:
        settings,_,source,_,series,results=load(use_snapshot=True)
        return send_file(io.BytesIO(make_report(series,results,settings,source)),mimetype='application/pdf',
                         as_attachment=request.args.get('view')!='1',download_name='mining_report.pdf')
    except (ValueError,OSError,requests.RequestException) as error:
        return str(error),400


@app.get('/health')
def health():
    return {'status':'ok'}


if __name__=='__main__':
    from waitress import serve
    serve(app,host=os.getenv('HOST','127.0.0.1'),port=int(os.getenv('PORT','5065')))
