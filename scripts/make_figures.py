#!/usr/bin/env python3
"""Publication-grade neutral technical PNG figures, generated ONLY from saved local results.

No logos, advertising, invented benchmark bars, or styling that obscures limitations.
"""
from __future__ import annotations
from collections import defaultdict
import csv
import json
from pathlib import Path
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager
import numpy as np

BASE=Path(__file__).resolve().parents[1]
RESULT=Path(sys.argv[1] if len(sys.argv)>1 else BASE/'results/experiment_18')
OUT=Path(sys.argv[2] if len(sys.argv)>2 else BASE/'figures')
OUT.mkdir(parents=True,exist_ok=True)

styles={"direct":"#374151","naive_retry":"#d97706","jitter_retry":"#b45309",
        "breaker_only":"#be123c","budget_bulkhead":"#047857","protected":"#4338ca"}
labels={"direct":"Без повторов","naive_retry":"Retry сразу ×3","jitter_retry":"Retry + jitter",
        "breaker_only":"Circuit breaker","budget_bulkhead":"Budget + bulkhead","protected":"Всё вместе"}
order=list(labels)
with (RESULT/'benchmark.json').open(encoding='utf-8') as f: data=json.load(f)
with (RESULT/'operations.csv').open(encoding='utf-8') as f:operations=list(csv.DictReader(f))
with (RESULT/'backend_events.csv').open(encoding='utf-8') as f:events=list(csv.DictReader(f))
by_name=defaultdict(list)
for r in data['runs']:by_name[r['policy']].append(r)
med=lambda name,metric:statistics.median(float(x[metric]) for x in by_name[name])
font=next((f for f in ['DejaVu Sans','Liberation Sans'] if f in {x.name for x in font_manager.fontManager.ttflist}), 'sans-serif')
plt.rcParams.update({'font.family':font,'figure.facecolor':'white','axes.facecolor':'white',
 'savefig.facecolor':'white','text.color':'#111827','axes.labelcolor':'#374151',
 'axes.edgecolor':'#cbd5e1','xtick.color':'#374151','ytick.color':'#374151',
 'font.size':13,'axes.titlesize':19,'axes.titleweight':'bold','axes.spines.top':False,
 'axes.spines.right':False,'grid.color':'#e5e7eb','grid.linestyle':'--', 'grid.alpha':0.8})

def setup(title,subtitle='', figsize=(13,7)):
 fig,ax=plt.subplots(figsize=figsize,dpi=150)
 fig.subplots_adjust(left=.14,right=.95,top=.78,bottom=.20)
 fig.text(.055,.96,title,fontsize=21,fontweight='bold',va='top')
 if subtitle:fig.text(.056,.90,subtitle,fontsize=12,color='#4b5563',va='top')
 ax.grid(axis='x',zorder=0)
 return fig,ax

def save(fig,name):
 path=OUT/name
 fig.savefig(path,dpi=150,facecolor='white')
 plt.close(fig)
 return path

# 01 — hero graphic: three numeric anchors and a true small conclusion.
fig=plt.figure(figsize=(13,7.2),dpi=150,facecolor='white')
ax=fig.add_axes([0,0,1,1]);ax.set_axis_off()
ax.text(.055,.92,'Защита API тоже может вызвать отказ',fontsize=28,fontweight='bold',va='top')
ax.text(.055,.85,'Локальный HTTP-стенд · 6 политик · 3 серии · 4 320 логических операций',fontsize=13,color='#4b5563')
metrics=[('47,9%','Без повторов',styles['direct']),('69,6%','Retry до трёх раз',styles['naive_retry']),('32,9%','С breaker + bulkhead',styles['protected'])]
for i,(value,cap,color) in enumerate(metrics):
 x=.055+i*.315
 ax.add_patch(FancyBboxPatch((x,.47),.282,.27,boxstyle='round,pad=0.012,rounding_size=0.02',linewidth=1.3,edgecolor='#d1d5db',facecolor='white'))
 ax.add_patch(FancyBboxPatch((x+.017,.67),.055,.012,boxstyle='round,pad=0.002',linewidth=0,facecolor=color))
 ax.text(x+.020,.59,value,fontsize=32,fontweight='bold',color=color)
 ax.text(x+.020,.515,cap,fontsize=12.2,color='#374151')
ax.text(.055,.38,'Ключевой парадокс',fontsize=17,fontweight='bold')
ax.text(.055,.315,'Circuit breaker бережёт зависимый сервис, но ошибочная настройка',fontsize=16)
ax.text(.055,.268,'способна отклонить запросы, которые сервер обслужил бы.',fontsize=16)
ax.plot([.055,.945],[.215,.215],lw=1.2,color='#d1d5db')
ax.text(.055,.16,'Источник: results/experiment_18/benchmark.json · медианы трёх запусков',fontsize=11,color='#64748b')
save(fig,'01_hero_real_http_results.png')

# 02 — six policy outcomes: success + min/max across repeats.
fig,ax=setup('Кому помогли повторы, а кому — circuit breaker?', 'Доля успешных логических операций, % · три независимых серии')
y=np.arange(len(order))[::-1];values=[med(x,'success_percent') for x in order]
low=[min(z['success_percent'] for z in by_name[x]) for x in order]
high=[max(z['success_percent'] for z in by_name[x]) for x in order]
ax.barh(y,values,color=[styles[x] for x in order],height=.57,zorder=2)
ax.errorbar(values,y,xerr=[[v-l for v,l in zip(values,low)],[h-v for v,h in zip(values,high)]],fmt='none',ecolor='#111827',capsize=4,zorder=3)
ax.set_yticks(y,labels=[labels[x] for x in order]);ax.set_xlim(0,100)
ax.set_xlabel('Успешных операций, %')
for yy,v in zip(y,values):ax.text(v+1.4,yy,f'{v:.1f}%',va='center',fontsize=12)
fig.text(.055,.08,'Часть отказов вызвана заданной неисправностью; breaker дополнительно отклоняет обращения',fontsize=11,color='#64748b')
save(fig,'02_success_rate_by_policy.png')

# 03 — amplification with reference line and numeric labels.
fig,ax=setup('Цена повтора: сколько HTTP-вызовов создаёт один запрос', 'Коэффициент усиления = обращения к зависимости / логические операции')
y=np.arange(len(order))[::-1];values=[med(x,'amplification') for x in order]
ax.barh(y,values,color=[styles[x] for x in order],height=.58,zorder=2)
ax.axvline(1,linestyle=':',linewidth=2,color='#64748b',zorder=3)
ax.set_yticks(y,labels=[labels[x] for x in order]);ax.set_xlim(0,2.25)
ax.set_xlabel('HTTP-вызовов на одну логическую операцию')
for yy,v in zip(y,values):ax.text(v+.035,yy,f'{v:.2f}×',va='center')
fig.text(.055,.08,'Менее 1× означает сброс запросов ещё до HTTP — не «экономию без последствий»',fontsize=11,color='#64748b')
save(fig,'03_http_amplification.png')

# 04 — p95 on all logical operations (short fail-fast is not success).
fig,ax=setup('Быстро отказать — не значит успешно ответить', 'p95 полного времени логической операции, включая немедленные отказы')
y=np.arange(len(order))[::-1];values=[med(x,'p95_ms') for x in order]
ax.barh(y,values,color=[styles[x] for x in order],height=.58,zorder=2)
ax.set_yticks(y,labels=[labels[x] for x in order]);ax.set_xlim(0,max(values)*1.24)
ax.set_xlabel('p95 задержки на клиенте, мс')
for yy,v in zip(y,values):ax.text(v+2,yy,f'{v:.1f} мс',va='center')
fig.text(.055,.08,'Для breaker маленький p95 обусловлен в том числе быстрым отказом без вызова сервера',fontsize=11,color='#64748b')
save(fig,'04_p95_latency_all_operations.png')

# 05 — three phases, median successes by policy. Per phase denominators disclosed.
phases=['healthy_before','incident','healthy_after']
phlabels=['До аварии','Во время аварии','После аварии']
fig,ax=setup('Когда именно теряются запросы', 'Доля успешных операций по фазам нагрузки; медиана трёх повторов',figsize=(14,7.3))
fig.subplots_adjust(left=.13,right=.95,top=.79,bottom=.24)
xs=np.arange(len(phases)); width=.12
for idx,key in enumerate(order):
 vals=[statistics.median([100*r['phases'][p]['successes']/r['phases'][p]['requests'] for r in by_name[key]]) for p in phases]
 ax.bar(xs+(idx-2.5)*width,vals,width=.115,label=labels[key],color=styles[key],zorder=2)
ax.set_xticks(xs,labels=phlabels);ax.set_ylim(0,110);ax.set_ylabel('Успешных операций, %');ax.grid(axis='y')
ax.legend(loc='lower center',bbox_to_anchor=(.5,-.39),ncol=3,frameon=False,fontsize=11)
fig.text(.055,.083,'Фаза определяется ID запроса: до 1/6, от 1/6 до 5/6, после 5/6 теста',fontsize=11,color='#64748b')
save(fig,'05_success_across_phases.png')

# 06 — retry budget vs availability in paired axes using no invented comparison.
fig,ax=setup('Компромисс: меньше обращений не всегда лучше', 'Каждая точка — отдельная измеренная серия; цвета — политики',figsize=(13,7.2))
fig.subplots_adjust(left=.10,right=.96,top=.80,bottom=.22)
for key in order:
 for run in by_name[key]:
  ax.scatter(run['amplification'],run['success_percent'],s=125,c=styles[key],
             marker='D' if key in ('protected','budget_bulkhead') else 'o',
             alpha=.7,edgecolors='white',linewidths=1,zorder=3)
 ax.scatter([],[],s=105,c=styles[key],label=labels[key])
ax.set_xlabel('HTTP-вызовов на логический запрос');ax.set_ylabel('Успешных операций, %')
ax.set_xlim(.19,2.02);ax.set_ylim(0,82);ax.grid(True)
ax.legend(loc='upper left',fontsize=11,ncol=2,frameon=False)
fig.text(.055,.084,'Точки близких прогонов могут перекрывать друг друга; это не независимые датасеты',fontsize=11,color='#64748b')
save(fig,'06_tradeoff_scatter_runs.png')

# 07 — true backend 503/overload diagnostics.
fig,ax=setup('Как политика изменяет нагрузку на зависимость', 'HTTP 503 от сервера и события отбраковки при заполненной ёмкости; медианы')
fig.subplots_adjust(left=.16,right=.95,top=.79,bottom=.23)
y=np.arange(len(order))[::-1];v503=[med(x,'backend_http_503') for x in order];ov=[med(x,'backend_overload') for x in order]
ax.barh(y,v503,height=.58,color=[styles[x] for x in order],alpha=.8,label='Все ответы HTTP 503')
ax.barh(y,ov,height=.24,color='#111827',label='Из них: отказ по ёмкости')
ax.set_yticks(y,labels=[labels[x] for x in order]);ax.set_xlabel('События на сервере за 240 исходных запросов')
ax.legend(loc='lower center',bbox_to_anchor=(.5,-.33),ncol=2,frameon=False)
fig.text(.055,.082,'Некоторые HTTP 503 преднамеренно возвращает fault injector, не только перегрузка',fontsize=11,color='#64748b')
save(fig,'07_backend_503_and_overload.png')

# 08 — logical architecture with clean nonoverlapping boxes, not measurement.
fig=plt.figure(figsize=(13,7.2),dpi=150,facecolor='white')
ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
ax.text(.055,.94,'Как устроен стенд: реальные HTTP-запросы',fontsize=24,fontweight='bold',va='top')
ax.text(.055,.875,'Схема архитектуры, не график измерений',fontsize=12,color='#64748b')
boxes=[(.06,.54,.24,.20,'Нагрузочный клиент','240 операций\nзаданным темпом'),
       (.39,.54,.24,.20,'Политика клиента','retry / budget\nbreaker / bulkhead'),
       (.72,.54,.24,.20,'HTTP-зависимость','127.0.0.1\ncapacity = 8')]
for x,y,w,h,title,body in boxes:
 ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.012,rounding_size=0.02',edgecolor='#94a3b8',facecolor='#f8fafc',lw=1.8))
 ax.text(x+.025,y+h-.065,title,fontsize=15,fontweight='bold')
 ax.text(x+.025,y+.056,body,fontsize=12,linespacing=1.6,color='#475569')
for a,b in [(.3,.39),(.63,.72)]:
 ax.add_patch(FancyArrowPatch((a,.64),(b,.64),arrowstyle='-|>',mutation_scale=17,lw=2,color='#334155'))
ax.add_patch(FancyBboxPatch((.39,.235),.57,.17,boxstyle='round,pad=0.012,rounding_size=0.02',edgecolor='#94a3b8',facecolor='#f8fafc',lw=1.6))
ax.text(.42,.335,'Фиксированный fault injector',fontsize=15,fontweight='bold')
ax.text(.42,.273,'503 постоянные / транзиентные · задержки 55 мс',fontsize=12,color='#475569')
ax.add_patch(FancyArrowPatch((.83,.405),(.83,.53),arrowstyle='-|>',mutation_scale=16,lw=2,color='#334155'))
ax.text(.055,.14,'Сервер запускается отдельно для каждой политики и каждой серии.',fontsize=12,color='#475569')
ax.text(.055,.10,'Все первичные события сохранены как CSV и защищены SHA-256.',fontsize=12,color='#475569')
save(fig,'08_lab_architecture.png')

# 09 — healthy phase difference, avoids seductive averaging and explains tuning.
fig,ax=setup('Цена общего circuit breaker видна в фазе восстановления', 'Успешные операции после аварийной фазы, %; три серии по каждой политике')
phase='healthy_after'; vals=[statistics.median([100*r['phases'][phase]['successes']/r['phases'][phase]['requests'] for r in by_name[key]]) for key in order]
y=np.arange(len(order))[::-1];ax.barh(y,vals,height=.57,color=[styles[x] for x in order],zorder=2)
ax.set_yticks(y,labels=[labels[x] for x in order]);ax.set_xlim(0,110);ax.set_xlabel('Успешных операций в healthy_after, %')
for yy,v in zip(y,vals):ax.text(v+1.5,yy,f'{v:.1f}%',va='center')
fig.text(.055,.08,'Речь об одном глобальном breaker для всех запросов: неверная гранулярность тоже ограничение',fontsize=11,color='#64748b')
save(fig,'09_recovery_phase_success.png')

print('Saved',len(list(OUT.glob('*.png'))),'PNG to',OUT)
