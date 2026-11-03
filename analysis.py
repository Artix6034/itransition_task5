import csv
import io
import math
import re
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import requests
from scipy.stats import t

TOTAL = 'Total output'
METHODS = ('IQR', 'Z-score', 'Moving average', 'Grubbs')


def read_source(sheet_url=''):
    if sheet_url:
        match = re.fullmatch(r'https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)(?:/[^\s]*)?', sheet_url.strip())
        if not match:
            raise ValueError('Enter a Google Sheets URL, or leave it blank to use the sample.')
        url = f'https://docs.google.com/spreadsheets/d/{match[1]}/gviz/tq'
        response = requests.get(url, params={'tqx':'out:csv','sheet':'Data','range':'A:C','headers':'1','_':time.time_ns()}, timeout=20,
                                headers={'Cache-Control':'no-cache'})
        response.raise_for_status()
        if len(response.content)>5_000_000:
            raise ValueError('The sheet is too large (maximum 5 MB).')
        text = response.content.decode('utf-8-sig')
        if '<html' in text[:300].lower() or '<!doctype' in text[:300].lower():
            raise ValueError('The spreadsheet is not readable. Enable access for anyone with the link.')
        source = 'Google Sheets, Data!A:C'
    else:
        text = (Path(__file__).parent / 'data' / 'sample.csv').read_text(encoding='utf-8-sig')
        source = 'Sample snapshot from the supplied workbook'
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or not {'Date','Mine','Production'} <= set(reader.fieldnames):
        raise ValueError('Data sheet needs the headers Date, Mine and Production in columns A:C.')
    records = []
    seen = set()
    for line, item in enumerate(reader,2):
        if not any((item.get(key) or '').strip() for key in ('Date','Mine','Production')):
            continue
        try:
            raw_date = item['Date'].strip()
            day = parse_date(raw_date)
            mine = item['Mine'].strip()
            # Google Sheets CSV uses the spreadsheet's decimal separator.
            number = item['Production'].strip().replace('\u00a0','').replace('\u202f','').replace(' ','')
            value = float(number.replace(',','.'))
            if not mine or not math.isfinite(value) or value<0:
                raise ValueError
            if (day,mine) in seen:
                raise ValueError(f'Duplicate record for {mine} on {day}.')
            seen.add((day,mine))
            records.append((day,mine,value))
        except (ValueError,TypeError,KeyError) as error:
            raise ValueError(f'Invalid data at CSV row {line}: {error}') from error
    if not records:
        raise ValueError('No production records found.')
    return sorted(records), source


def parse_date(value):
    for fmt in ('%Y-%m-%d','%m/%d/%Y','%m/%d/%y','%d.%m.%Y','%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(value,fmt).date()
        except ValueError:
            pass
    try:
        return (datetime(1899,12,30)+timedelta(days=float(value))).date()
    except (ValueError,OverflowError):
        raise ValueError(f'Unsupported date: {value}') from None


def split_series(records):
    groups = defaultdict(dict)
    totals = defaultdict(float)
    for day, mine, value in records:
        if mine == TOTAL:
            raise ValueError(f'Mine name {TOTAL!r} is reserved for the daily aggregate.')
        groups[mine][day] = value
        totals[day] += value
    days = sorted(totals)
    if any((right-left).days!=1 for left,right in zip(days,days[1:])):
        raise ValueError('The source has missing calendar days.')
    # Missing mine/day records must not silently become lower aggregate production.
    for mine, values in groups.items():
        if set(values) != set(days):
            raise ValueError(f'Missing dates for {mine}. Each active mine needs one record per day.')
    groups[TOTAL] = totals
    return {name:(days,np.array([values[d] for d in days],dtype=float))
            for name,values in sorted(groups.items(), key=lambda pair:(pair[0]!=TOTAL,pair[0]))}


def analyze(days, values, settings):
    count = len(values)
    mean, median = float(np.mean(values)), float(np.median(values))
    std = float(np.std(values,ddof=1)) if count>1 else 0.0
    q1,q3 = np.percentile(values,[25,75])
    iqr = float(q3-q1)
    low,high = float(q1-settings['iqr']*iqr),float(q3+settings['iqr']*iqr)
    z = np.abs(values-mean)/std if std>0 else np.zeros(count)
    moving = np.full(count,np.nan)
    window = settings['window']
    # A full preceding window, excluding the current value, avoids self-masking.
    for i in range(window,count):
        moving[i] = np.mean(values[i-window:i])
    percent = np.full(count,np.nan)
    valid = np.isfinite(moving) & (moving!=0)
    percent[valid] = 100*np.abs(values[valid]-moving[valid])/np.abs(moving[valid])
    percent[(moving==0)&(values==0)] = 0
    percent[(moving==0)&(values!=0)] = np.inf
    grubbs = np.zeros(count,dtype=bool)
    g = critical = None
    if count>=3 and std>0:
        max_index = int(np.argmax(z))
        g = float(z[max_index])
        quantile = float(t.ppf(1-settings['alpha']/(2*count),count-2))
        critical = (count-1)/math.sqrt(count)*math.sqrt(quantile**2/(count-2+quantile**2))
        if g>critical:
            grubbs[max_index] = True
    flags = {'IQR':(values<low)|(values>high),'Z-score':z>settings['z'],
             'Moving average':percent>settings['percent'],'Grubbs':grubbs}
    anomalies=[]
    for index in range(count):
        methods=[method for method in METHODS if flags[method][index]]
        if methods:
            baseline = float(moving[index]) if np.isfinite(moving[index]) else median
            anomalies.append({'date':days[index].isoformat(),'value':float(values[index]),
                'baseline':baseline,'direction':'spike' if values[index]>baseline else 'drop',
                'methods':methods,'z':float(z[index]),'ma_percent':float(percent[index]),
                'index':index})
    return {'count':count,'mean':mean,'std':std,'median':median,'iqr':iqr,'q1':float(q1),'q3':float(q3),
            'low':low,'high':high,'flags':flags,'anomalies':anomalies,'moving':moving,
            'grubbs_stat':g,'grubbs_critical':critical}


def trend(days, values, degree):
    x = np.array([(d-days[0]).days for d in days],dtype=float)
    if len(values)<=degree or len(np.unique(x))<=degree:
        return None
    return np.polynomial.Polynomial.fit(x,values,degree)(x)
