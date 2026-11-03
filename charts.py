import io
import threading

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from analysis import TOTAL, trend

LOCK = threading.Lock()
COLORS = ['#28657b','#698d76','#bb995b','#7c77a1','#587a91','#ba745e']


def chart_png(name, series, results, settings, width=10, height=4.0):
    days, values = series[name]
    with LOCK, plt.rc_context({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                              'axes.edgecolor':'#d2dce3','text.color':'#24394b','axes.labelcolor':'#536574'}):
        fig, ax = plt.subplots(figsize=(width,height),layout='constrained')
        mode = settings['chart']
        if mode == 'stacked' and name == TOTAL:
            parts = [(mine,data[1]) for mine,data in series.items() if mine!=TOTAL]
            ax.stackplot(days,*[data for _,data in parts],labels=[mine for mine,_ in parts],colors=COLORS,alpha=.75)
        elif mode == 'stacked':
            ax.fill_between(days,values,color=COLORS[0],alpha=.3,label=name)
            ax.plot(days,values,color=COLORS[0],lw=1.5)
        elif mode == 'bar':
            ax.bar(days,values,color=COLORS[0],width=.78,label=name)
        else:
            ax.plot(days,values,color=COLORS[0],lw=1.7,label=name)
        fitted = trend(days,values,settings['degree'])
        if fitted is not None:
            ax.plot(days,fitted,color='#9b7430',lw=1.6,ls='--',label=f"Degree {settings['degree']} trend")
        result = results[name]
        selected = settings['method']
        mask = np.logical_or.reduce(list(result['flags'].values())) if selected=='Any test' else result['flags'][selected]
        if mask.any():
            ax.scatter(np.array(days)[mask],values[mask],color='#ba4d3f',s=33,zorder=5,label='Flagged observations')
        ax.set_title(name,loc='left',fontweight='bold',pad=14)
        ax.set_ylabel('Daily production (tons)')
        ax.grid(axis='y',alpha=.16)
        ax.set_axisbelow(True)
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4,maxticks=7))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
        ax.legend(frameon=False,fontsize=8,loc='upper left',ncol=2)
        out=io.BytesIO()
        fig.savefig(out,format='png',dpi=150,facecolor='white')
        plt.close(fig)
        return out.getvalue()
