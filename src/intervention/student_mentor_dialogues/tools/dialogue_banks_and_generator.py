from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from src.utils.constants import (
    DIALOGUE_SEED as SEED,
    DIALOGUE_N as N,
    DIALOGUE_TOPICS as TOPICS,
    DIALOGUE_SUPPORTS as SUPPORTS,
    DIALOGUE_SECONDARIES as SECONDARIES,
    DIALOGUE_INTRO as INTRO,
    DIALOGUE_CORE_GENERAL as CORE_GENERAL,
    DIALOGUE_SECONDARY_GENERAL as SECONDARY_GENERAL,
    DIALOGUE_SUPPORT_GENERAL as SUPPORT_GENERAL,
    DIALOGUE_CLOSING as CLOSING,
    DIALOGUE_STATUS as STATUS,
    DIALOGUE_TOPIC_QUESTIONS as TOPIC_QUESTIONS,
)
import random, csv, json, zipfile, hashlib, re
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import Counter

rng=random.Random(SEED)
root=Path(__file__).resolve().parent.parent
output=root/'generated'
output.mkdir(parents=True, exist_ok=True)

# All personas and incidents below are invented; no survey row or real child is used.
# Attributes are authored scenario ingredients, not independently validated gold annotations.
# Every item is a mentor/student exchange; generated minute labels are simulated dialogue timing.


# Plausible but not falsely certain; the status is explicitly spoken during each session.

# Topic-specific clarification exchanges: deliberately nuanced/uncertain and non-diagnostic.

# To obtain varied but coherent transcripts, choose subsequences from each logically ordered bank,
# retain key question anchors, and create a minute record from each selected exchange.
def sample_keep_order(items, n, mandatory=()):
    if n > len(items):
        raise ValueError((n,len(items)))
    required=set(mandatory)
    if len(required)>n:
        raise ValueError('not enough space for mandatory beats')
    extras=list(set(range(len(items)))-required)
    picked=sorted(required|set(rng.sample(extras,n-len(required))))
    return [items[j] for j in picked]

# Need 30..60, allocate extra slots across stages with caps exactly 60.
def counts_for_duration(duration):
    vals=[4,10,4,8,4]
    maximum=[6,19,10,17,8]
    for _ in range(duration-30):
        available=[i for i in range(5) if vals[i]<maximum[i]]
        # keep exploring and planning phases long enough for complex sessions
        weights=[1.0,1.7,1.0,1.4,1.0]
        chosen=rng.choices(available,weights=[weights[i] for i in available])[0]
        vals[chosen]+=1
    assert sum(vals)==duration
    return vals

# A little variation in prompt framing with identical factual content.
def augment_mentor(text, level):
    if level=='reflective' and rng.random()<0.09 and text.startswith(('Can we','Could we','Would it','Would you')):
        return 'Just to clarify, '+text[0].lower()+text[1:]
    if level=='concise' and rng.random()<0.10:
        return text.replace('Would you like','Do you want').replace('Would it help','Could it help')
    return text

def augment_student(text, level):
    if level=='hesitant' and rng.random()<0.16 and not text.startswith(('I ','No,','Yes,','Maybe')):
        return rng.choice(['I think ','Maybe '])+text[0].lower()+text[1:]
    if level=='direct' and rng.random()<0.09:
        return text.replace('I would like','I want').replace('I do not know','I’m not sure')
    return text


def build_session(i, forced_reason=None, forced_action=None):
    sid=f'S{i:04d}'
    reason=forced_reason if forced_reason is not None else rng.choice(list(TOPICS))
    topic=TOPICS[reason]
    action=forced_action if forced_action is not None else rng.choice(topic['actions'])
    if action not in topic['actions']:
        raise ValueError('Action not permitted for topic')
    secondary=rng.choice([k for k in SECONDARIES if not (
       (reason=='math_gap' and k=='math_confidence') or
       (reason=='attendance_dispute' and k=='attendance_record') or
       (reason=='device_access' and k=='online_uploads') or
       (reason=='exam_pressure' and k=='exam_worry')
    )])
    duration=rng.randint(30,60)
    intro_n,core_n,secondary_n,action_n,closing_n=counts_for_duration(duration)
    style=rng.choice(['reflective','concise','neutral','direct','hesitant'])
    # Initial + general cause exploration. Core begins with main disclosure.
    core_topic=[(q,topic[field]) for q,field in TOPIC_QUESTIONS]
    core_merged=core_topic[:5]+CORE_GENERAL[:7]+core_topic[5:]+CORE_GENERAL[7:]
    core=sample_keep_order(core_merged,core_n-1, mandatory=(0,1,2,3,4))
    stage='followup' if rng.random()<0.34 else 'initial'
    previous={
        'tutoring': 'I attended one practice session. I followed the example there, but I still need more practice before we know whether it lasts.',
        'family_liaison': 'Someone offered to contact home last time, but I do not know whether the conversation actually happened.',
        'transport_assessment': 'I wrote down my usual journey, but no decision about travel support has reached me.',
        'family_finances': 'We received information about possible help, but I do not know whether an application was made.',
        'attendance_planning': 'I tried keeping a morning record for a few days. I still need help comparing it with the register.',
        'wellbeing_checkin': 'I had one brief check-in. It was good to talk, but the school difficulty has not gone away.',
        'homework_support': 'I made a short task list. I finished one item, but several others remain.',
        'learning_access': 'I tried a written checklist in one lesson. It helped me follow that task, but I do not know if it works elsewhere.',
        'device_access': 'I used a school computer once, but I have not been offered regular access.',
        'school_meals': 'I asked what food was available, but I have not had an eligibility decision.',
        'language_support': 'I tried a short vocabulary list. I understood some words better, though longer questions still confuse me.',
        'peer_support': 'Someone suggested a group activity, but I have not decided whether I want to take part.',
        'reentry_support': 'A teacher showed me the timetable last time, but the missing coursework is still unclear.'
    }
    if stage=='followup':
        core.append(('Before we discuss a new plan, what happened after the earlier support conversation?',previous[action]))
    else:
        core.append(('Have you previously had a formal support session about this concern?', 'Not a formal one, though I might have mentioned part of it to a teacher.'))
    second=SECONDARIES[secondary]+SECONDARY_GENERAL
    second=sample_keep_order(second,secondary_n,mandatory=(0,))
    status=rng.choice(list(STATUS))
    support_begin=[
       ('I would like us to consider an option that fits what you described. May I ask about it?', 'Yes, I would like to hear what is possible.'),
       ('The possible support area is '+action.replace('_',' ')+'. Does discussing that make sense?', 'Yes, we can talk about it without assuming it has been arranged.'),
    ]
    support_pool=SUPPORTS[action][:5]+SUPPORT_GENERAL[:6]+SUPPORTS[action][5:]+SUPPORT_GENERAL[6:]
    # keep 2 opening exchanges + 2 status exchanges within the action phase
    support_middle=sample_keep_order(support_pool,action_n-4,mandatory=(0,))
    support=support_begin+support_middle+list(STATUS[status])
    intro=sample_keep_order(INTRO,intro_n,mandatory=(0,))
    closing=sample_keep_order(CLOSING,closing_n,mandatory=(0,len(CLOSING)-1))
    beats=intro+core+second+support+closing
    assert len(beats)==duration,(len(beats),duration)
    first_day=date(2026,9,1)
    while True:
        d=first_day+timedelta(days=rng.randrange(59))
        if d.weekday()<5: break
    start_minutes=rng.randrange(8*60+20,14*60+10,5)
    base=datetime(2026,d.month,d.day,start_minutes//60,start_minutes%60)
    end=base+timedelta(minutes=duration)
    md=[
        '# Student', '',
        '**Synthetic session:** '+sid+'  ',
        '**Date:** '+d.isoformat()+'  ',
        '**Start:** '+base.strftime('%H:%M')+'  ',
        '**End:** '+end.strftime('%H:%M')+'  ',
        '**Duration:** '+str(duration)+' minutes  ',
        '**Data provenance:** Fully fictional; simulated timestamps and conversation.', '',
        '## Conversation log',''
    ]
    for j,(m,s) in enumerate(beats):
        minute=(base+timedelta(minutes=j)).strftime('%H:%M')
        m=augment_mentor(m,style)
        s=augment_student(s,style)
        md.extend([f'### {minute}', '',f'**Mentor:** {m}', '',f'**Student:** {s}', ''])
    md.extend(['---','','*End of synthetic session. No subsequent intervention outcome or student dropout result is implied.*',''])
    content='\n'.join(md)
    path=output/f'session_{i:04d}.md'
    path.write_text(content,encoding='utf-8')
    return dict(session_id=sid,filename=f'sessions/session_{i:04d}.md',date=d.isoformat(),start=base.strftime('%H:%M'),end=end.strftime('%H:%M'),minutes=duration,primary_scenario=reason,secondary_scenario=secondary,support_type=action,support_status=status,writing_style=style,session_stage=stage,source='fully_synthetic',dropout_outcome='not_generated',sha256=hashlib.sha256(content.encode('utf-8')).hexdigest())

