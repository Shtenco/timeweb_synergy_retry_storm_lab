#!/usr/bin/env python3
"""Independent editorial figures, built from measured raw CSV/JSON. No fabricated samples.

Design: white research-paper style; varied data encodings; restrained ink/cobalt/coral palette.
If a plot is conceptual, the caption explicitly says so.
"""
from __future__ import annotations
import csv, json, math, statistics, sys
from pathlib import Path
from collections import Counter, defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, Circle
from matplotlib import font_manager
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'results/experiment_18'
OUT=ROOT/'figures_editorial'
OUT.mkdir(exist_ok=True)
D=json.loads((SRC/'benchmark.json').read_text(encoding='utf-8'))
with (SRC/'operations.csv').open(encoding='utf-8') as f: OP=list(csv.DictReader(f))
with (SRC/'backend_events.csv').open(encoding='utf-8') as f: EV=list(csv.DictReader(f))
RUNS=D['runs']
KEYS=['direct','naive_retry','jitter_retry','breaker_only','budget_bulkhead','protected']
NAMES=['Без повторов','Retry без паузы','Retry + jitter','Circuit breaker','Budget + bulkhead','Все три защиты']
KNAME=dict(zip(KEYS,NAMES))
COLOR={'direct':'#30435c','naive_retry':'#e68b22','jitter_retry':'#b46225','breaker_only':'#cc4564','budget_bulkhead':'#0b7b72','protected':'#4057b2'}
CBASE='#182330';MUTED='#506174';GRID='#dce4e9';LITE='#edf2f5'
MED=lambda k,v:statistics.median(float(x[v]) for x in RUNS if x['policy']==k)
BY={k:[x for x in RUNS if x['policy']==k] for k in KEYS}
FONT='DejaVu Sans' if 'DejaVu Sans' in {x.name for x in font_manager.fontManager.ttflist} else 'Liberation Sans'
plt.rcParams.update({'font.family':FONT, 'font.size':12, 'text.color':CBASE,'axes.labelcolor':MUTED,
 'axes.edgecolor':'#aebbc6','xtick.color':MUTED,'ytick.color':MUTED,
 'axes.titleweight':'bold','axes.facecolor':'white','figure.facecolor':'white',
 'savefig.facecolor':'white','grid.color':GRID, 'axes.spines.right':False,'axes.spines.top':False})

def canvas(title,subtitle,foot='',figsize=(13.6,7.5),left=.19,right=.94,top=.78,bottom=.18):
 fig,ax=plt.subplots(figsize=figsize,dpi=140)
 fig.subplots_adjust(left=left,right=right,top=top,bottom=bottom)
 fig.text(.052,.947,title,fontsize=22,fontweight='bold',va='top')
 fig.text(.053,.88,subtitle,fontsize=11.7,color=MUTED,va='top')
 if foot:fig.text(.053,.052,foot,fontsize=10.1,color=MUTED)
 return fig,ax

def write(fig,fn):
 fn=OUT/fn;fig.savefig(fn,dpi=140,facecolor='white');plt.close(fig)
 return fn

# 01: cover image at exact Habr size, strong graphical evidence, zero dense labels.
fig=plt.figure(figsize=(7.8,4.4),dpi=100,facecolor='white')
ax=fig.add_axes([0,0,1,1]);ax.axis('off')
ax.text(.055,.89,'Когда защита API стала причиной отказов',size=18.9,weight='bold',transform=ax.transAxes)
ax.text(.055,.78,'Сравнение двух политик на локальном HTTP-стенде',size=10.5,color=MUTED,transform=ax.transAxes)
ax.plot([.08,.91],[.57,.57],color=GRID,lw=12,solid_capstyle='butt',transform=ax.transAxes)
ax.plot([.08,.08+.83*.5625],[.57,.57],color=COLOR['budget_bulkhead'],lw=12,solid_capstyle='butt',transform=ax.transAxes)
ax.plot([.08,.08+.83*.3292],[.38,.38],color=COLOR['protected'],lw=12,solid_capstyle='butt',transform=ax.transAxes)
ax.plot([.08,.91],[.38,.38],color=GRID,lw=0.8,transform=ax.transAxes,zorder=-1)
ax.text(.08,.63,'56,25%',weight='bold',size=15,color=COLOR['budget_bulkhead'],transform=ax.transAxes)
ax.text(.08,.25,'32,92%',weight='bold',size=15,color=COLOR['protected'],transform=ax.transAxes)
ax.text(.38,.645,'Retry budget + bulkhead',size=10.6,transform=ax.transAxes,color=MUTED)
ax.text(.34,.265,'+ общий circuit breaker',size=10.6,transform=ax.transAxes,color=MUTED)
ax.text(.08,.11,'−23,33 п. п. успешности в измеренной конфигурации',size=10.5,weight='bold',transform=ax.transAxes)
write(fig,'00_COVER_780x440.png')

# 02. Outcome: lollipops with all three repeats
fig,ax=canvas('Шесть политик, один сценарий сбоев','Успешность логических операций · три запуска на каждую политику',
 'Точки — отдельные серии; крупная метка — медиана. Чем больше, тем лучше.')
y=np.arange(6)[::-1]
ax.set_xlim(0,90);ax.set_ylim(-.65,5.7);ax.grid(axis='x',alpha=.65)
for yi,k in zip(y,KEYS):
 v=MED(k,'success_percent');ax.hlines(yi,0,v,color=COLOR[k],lw=3.5,zorder=2)
 for j,r in enumerate(BY[k]):ax.plot(float(r['success_percent']),yi+(j-1)*.13,'o',ms=7,color=COLOR[k],mec='white',mew=.9,zorder=4)
 ax.text(v+1.6,yi,f'{v:.1f}%',va='center',weight='bold',size=12,color=COLOR[k]);ax.plot(v,yi,'o',ms=12,color=COLOR[k],mec='white',mew=2,zorder=3)
ax.set_yticks(y,NAMES);ax.set_xlabel('Успешных операций, %')
write(fig,'01_SUCCESS_DOT_RANGE.png')

# 03. True incident map: samples from logged server events for direct only.
fig,ax=canvas('Проверка начиналась с заранее заданного сбоя','ID исходного запроса → фактический класс ошибки; прямая политика, серия 1',
 'Один сервер, 240 ID. Цвет отражает класс в журнале первого обращения.',left=.13,bottom=.23)
r=[x for x in EV if x['policy']=='direct' and int(x['repeat'])==0 and int(x['attempt'])==1]
classes={'healthy':'#0b7b72','permanent_503':'#c44e52','transient_503':'#e68b22','slow_200':'#7171a7'}
cat=[x['category'] for x in sorted(r,key=lambda z:int(z['request_id']))]
colors=[classes.get(x,'#bec9d2') for x in cat]
for i,c in enumerate(colors):ax.add_patch(Rectangle((i,0),1,1,facecolor=c,edgecolor='white',linewidth=.14))
ax.set_xlim(0,240);ax.set_ylim(-.3,1.55);ax.set_yticks([]);ax.set_xlabel('Порядковый ID запроса')
ax.axvspan(40,200,color='#c44e52',alpha=.06)
ax.text(40,1.14,'Начало сбоя: ID 40',size=11,weight='bold',color='#b44448')
ax.text(200,1.14,'Восстановление: ID 200',ha='right',size=11,weight='bold',color='#0b7b72')
labels=[('Без ошибок',classes['healthy']),('Постоянный 503',classes['permanent_503']),('Временный 503',classes['transient_503']),('Медленный ответ',classes['slow_200'])]
for j,(t,c) in enumerate(labels):
 ax.scatter(10+j*58,-.18,s=70,marker='s',color=c,clip_on=False);ax.text(15+j*58,-.18,t,size=9.2,va='center')
write(fig,'02_FAILURE_RIBBON.png')

# 04. Attempt amplification actual measurements.
fig,ax=canvas('Сколько дополнительных вызовов создал retry?','Клиент отправляет 240 логических операций за прогон',
 'Тонкие точки — отдельные запуски; 1,0 означает ровно один вызов на операцию.')
ax.grid(axis='x',alpha=.6)
for yi,k in zip(y,KEYS):
 m=MED(k,'amplification');ax.hlines(yi,0,m,color=COLOR[k],linewidth=5)
 ax.scatter([float(q['amplification']) for q in BY[k]],[yi-.13,yi,yi+.13],s=28,c=COLOR[k],edgecolors='white',zorder=3)
 ax.text(m+.045,yi,f'{m:.2f}×',size=12,va='center',weight='bold')
ax.axvline(1,color='#718094',linestyle='--',linewidth=1)
ax.set_xlim(0,2.25);ax.set_yticks(y,NAMES);ax.set_xlabel('Реальных HTTP-попыток / исходная операция')
write(fig,'03_AMPLIFICATION.png')

# 05. Success by phase directly from run dict
phases=['healthy_before','incident','healthy_after'];phase_names=['До сбоя','Во время сбоя','После восстановления']
fig,ax=canvas('Где именно теряется доступность','Медиана успешности по фазам для каждой политики · 3 запуска',
 'Цвет — доля успеха от 0% (светлый) до 100% (тёмный).',left=.21,bottom=.22,top=.78)
mat=np.array([[statistics.median(float(z['phases'][ph]['successes']) / float(z['phases'][ph]['requests']) * 100 for z in BY[k]) for ph in phases] for k in KEYS])
from matplotlib.colors import LinearSegmentedColormap
cm=LinearSegmentedColormap.from_list('dat',['#f4f7f8','#9ac9bf','#0b746d'])
ax.imshow(mat,aspect='auto',vmin=0,vmax=100,cmap=cm)
ax.set_xticks(range(3),phase_names);ax.set_yticks(range(6),NAMES)
for i in range(6):
 for j in range(3):ax.text(j,i,f'{mat[i,j]:.1f}%',ha='center',va='center',color='white' if mat[i,j]>76 else CBASE,weight='bold',fontsize=11)
for spine in ax.spines.values():spine.set_visible(False)
write(fig,'04_PHASE_HEATMAP.png')

# 06. Empirical p50/p95 paired dumbbell, exposes fast failures.
fig,ax=canvas('Низкий p95 не равен высокой доступности','Время до успеха или окончательного отказа; все логические операции',
 'У breaker p95 мал, потому что многие запросы отвергнуты сразу, до HTTP.',left=.20)
ax.grid(axis='x',alpha=.65)
for yi,k in zip(y,KEYS):
 p50=MED(k,'p50_ms');p95=MED(k,'p95_ms')
 ax.plot([p50,p95],[yi,yi],lw=3,color=COLOR[k]);ax.plot([p50],[yi],'o',ms=9,color='white',mec=COLOR[k],mew=2.5);ax.plot([p95],[yi],'o',ms=10,color=COLOR[k],mec='white',mew=1)
 ax.text(p95+2,yi,f'{p95:.1f}',size=11,va='center')
ax.set_xlim(0,190);ax.set_yticks(y,NAMES);ax.set_xlabel('Миллисекунды: ○ медиана · ● p95')
write(fig,'05_LATENCY_DUMBBELL.png')

# 07. Empirical ECDF for four policies from raw operations, repeat 0
fig,ax=canvas('Быстрые отказы и долгие повторы на одной шкале','Распределение задержек всех операций, включая отказавшие · серия 1',
 'В этой метрике исключено ожидание в очереди пула до начала исполнения.',left=.13)
for k in ['direct','naive_retry','budget_bulkhead','protected']:
 x=np.sort(np.array([float(z['latency_ms']) for z in OP if z['policy']==k and int(z['repeat'])==0]));x=np.maximum(x,.1)
 ax.step(x,np.arange(1,len(x)+1)/len(x)*100,color=COLOR[k],lw=2.5,label=KNAME[k],where='post')
ax.set_xscale('log');ax.set_xlim(.1,300);ax.set_ylim(0,102);ax.set_xlabel('Задержка одной логической операции, мс (логарифмическая ось)');ax.set_ylabel('Доля операций ≤ t, %');ax.grid(alpha=.5)
ax.legend(loc='lower right',fontsize=10.3,frameon=False)
write(fig,'06_ECDF_LATENCY.png')

# 08. Final outcome-by-request heatmap for six policies same repeat 0
fig,ax=canvas('Какие именно запросы спасли повторы','Каждая ячейка — исходный ID от 0 до 239; серия 1',
 'Бирюзовый — успешный ответ, красный — отказ; один и тот же набор ID.',left=.19,bottom=.16)
for yi,k in enumerate(KEYS):
 b={int(z['request_id']):z['success']=='True' for z in OP if z['policy']==k and int(z['repeat'])==0}
 for i in range(240):
  ax.add_patch(Rectangle((i,yi),1,1,linewidth=0,facecolor='#148675' if b.get(i,False) else '#d45d68'))
ax.axvline(40,color='white',lw=1.8);ax.axvline(200,color='white',lw=1.8)
ax.set_xlim(0,240);ax.set_ylim(6,0);ax.set_yticks(np.arange(6)+.5,NAMES);ax.set_xticks([0,40,80,120,160,200,240]);ax.set_xlabel('ID операции');ax.grid(False)
for s in ax.spines.values():s.set_visible(False)
write(fig,'07_REQUEST_OUTCOME_RASTER.png')

# 09. Attempts histogram (must show actual per policy and total)
fig,ax=canvas('Как распределились попытки','Для каждой политики — все 720 логических операций трёх повторов',
 'Считаем также операции с нулём HTTP-вызовов — локальные отказы breaker.',left=.14,top=.77)
vals=np.array([[sum(1 for z in OP if z['policy']==k and int(z['attempts'])==att) for att in (0,1,2,3)] for k in KEYS]);pos=np.arange(6);bottom=np.zeros(6)
for att,col in zip(range(4),['#c3cbd3','#7ba9a3','#ecc58b','#d7746b']):
 ax.bar(pos,vals[:,att],bottom=bottom,width=.65,color=col,label=f'{att} попыток' if att==0 else (f'{att} попытка' if att==1 else f'{att} попытки'),edgecolor='white',linewidth=.8);bottom+=vals[:,att]
ax.set_xticks(pos,[n.replace(' ','\n',1) for n in NAMES],fontsize=9.3);ax.set_ylabel('Количество логических операций');ax.set_ylim(0,780);ax.legend(loc='upper right',frameon=False,ncol=3,fontsize=10)
write(fig,'08_ATTEMPTS_STACK.png')

# 10. Stack reasons (only actual raw reason enum)
reason_list=sorted(set(z['reason'] for z in OP));counts={k:Counter(z['reason'] for z in OP if z['policy']==k) for k in KEYS}
reasons=sorted(reason_list,key=lambda r:-sum(counts[k][r] for k in KEYS))
fig,ax=canvas('Из-за чего закончились запросы','Финальный статус логической операции · 720 операций на политику',
 'Источники: сырые поля reason в operations.csv; не произвольные категории.',left=.13,top=.73,bottom=.27)
rs_colors=['#198876','#cf5866','#e4a44b','#7081a2','#ad83b2','#a9b1ba','#475b75','#8d8d6a']
bottom=np.zeros(6)
for j,r in enumerate(reasons):
 v=np.array([counts[k][r] for k in KEYS]);ax.bar(range(6),v,bottom=bottom,width=.7,label=r,color=rs_colors[j%len(rs_colors)]);bottom+=v
ax.set_xticks(range(6),[n.replace(' ','\n',1) for n in NAMES],fontsize=9.1);ax.set_ylabel('Количество операций');ax.set_ylim(0,760);ax.legend(loc='upper center',bbox_to_anchor=(.50,1.16),frameon=False,ncol=3,fontsize=8.7)
write(fig,'09_REASONS_STACK.png')

# 11. Paired intervention: no breaker vs breaker across each series
fig,ax=canvas('Абляция: добавили общий circuit breaker','Сравнение budget + bulkhead с protected при одинаковых параметрах стенда',
 'Каждая линия — одна серия; медианная разница −23,33 процентного пункта.',left=.12,top=.75)
for j in range(3):
 a=BY['budget_bulkhead'][j]['success_percent'];b=BY['protected'][j]['success_percent'];ax.plot([0,1],[a,b],color='#9caab6',lw=2,zorder=1);ax.scatter([0,1],[a,b],c=[COLOR['budget_bulkhead'],COLOR['protected']],s=125,zorder=3,edgecolors='white')
 ax.text(1.05,b,f'{b:.1f}%',va='center',fontsize=10.5)
ax.set_xticks([0,1],['Budget + bulkhead','Те же ограничения + breaker']);ax.set_xlim(-.25,1.32);ax.set_ylim(20,65);ax.set_ylabel('Успешность, %');ax.grid(axis='y',alpha=.6)
write(fig,'10_PAIRED_BREAKER_ABLATION.png')

# 12. Scatter p95 vs availability (18 points)
fig,ax=canvas('Успех, давление на сервер и цена задержки','18 независимых запусков · каждый маркер — одна серия одной политики',
 'Переместиться левее — не всегда улучшение: breaker отказывает клиенту без вызова сервера.',left=.14,top=.76)
for k in KEYS:
 ax.scatter([float(z['amplification']) for z in BY[k]],[float(z['success_percent']) for z in BY[k]],s=85,color=COLOR[k],alpha=.87,edgecolors='white',lw=1,label=KNAME[k])
ax.axvline(1,color='#8896a3',lw=1,ls='--');ax.set_xlim(.18,2.12);ax.set_ylim(20,82);ax.set_xlabel('HTTP-вызовов на одну операцию');ax.set_ylabel('Успешность, %');ax.grid(alpha=.4)
ax.legend(loc='upper right',fontsize=9.3,frameon=False,ncol=2)
write(fig,'11_TRADEOFF_SCATTER.png')

# 13. Conceptual sequence diagram, unique layout (not fake measurements)
fig=plt.figure(figsize=(13.6,7.5),dpi=140,facecolor='white');ax=fig.add_axes([.045,.10,.92,.73]);ax.axis('off')
fig.text(.053,.945,'Где формируется лавина повторов',fontsize=22,weight='bold',va='top');fig.text(.053,.88,'Временная диаграмма: логика обмена сообщениями, а не замер производительности',color=MUTED,fontsize=11.7)
lanes=[('Клиент',.15),('Защита',.47),('HTTP-сервис',.81)]
for lab,xx in lanes:
 ax.plot([xx,xx],[.13,.86],ls='--',lw=1.25,color='#9baab6');ax.text(xx,.91,lab,ha='center',fontsize=13,weight='bold')
steps=[(.15,.81,.79,'1. Исходный запрос','#30435c'),(.81,.15,.67,'503 / timeout','#c44e52'),(.15,.81,.54,'2. Немедленный retry','#e68b22'),(.81,.15,.42,'Ошибка / перегрузка','#c44e52'),(.15,.47,.30,'3. Бюджет: проверка лимита','#0b7b72'),(.47,.15,.18,'Отказать либо повторить позже','#0b7b72')]
for x1,x2,h,lab,col in steps:
 ar=FancyArrowPatch((x1,h),(x2,h),arrowstyle='-|>',mutation_scale=16,lw=2.5,color=col);ax.add_patch(ar);ax.text((x1+x2)/2,h+.03,lab,ha='center',fontsize=10.2,color=col,weight='bold')
fig.text(.055,.045,'Подпись: схема механики retry; доли, тайминги и успешность приведены отдельно в измерительных графиках',fontsize=10,color=MUTED)
write(fig,'12_RETRY_SEQUENCE_SCHEMATIC.png')

# 14. Circuit breaker states as a true transition diagram conceptual
fig=plt.figure(figsize=(13.6,7.5),dpi=140,facecolor='white');ax=fig.add_axes([.05,.11,.90,.73]);ax.set_xlim(0,12);ax.set_ylim(0,6);ax.axis('off')
fig.text(.055,.945,'Circuit breaker: точка, где отказ перестаёт доходить до HTTP',fontsize=20.8,weight='bold',va='top')
fig.text(.055,.885,'Схема автомата состояний в демонстрационном коде, не количественный график',fontsize=11.6,color=MUTED)
states=[(2,3.5,'CLOSED','Обычные запросы','#0b7b72'),(6,3.5,'OPEN','Быстрый отказ','#c44e52'),(10,3.5,'HALF-OPEN','Одна проба','#4057b2')]
for x,y,s,detail,col in states:
 ax.add_patch(Circle((x,y),radius=.80,facecolor='white',edgecolor=col,lw=3));ax.text(x,y+.15,s,ha='center',va='center',weight='bold',fontsize=12.0,color=col);ax.text(x,y-.24,detail,ha='center',va='center',fontsize=9.5)
for x1,x2,y1,txt,col in [(2.8,5.2,3.5,'Порог ошибок','#c44e52'),(6.8,9.2,3.5,'Пауза истекла','#4057b2')]:
 ax.add_patch(FancyArrowPatch((x1,y1),(x2,y1),arrowstyle='-|>',mutation_scale=18,lw=2,color=col));ax.text((x1+x2)/2,y1+.32,txt,ha='center',fontsize=10.5,color=col)
for endx,yy,txt in [(2,2.06,'Успешная проба закрывает контур'),(6,1.2,'Ошибка пробы возвращает OPEN')]:
 ax.add_patch(FancyArrowPatch((9.75,2.75),(endx+.10,yy),arrowstyle='-|>',connectionstyle='arc3,rad=-.12',mutation_scale=17,lw=2,color='#59697a'));ax.text(5.8,1.95 if endx==2 else .76,txt,ha='center',size=10,color=MUTED)
fig.text(.055,.04,'В показанном стенде один breaker обслуживает все запросы к общей зависимости',fontsize=10,color=MUTED)
write(fig,'13_BREAKER_STATE_MACHINE.png')

# 15. Operational checklist small editorial table, not generic cards
fig=plt.figure(figsize=(13.6,7.5),dpi=140,facecolor='white');ax=fig.add_axes([.06,.12,.89,.72]);ax.set_xlim(0,12);ax.set_ylim(0,6.6);ax.axis('off')
fig.text(.055,.945,'Что измерять перед включением защиты',fontsize=22,fontweight='bold',va='top')
fig.text(.055,.885,'Инженерный чек-лист по итогам лаборатории — рекомендации, не результаты бенчмарка',fontsize=11.6,color=MUTED)
items=[('Причина отказа','503, timeout, локальный reject', 'Не смешивать разные классы'),('Успех по фазам','До инцидента / во время / после','Замечать задержку восстановления'),('Стоимость повторов','Attempts per operation','Ограничить общий retry budget'),('Half-open','Число одновременных проб','Одна проба, защита от stale result'),('Дедлайн','От прибытия до завершения','Считать очередь на входе'),('Гранулярность','По зависимости, ключу, маршруту','Не глушить здоровые операции')]
for i,(key,metric,meaning) in enumerate(items):
 y=5.9-i*.9;ax.hlines(y-.25,0,12,color=GRID,lw=1);ax.text(.05,y,key,va='center',size=11.7,weight='bold',color=CBASE);ax.text(4.4,y,metric,va='center',size=11.1,color=CBASE);ax.text(9.0,y,meaning,va='center',size=9.9,color=MUTED)
ax.text(.05,6.34,'КОНТРОЛЬ',weight='bold',size=9.5,color='#5c6c7a');ax.text(4.4,6.34,'ЧТО СМОТРЕТЬ',weight='bold',size=9.5,color='#5c6c7a');ax.text(9.0,6.34,'ЗАЧЕМ',weight='bold',size=9.5,color='#5c6c7a')
fig.text(.055,.045,'Статус: методический чек-лист. Исходные результаты — в benchmark.json и operations.csv',size=10,color=MUTED)
write(fig,'14_DEPLOYMENT_CHECKLIST.png')

# numerical and provenance manifest
names=[
('00_COVER_780x440.png','КПДВ: успешность budget+bulkhead и той же конфигурации с breaker','measured'),
('01_SUCCESS_DOT_RANGE.png','Шесть клиентских политик: медианы и три индивидуальных запуска','measured'),
('02_FAILURE_RIBBON.png','Фактические классы отказов в журнале сервера на 240 исходных ID','measured'),
('03_AMPLIFICATION.png','Число реальных HTTP-попыток на одну логическую операцию','measured'),
('04_PHASE_HEATMAP.png','Доля успешных операций до аварии, во время неё и после','measured'),
('05_LATENCY_DUMBBELL.png','Медиана и p95 времени до ответа или отказа, включая быстрые отказы','measured'),
('06_ECDF_LATENCY.png','Эмпирические распределения задержек четырёх политик, первый повтор','measured'),
('07_REQUEST_OUTCOME_RASTER.png','Результат каждого из 240 исходных запросов по политикам, первый повтор','measured'),
('08_ATTEMPTS_STACK.png','Число операций с одной, двумя и тремя HTTP-попытками','measured'),
('09_REASONS_STACK.png','Причины завершения логических операций по сырым записям','measured'),
('10_PAIRED_BREAKER_ABLATION.png','Парное сравнение конфигураций с общим breaker и без него','measured'),
('11_TRADEOFF_SCATTER.png','Компромисс между HTTP-усилением и успешностью в 18 прогонах','measured'),
('12_RETRY_SEQUENCE_SCHEMATIC.png','Последовательность retry и проверки общего бюджета, принцип работы','conceptual'),
('13_BREAKER_STATE_MACHINE.png','Переходы автомата circuit breaker: CLOSED, OPEN и HALF-OPEN','conceptual'),
('14_DEPLOYMENT_CHECKLIST.png','Критерии безопасной настройки защиты перед продуктивным запуском','conceptual')]
(OUT/'MANIFEST.json').write_text(json.dumps([dict(file=f,caption=cap,kind=kind,source='results/experiment_18/benchmark.json + operations.csv + backend_events.csv' if kind=='measured' else 'source code and methodology') for f,cap,kind in names],ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Created {len(names)} visuals in {OUT}')
