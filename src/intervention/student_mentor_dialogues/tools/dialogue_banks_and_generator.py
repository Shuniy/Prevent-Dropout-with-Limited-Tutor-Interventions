from __future__ import annotations
import random, csv, json, zipfile, hashlib, re
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import Counter

SEED=20261103
N=400
rng=random.Random(SEED)
root=Path(__file__).resolve().parent.parent
output=root/'generated'
output.mkdir(parents=True, exist_ok=True)

# All personas and incidents below are invented; no survey row or real child is used.
# Attributes are authored scenario ingredients, not independently validated gold annotations.
# Every item is a mentor/student exchange; generated minute labels are simulated dialogue timing.
TOPICS={
 'transport_cost': dict(
    overview='The bus fare has become difficult to cover on some mornings.',
    timeline='It became harder around the middle of last month, but I cannot remember the exact week.',
    pattern='It is usually worse near the end of the week when we have already spent money on other things.',
    example='Last Thursday I waited at the stop, then went home because I had no fare.',
    impact='When I arrive late or miss a day, I struggle to follow the next lesson.',
    attempt='I have walked a few times, but it takes a long time and I arrive tired.',
    constraint='I do not know whether our route is covered by any school scheme.',
    misconception='I do not skip school just because I dislike lessons.',
    uncertainty='I am not sure how many days the fare itself was the problem.',
    aspiration='I would like a reliable way of getting here without worrying every morning.',
    priority='Please find out whether transport help can even be considered.',
    actions=['transport_assessment','family_finances','attendance_planning']),
 'unreliable_bus': dict(
    overview='The morning bus sometimes does not show up on time.',
    timeline='It started happening more often after the route changed.',
    pattern='Some mornings it comes normally, and other mornings we wait a long time.',
    example='On Tuesday I reached the gate after the first lesson had finished.',
    impact='The late mark makes me anxious about going into class.',
    attempt='I tried leaving earlier, but there is no earlier bus I can use every day.',
    constraint='I cannot tell when the service will be delayed.',
    misconception='Being late does not always mean I got up late.',
    uncertainty='I have not kept all the bus times, so I cannot prove every delay.',
    aspiration='I want a predictable morning and to stop missing the first class.',
    priority='Could someone review my lateness separately from absences?',
    actions=['transport_assessment','attendance_planning']),
 'household_finances': dict(
    overview='Money is tight at home and I sometimes lack what classes require.',
    timeline='It got more noticeable after my parent lost some working hours.',
    pattern='Not every week is the same; sometimes we manage and sometimes we cannot.',
    example='I did not bring the requested materials for a project last week.',
    impact='I feel embarrassed and spend time worrying instead of concentrating.',
    attempt='I borrowed supplies once but I cannot keep borrowing everything.',
    constraint='I do not know exactly what support our household would qualify for.',
    misconception='A missing item does not mean my family is not interested in school.',
    uncertainty='I do not know our household income and would rather not guess.',
    aspiration='I would like to attend without feeling that I am constantly behind on costs.',
    priority='Please explain the available support and what information it requires.',
    actions=['family_finances','family_liaison','school_meals']),
 'caregiving': dict(
    overview='I sometimes help care for someone at home before school.',
    timeline='The morning routine changed when the usual caregiver started a new shift.',
    pattern='It happens on certain days, not every morning.',
    example='Last Monday I had to wait for an adult to come home before I could leave.',
    impact='I missed registration and spent the day worried about catching up.',
    attempt='I asked whether the routine could change, but no one has sorted it yet.',
    constraint='I do not control the adults’ schedules.',
    misconception='I am not saying I have to stay home every day.',
    uncertainty='I do not know the schedule for the next few weeks.',
    aspiration='I want to help at home and still be able to attend consistently.',
    priority='Can we plan around the difficult mornings without blaming my family?',
    actions=['family_liaison','attendance_planning']),
 'housing_changes': dict(
    overview='We have been staying in different places and my school routine keeps changing.',
    timeline='We moved temporarily several weeks ago.',
    pattern='Some weeks are settled; other weeks we do not know where we will be staying.',
    example='I left my workbook at another address and could not finish the assignment.',
    impact='It is hard to sleep, plan travel, and remember everything I need.',
    attempt='I keep my important books in one bag now, which helps a little.',
    constraint='I cannot promise when our address will stop changing.',
    misconception='I am not changing schools by choice.',
    uncertainty='We do not have a confirmed longer-term address yet.',
    aspiration='I want a stable place to do work and a way to keep coming to the same school.',
    priority='Could someone help me work out whom to contact about school arrangements?',
    actions=['family_liaison','transport_assessment','attendance_planning']),
 'food_access': dict(
    overview='Some mornings I come to school without having eaten enough.',
    timeline='It has happened more often in the last few weeks.',
    pattern='Not every day. It depends on what is available at home.',
    example='On Friday I felt hungry halfway through the first lesson.',
    impact='I found it difficult to pay attention, particularly before lunch.',
    attempt='I have brought something small when possible, but that is not always possible.',
    constraint='I do not know what help the school currently provides.',
    misconception='Being distracted in class does not mean I am trying to be rude.',
    uncertainty='I am not sure whether we meet the rules for any meal programme.',
    aspiration='I want to be able to focus instead of thinking about food.',
    priority='I would like to hear what meal support is available.',
    actions=['school_meals','family_finances','family_liaison']),
 'math_gap': dict(
    overview='I missed part of the maths course and now the new work does not make sense.',
    timeline='It started after I was absent during the fractions lessons.',
    pattern='It is especially difficult during algebra; other topics are better.',
    example='I could not do the equation on the board even after copying the example.',
    impact='My confidence drops and I leave questions blank.',
    attempt='I watched a short video, but I got stuck halfway through.',
    constraint='I need help with the basics before the class moves further ahead.',
    misconception='I am struggling with one part of maths, not refusing to learn everything.',
    uncertainty='I am not sure exactly which earlier step I misunderstood.',
    aspiration='I want to solve questions without always copying the answer.',
    priority='Can someone find the first concept I need to practise?',
    actions=['tutoring','homework_support','learning_access']),
 'reading_gap': dict(
    overview='Long reading assignments take me much longer than they seem to take others.',
    timeline='I have found longer texts difficult for quite a while.',
    pattern='Short passages are okay; unfamiliar words slow me down.',
    example='I spent the whole evening on two pages and did not finish the questions.',
    impact='I often understand less of the lesson because I am still reading the instructions.',
    attempt='I tried reading aloud and making notes, which sometimes helps.',
    constraint='I do not want the whole class to listen to me struggle.',
    misconception='I can read; I am not saying that I cannot read at all.',
    uncertainty='I have not had any assessment, and I do not know what is causing it.',
    aspiration='I would like strategies that let me keep up without feeling exposed.',
    priority='Could we look at an accessible way to practise reading?',
    actions=['tutoring','learning_access','homework_support']),
 'device_access': dict(
    overview='Several assignments need internet access, and I cannot always get online.',
    timeline='It became a problem when more homework moved to the online platform.',
    pattern='I can sometimes use a shared phone, but it is not always available.',
    example='I wrote my answers on paper because the upload page would not load.',
    impact='Some of my work is showing as missing even though I attempted it.',
    attempt='I used the library computer once, but its opening time did not always fit.',
    constraint='I cannot rely on having a personal laptop or steady connection.',
    misconception='A missing online upload does not always mean the homework was not done.',
    uncertainty='I do not know whether teachers will accept an offline version for each task.',
    aspiration='I want a reliable way to hand in the work I complete.',
    priority='Could we check whether I can use school equipment or submit differently?',
    actions=['device_access','homework_support','family_liaison']),
 'language_learning': dict(
    overview='I understand many lessons, but I sometimes miss important instructions in English.',
    timeline='This became more noticeable with the new subject vocabulary this term.',
    pattern='I can follow spoken examples better than long written explanations.',
    example='I understood the calculation but did not understand what the question was asking.',
    impact='I spend extra time translating words and sometimes finish late.',
    attempt='I keep a vocabulary list in my notebook.',
    constraint='I do not want teachers to assume I understand nothing.',
    misconception='I know the subject content in some lessons; the wording can be the problem.',
    uncertainty='I do not know which language-support sessions the school currently runs.',
    aspiration='I want to follow new topics without having to guess at instructions.',
    priority='Could we try a vocabulary or instruction-checking approach?',
    actions=['language_support','tutoring','learning_access']),
 'peer_bullying': dict(
    overview='A few students have been making comments that make school uncomfortable.',
    timeline='It began a few weeks ago and has happened on more than one day.',
    pattern='It happens mainly around breaks, not in every lesson.',
    example='Someone mocked my answer when I was walking out of class.',
    impact='I sometimes stay away from shared spaces and feel tense during the day.',
    attempt='I moved away from them, but that did not settle the situation.',
    constraint='I worry that a public confrontation could make things worse.',
    misconception='I am not saying everyone in my class is involved.',
    uncertainty='I do not know whether a staff member witnessed the incidents.',
    aspiration='I want to feel safe enough to concentrate on lessons.',
    priority='Can we discuss a safe way to tell the right staff without making it public?',
    actions=['wellbeing_checkin','family_liaison','peer_support']),
 'friendship_conflict': dict(
    overview='I had a disagreement with friends and now group work feels awkward.',
    timeline='It happened after a group project two weeks ago.',
    pattern='It is mainly difficult when we have to work together.',
    example='Last week no one answered when I asked which section I should do.',
    impact='I have stopped contributing as much in that class.',
    attempt='I tried sending a message to clear things up, but it did not resolve much.',
    constraint='I do not want a forced meeting if the others are not willing.',
    misconception='I am not asking the school to decide that one person is entirely wrong.',
    uncertainty='I do not know what the others think about discussing it.',
    aspiration='I want group work to be manageable even if we are not close friends.',
    priority='Could we discuss options without requiring everyone to meet?',
    actions=['peer_support','wellbeing_checkin','attendance_planning']),
 'exam_pressure': dict(
    overview='I get very worried before tests, and then I cannot show what I know.',
    timeline='The worry grew after two disappointing marks.',
    pattern='It is worse before timed assessments than during ordinary classwork.',
    example='I revised the night before but froze when I saw the first question.',
    impact='I sometimes avoid revision because it reminds me of the test.',
    attempt='I tried making a timetable but it had too much in it.',
    constraint='I need a plan small enough to follow.',
    misconception='I do want to sit the tests; I am not trying to get out of them.',
    uncertainty='I do not know whether my test marks reflect what I actually understand.',
    aspiration='I would like a calmer way to prepare and start questions.',
    priority='Could we practise a manageable revision routine?',
    actions=['tutoring','wellbeing_checkin','homework_support']),
 'learning_access': dict(
    overview='I have trouble following lessons when instructions come all at once.',
    timeline='I have noticed it more since the timetable became busier.',
    pattern='One step at a time is easier for me than several spoken directions.',
    example='I completed the first part but forgot what the next two tasks were.',
    impact='I lose time and sometimes look like I am not paying attention.',
    attempt='I write short reminders, but I do not always catch every instruction.',
    constraint='I would rather explore practical adjustments before making assumptions about why this happens.',
    misconception='This does not mean I have a diagnosis or that I cannot do the work.',
    uncertainty='I do not know what adjustments a teacher can reasonably offer.',
    aspiration='I would like to know the steps clearly and finish more tasks.',
    priority='Could we try a written checklist or smaller steps?',
    actions=['learning_access','tutoring','homework_support']),
 'health_appointments': dict(
    overview='I have been absent for appointments and then I struggle to catch up.',
    timeline='The appointments became more frequent this term.',
    pattern='They are not on a fixed school day.',
    example='I missed a practical lesson when an appointment ran late.',
    impact='I return with missing notes and do not know what to prioritise.',
    attempt='I have asked classmates for notes, but they do not cover everything.',
    constraint='I prefer not to discuss private medical details in this meeting.',
    misconception='I am not saying I am unable to attend school most days.',
    uncertainty='I do not know the dates of all future appointments.',
    aspiration='I want a way to catch up that does not require explaining personal health details.',
    priority='Can we agree how work will be shared after authorised absences?',
    actions=['attendance_planning','homework_support','wellbeing_checkin']),
 'low_motivation': dict(
    overview='I feel disconnected from some lessons and have stopped trying as much.',
    timeline='The feeling has built up over the last couple of months.',
    pattern='I am more interested in practical activities than long written tasks.',
    example='I left a worksheet unfinished even though I had enough time.',
    impact='My marks are slipping and teachers have noticed I am quieter.',
    attempt='I tried setting a study goal, but it felt too big to keep going.',
    constraint='Being told to just try harder does not give me a starting point.',
    misconception='I do have interests and goals outside this difficult subject.',
    uncertainty='I am not sure whether the problem is boredom, confusion or both.',
    aspiration='I want to find a reason to keep up with the parts of school that matter.',
    priority='Could we work out one achievable goal for the next week?',
    actions=['wellbeing_checkin','tutoring','homework_support']),
 'school_transfer': dict(
    overview='I changed schools and the topics do not line up with what I studied before.',
    timeline='I joined this school earlier in the term.',
    pattern='Some subjects match, while others use books I have not seen.',
    example='The class referred to a project that started before I arrived.',
    impact='I feel as if I am behind even in subjects I used to enjoy.',
    attempt='I asked for the notes but received only part of the material.',
    constraint='I cannot immediately redo every lesson from the previous term.',
    misconception='Changing schools does not mean I am a new learner in every subject.',
    uncertainty='I do not know which earlier modules are essential to catch up on.',
    aspiration='I want to understand the new school routine and keep my subjects on track.',
    priority='Could someone map the missing topics and help me settle in?',
    actions=['reentry_support','tutoring','attendance_planning']),
 'attendance_dispute': dict(
    overview='Some attendance marks look wrong, and I think this is affecting how teachers see me.',
    timeline='I first noticed the issue when I saw the attendance summary last week.',
    pattern='I am not disputing every absence, just a couple of entries.',
    example='On one morning I arrived late, but the record appears to show a full absence.',
    impact='I feel unfairly judged and less comfortable asking for help.',
    attempt='I mentioned it to a teacher but do not know whether it was checked.',
    constraint='I do not have written proof for every late arrival.',
    misconception='Some of the other absences are real; I am not denying those.',
    uncertainty='The register needs checking before anyone knows the correct count.',
    aspiration='I would like the record reviewed and then a fair discussion about attendance.',
    priority='Please check the disputed dates instead of changing them just on my word.',
    actions=['attendance_planning','family_liaison']),
 'classroom_noise': dict(
    overview='It is hard for me to focus when the classroom is noisy.',
    timeline='It became more difficult after we moved rooms.',
    pattern='Quiet independent work is easier than crowded group activities.',
    example='I missed part of a demonstration because people were talking nearby.',
    impact='I ask for things to be repeated and sometimes fall behind.',
    attempt='I moved closer to the front once and could follow better.',
    constraint='I cannot choose a quiet place in every classroom.',
    misconception='I am not saying other students are always causing trouble.',
    uncertainty='I do not know which seating changes are possible.',
    aspiration='I want to hear instructions clearly and finish classwork.',
    priority='Could we ask about a quieter working spot or written directions?',
    actions=['learning_access','tutoring','wellbeing_checkin']),
 'missed_coursework': dict(
    overview='I have several unfinished assignments and do not know which to start with.',
    timeline='The backlog grew over a few weeks after I missed deadlines.',
    pattern='I can start small tasks, but bigger assignments make me stop.',
    example='I opened the project brief and could not decide what the first step was.',
    impact='I avoid checking the platform because the list makes me anxious.',
    attempt='I wrote down the deadlines, but I did not rank them.',
    constraint='I cannot realistically finish everything tonight.',
    misconception='A late assignment does not mean I did no work at all.',
    uncertainty='I do not know which deadlines can still be negotiated.',
    aspiration='I want a realistic order for finishing the most important work.',
    priority='Could we break the backlog into a short, agreed plan?',
    actions=['homework_support','tutoring','attendance_planning']),
 'part_time_work': dict(
    overview='I sometimes help with paid work outside school and feel exhausted afterward.',
    timeline='The work hours increased recently because the household needed help.',
    pattern='Some evenings are much later than others.',
    example='After a late shift I struggled to stay awake during morning revision.',
    impact='Homework takes longer and I occasionally arrive late.',
    attempt='I tried doing homework earlier, but the hours change unexpectedly.',
    constraint='I do not want to make commitments about work hours I cannot control.',
    misconception='I am not asking to leave education; I want a workable balance.',
    uncertainty='I cannot confirm what the next month of work will look like.',
    aspiration='I want enough rest and time to complete schoolwork.',
    priority='Can we talk about support with the timetable and family pressures?',
    actions=['family_liaison','family_finances','attendance_planning']),
 'safety_route': dict(
    overview='I feel uncomfortable on part of the route to school.',
    timeline='It has been concerning me since an incident near the crossing last month.',
    pattern='It is worse when I have to travel alone at an early time.',
    example='I waited for other people instead of using the crossing on my own.',
    impact='I can arrive late and feel distracted once I reach school.',
    attempt='I tried another path, but it takes substantially longer.',
    constraint='I do not want to give details in front of other students.',
    misconception='This is about feeling safe on the route, not about disliking school.',
    uncertainty='I am not sure if the council or school has already reviewed that location.',
    aspiration='I want a route that feels safe enough to use consistently.',
    priority='Could an appropriate adult help assess options without making assumptions?',
    actions=['transport_assessment','wellbeing_checkin','family_liaison']),
}

SUPPORTS={
 'tutoring': [
    ('If tutoring were available, what topic would you want to start with?', 'The first topic I stopped understanding, not the hardest chapter.'),
    ('Would short practice with feedback help more than another lecture?', 'Yes, I would like to try a few problems and see where I go wrong.'),
    ('How long could you concentrate on one practice block?', 'About twenty minutes, with a short break if I need it.'),
    ('Is it easier to ask questions alone or in a small group?', 'A small group might be okay, but one-to-one would feel safer at first.'),
    ('What would tell you that practice was useful?', 'If I can explain a step without reading the answer.'),
    ('Could we begin with one worked example rather than assuming you know the earlier steps?', 'Yes, starting slowly would help.'),
    ('Would you rather take home a short practice sheet or use an online exercise?', 'A short paper sheet would be more reliable for me.'),
    ('How should we respond if the first tutoring approach does not work?', 'Try a different explanation rather than just giving more of the same.'),
    ('Would a trial session be okay before committing to several sessions?', 'Yes, I would like to try it first.'),
 ],
 'family_liaison': [
    ('Would a conversation with a family liaison worker be helpful?', 'Maybe, if I understand what would be discussed first.'),
    ('What would you feel comfortable sharing with a family member?', 'The school difficulties, but not every personal thing I said today.'),
    ('Is there a trusted adult you would prefer us to contact?', 'There is someone at home, but I would like to speak with them first.'),
    ('Would a phone call or a meeting be easier for the family?', 'A phone call may fit better, depending on work hours.'),
    ('Do you want to help decide the wording of the first message?', 'Yes, I do not want it to sound as if I am being reported.'),
    ('What questions should a liaison worker avoid assuming answers to?', 'They should not assume the adults at home do not care.'),
    ('Should we check whether an interpreter or another communication option is needed?', 'We can ask rather than assuming.'),
    ('What would a useful family-school conversation achieve?', 'A realistic agreement on what each person can manage.'),
    ('If there is disagreement about the situation, what would help?', 'Hear both sides and check the records instead of picking a side.'),
 ],
 'transport_assessment': [
    ('Can we map the journey you usually take to school?', 'I normally use the bus and walk the last part.'),
    ('Would you be able to tell the support office which route you use?', 'Yes, although I might need to check the route number.'),
    ('Are the costs, reliability, or safety of the journey your main concern?', 'The problem is not the same every day; I would like someone to ask about each part.'),
    ('Would you be willing to keep a short record of travel difficulties?', 'I could write down the date and what happened.'),
    ('Do you know whether a pass or travel programme already exists?', 'No, I have not been given that information.'),
    ('Should the office check eligibility before asking your family for documents?', 'Yes, I would prefer to know what is required.'),
    ('Would a change in arrival arrangements help while the route is reviewed?', 'It might, but the teacher would need to agree.'),
    ('What would you do if transport help were not available?', 'I would still need to discuss an alternative plan.'),
    ('What information should remain marked as uncertain?', 'The number of days affected and whether any programme covers my journey.'),
 ],
 'family_finances': [
    ('Would you like information about school-related financial support?', 'Yes, but I do not want to promise that we qualify.'),
    ('Which school expense feels most urgent to discuss?', 'The expense that has been stopping me from taking part.'),
    ('Would you prefer to review general options before involving home?', 'Yes, I would like to understand them first.'),
    ('Do you have confirmed information about household income?', 'No, I do not know the exact amount.'),
    ('Is there a trusted adult who could review application requirements?', 'Probably, if the information is clear.'),
    ('How would you feel about an eligibility assessment?', 'I would consider it if someone explains what is recorded.'),
    ('What should we avoid promising today?', 'That money or a fee waiver is guaranteed.'),
    ('Would help with materials be useful even if other financial support is unavailable?', 'Yes, that could remove one practical difficulty.'),
    ('What kind of update would help you feel informed?', 'A simple answer about what has been checked and what has not.'),
 ],
 'attendance_planning': [
    ('Would it help to separate recorded attendance from the reasons behind it?', 'Yes, some marks and some reasons need checking.'),
    ('Can we identify the hardest point in the school morning?', 'Usually the first part, before I reach the classroom.'),
    ('Would an agreed way to report a delay be useful?', 'Yes, then staff would know what happened.'),
    ('Do you want to check the register together for specific dates?', 'Yes, but I may not remember every date precisely.'),
    ('Would an attendance goal for next week feel manageable?', 'A small goal would be better than asking for perfect attendance overnight.'),
    ('How should school respond if an agreed plan does not work?', 'Ask what happened instead of assuming I gave up.'),
    ('Could a teacher provide missed work in a predictable way?', 'That would make returning easier.'),
    ('Do you need a way to explain late arrival privately?', 'Yes, I do not want to explain it to the whole class.'),
    ('Would you be okay reviewing the plan after one week?', 'Yes, one week is enough to see whether it is practical.'),
 ],
 'wellbeing_checkin': [
    ('Would you feel comfortable having a regular private check-in at school?', 'Maybe. I would like to know who I would speak with.'),
    ('What makes it easier for you to talk when something is difficult?', 'Having time and not being interrupted.'),
    ('Do you prefer practical problem-solving or space to talk first?', 'Talking first, then we can think about a plan.'),
    ('Are there places at school where you currently feel comfortable?', 'There are a couple of rooms where it is quieter.'),
    ('Would you like me to explain which concerns staff may need to share for safety?', 'Yes, I want to know how that works.'),
    ('How would you recognise a helpful check-in?', 'I would feel heard and know what to do next.'),
    ('Would it help to identify an adult you can approach between appointments?', 'Yes, especially on difficult days.'),
    ('Can we avoid deciding today what is causing every feeling?', 'Yes, I am still figuring it out.'),
    ('Would you prefer a written reminder of the next contact?', 'A small note would help me remember.'),
 ],
 'homework_support': [
    ('Would you like to sort unfinished tasks by priority rather than by age?', 'Yes, the oldest task is not always the most urgent.'),
    ('Could you show me how you currently track assignments?', 'I have a list but it is mixed up.'),
    ('What size of homework task feels possible on a normal evening?', 'Something I can finish in twenty or thirty minutes.'),
    ('Would checking with teachers about which deadlines remain active help?', 'Yes, I do not know which tasks still count.'),
    ('Would you prefer a paper planner or the school platform?', 'A paper planner would be easier to see every day.'),
    ('What usually interrupts your homework time?', 'Sometimes other responsibilities or just not knowing how to begin.'),
    ('Could we break one assignment into a first action and a next action?', 'Yes, that sounds less overwhelming.'),
    ('How would you know when to ask for help instead of getting stuck?', 'If I cannot make progress after trying a few minutes.'),
    ('Would a short check-in on completed steps be useful?', 'Yes, as long as it is not another stressful deadline.'),
 ],
 'learning_access': [
    ('Would written instructions alongside spoken ones make tasks easier?', 'I think so. I can check them again if I lose my place.'),
    ('Do you want to try breaking instructions into numbered steps?', 'Yes, that would be clearer.'),
    ('Are there seating or classroom arrangements you want to discuss?', 'Possibly, if they are not too noticeable.'),
    ('What kind of example is easiest for you to follow?', 'One worked through slowly, with the steps shown.'),
    ('Would you be comfortable with a short learning-support discussion?', 'Yes, as long as no one decides I have a condition from one conversation.'),
    ('Should we ask teachers which adjustments they can actually provide?', 'Yes, I would rather have a realistic arrangement.'),
    ('What if one change helps in maths but not in another subject?', 'Then we should review subjects separately.'),
    ('Would an informal trial of a checklist be acceptable?', 'That would be okay.'),
    ('How should your feedback be collected after trying a change?', 'Just ask whether I followed the instructions more easily.'),
 ],
 'device_access': [
    ('What equipment do assignments require most often?', 'Mostly a browser and a way to upload files.'),
    ('Would school computer access help if a slot were available?', 'Yes, but I would need to know the opening times.'),
    ('Do you know whether the school has any loan devices?', 'No, I have never asked.'),
    ('Can you work offline and upload later for some assignments?', 'Sometimes, but it depends on what the teacher allows.'),
    ('Would checking teacher-approved paper alternatives be useful?', 'Yes, that could prevent missing-work marks.'),
    ('Is shared-device access predictable from one week to another?', 'Not always, and I cannot use it whenever I need.'),
    ('Would a device-assessment referral require a family conversation?', 'I would like to hear the rules before contacting home.'),
    ('What is the most important online task to make possible?', 'Submitting my own work on time.'),
    ('What if equipment is not available immediately?', 'I would want a temporary way to submit work.'),
 ],
 'school_meals': [
    ('Would you like to learn what meal or breakfast arrangements the school offers?', 'Yes, I do not know all the options.'),
    ('Would a quiet conversation about eligibility be preferable?', 'Yes, I would rather not discuss it in front of classmates.'),
    ('Do you know which forms or permissions might be required?', 'No, that would have to be checked.'),
    ('Would information about today’s provision be useful separately from longer-term aid?', 'Yes, especially if it is already available to students.'),
    ('Should the support office check the current criteria?', 'Yes, I do not want someone to assume I am eligible.'),
    ('What would make a school meal option practical for you?', 'Knowing when and where it is offered.'),
    ('Would you want a family member involved in a formal application?', 'If needed, but please explain it to me first.'),
    ('What would you like staff to understand about concentration in morning lessons?', 'Sometimes I am distracted by being hungry, not the subject.'),
    ('How would you like a decision about meal support communicated?', 'Privately and clearly.'),
 ],
 'language_support': [
    ('Would reviewing important subject words before a lesson be useful?', 'Yes, I could understand the instructions faster.'),
    ('Do you prefer hearing an example or seeing a written one?', 'Usually both together.'),
    ('Could you show a question that was difficult because of its wording?', 'Yes, I have one in my notebook.'),
    ('Would a small vocabulary list each week be manageable?', 'Yes, if it is not too long.'),
    ('Do you want extra time to ask about unfamiliar instructions?', 'Yes, without holding up the whole class.'),
    ('Should we avoid making assumptions about which languages you speak?', 'Please ask me rather than guessing.'),
    ('Would you like the teacher to check understanding of instructions privately?', 'That could help.'),
    ('What would show the support is useful?', 'I would answer more of the question instead of guessing what it means.'),
    ('If the extra vocabulary list is not enough, what next?', 'We could try another explanation or more practice.'),
 ],
 'peer_support': [
    ('Would speaking with a trusted peer or staff-facilitated group be helpful?', 'Maybe, but I do not want to be forced into a conversation.'),
    ('How much contact would feel comfortable right now?', 'A small amount, and only with people I trust.'),
    ('Would you prefer a staff member to help with group arrangements?', 'Yes, especially at the beginning.'),
    ('What should staff avoid doing?', 'Do not announce my situation to the whole class.'),
    ('Would an alternative group-work arrangement help temporarily?', 'Yes, while we work out what is practical.'),
    ('Do you know a peer you already feel safe working with?', 'There may be one person, but I want to ask them first.'),
    ('What would make a meeting feel voluntary?', 'Knowing I can say no and still get help.'),
    ('Should we separate an immediate safety concern from an ordinary disagreement?', 'Yes, those are not the same thing.'),
    ('How would you like feedback about any arrangement?', 'Privately and without blaming anyone beforehand.'),
 ],
 'reentry_support': [
    ('Could we map the topics covered before and after your school change?', 'Yes, then I could see what I actually missed.'),
    ('Are there routines here that still feel unfamiliar?', 'The assignment platform and some of the lesson times.'),
    ('Would a timetable guide or a buddy system be helpful?', 'A guide would be good. I am not sure about a buddy yet.'),
    ('Can we ask teachers for the essential earlier materials?', 'Yes, the main topics would be enough to begin.'),
    ('What do you already know well that we should not make you repeat?', 'Some of the basics from my previous school.'),
    ('Would one point of contact for questions help?', 'Yes, I get different answers from different people.'),
    ('How should we prioritise catching up?', 'The topics needed for next week’s lessons first.'),
    ('If a subject follows a different syllabus, what would help?', 'A short comparison of what changed.'),
    ('Could we review how settled you feel after another week?', 'Yes, I will probably know more by then.'),
 ],
}

SECONDARIES={
 'math_confidence': [
    ('How is your confidence in maths at the moment?', 'Lower than last term, especially when the teacher moves quickly.'),
    ('Would looking at one missing prerequisite be manageable?', 'Yes, I do not want another huge pile of work.'),
    ('Have you told your maths teacher where you get stuck?', 'Not yet; I find it awkward to interrupt.'),
    ('Should we keep the maths concern separate from the original attendance issue?', 'Yes, both matter but they are not identical.'),
 ],
 'missed_notes': [
    ('What happens to class notes when you miss a lesson?', 'I usually receive only a photo of someone’s page.'),
    ('Does that give you enough context to understand the topic?', 'Not always; it misses what the teacher explained aloud.'),
    ('Would a short catch-up summary from staff be useful?', 'Yes, if it says which part to do first.'),
    ('Should we check what the teacher can realistically share?', 'Yes, I do not expect someone to rewrite every lesson.'),
 ],
 'quiet_place': [
    ('Do you have a place where you can usually concentrate after school?', 'Sometimes, but there can be a lot going on at home.'),
    ('Would school study space help if it fits your schedule?', 'Possibly, depending on the time.'),
    ('Does noise interfere every evening?', 'No, some evenings are easier.'),
    ('Should we treat that as a separate study-access concern?', 'Yes, it affects homework rather than getting to school.'),
 ],
 'teacher_contact': [
    ('Is there a teacher you already feel comfortable approaching?', 'There is one, but I have not spoken about this.'),
    ('What would make that conversation easier?', 'Knowing what to say before I go.'),
    ('Would a short written question help you start?', 'Yes, I could show it if I get nervous.'),
    ('Should we ask before sharing your details with that teacher?', 'Please do.'),
 ],
 'exam_worry': [
    ('Have upcoming tests added pressure?', 'Yes, I worry about catching up before the next one.'),
    ('What happens when you try to revise?', 'I sometimes jump between topics without finishing one.'),
    ('Would a smaller revision target help?', 'Probably; one topic a day feels possible.'),
    ('Should we avoid interpreting that as not caring?', 'Yes, I do care about the result.'),
 ],
 'online_uploads': [
    ('Have online submissions been working reliably for you?', 'Not every time; I have had trouble with the platform.'),
    ('Is the problem finishing the work or sending it?', 'Sometimes the work is complete but not uploaded.'),
    ('Could we check one assignment status rather than guessing?', 'Yes, I can show the saved file.'),
    ('Should we confirm the teacher’s accepted submission method?', 'That would help.'),
 ],
 'morning_routine': [
    ('How predictable is your morning routine?', 'It changes on some days, so I cannot always plan well.'),
    ('Is the same reason behind every late arrival?', 'No, that would be too simple.'),
    ('Would writing down two or three mornings help us see a pattern?', 'Yes, I could try that.'),
    ('What should we avoid concluding before checking?', 'That I am always late because I chose to be.'),
 ],
 'belonging': [
    ('Do you feel connected to other people at school?', 'Some days, but I do not have a big group of friends.'),
    ('Is there an activity that makes school feel better?', 'I enjoy one practical class.'),
    ('Would joining another activity interest you?', 'Maybe, as long as it does not add too much pressure.'),
    ('Should we avoid assuming you are isolated all the time?', 'Yes, it is not like that every day.'),
 ],
 'deadline_confusion': [
    ('Are assignment deadlines clear to you?', 'Sometimes the platform and what I hear in class do not match.'),
    ('Could we verify one deadline together?', 'Yes, I brought the assignment list.'),
    ('Would a weekly task check be useful?', 'That would help me avoid guessing.'),
    ('Should we label any uncertain dates as needing confirmation?', 'Definitely.'),
 ],
 'fatigue': [
    ('Have you been feeling tired in lessons?', 'More than usual, but not every day.'),
    ('Have you noticed a particular pattern?', 'It can be worse after an unsettled evening.'),
    ('Would you like to talk about practical school supports without discussing private details?', 'Yes, that would be better.'),
    ('Should we avoid guessing at the cause of tiredness?', 'Yes, I do not know exactly why either.'),
 ],
 'attendance_record': [
    ('Do the dates in the attendance register match your memory?', 'One date looks wrong, but I am not sure about the others.'),
    ('Could you say which entry should be checked first?', 'The day I arrived late after the first class.'),
    ('Should the office verify the entry before changing it?', 'Yes, I understand it needs checking.'),
    ('Does a record correction by itself solve the original difficulty?', 'No, we still need to work on that.'),
 ],
}

INTRO=[
 ('Thanks for coming. Is it okay if we talk about how school has been going?', 'Yes, though I am not sure where to start.'),
 ('This is to understand what support might be useful, not to decide you have done something wrong. How does that sound?', 'That helps. I was worried I might be in trouble.'),
 ('We can distinguish things you know, things you think, and things we still need to check. Is that fair?', 'Yes, because I do not know every detail.'),
 ('What would you most like to get from today’s conversation?', 'I want a practical next step instead of just another warning.'),
 ('You can tell me when a question feels too personal. Are you comfortable continuing?', 'Yes. I might skip a few details.'),
 ('Is there something at school that is still going reasonably well?', 'There are lessons I enjoy, even though other things are difficult.'),
]

CORE_GENERAL=[
 ('What has a relatively good school day looked like recently?', 'I get here, know what I am doing, and can follow the first lesson.'),
 ('How does a more difficult day usually begin?', 'There is usually something unexpected before I can settle down.'),
 ('Has the problem affected every subject equally?', 'No, it is more noticeable in some lessons than others.'),
 ('How do you respond when you realise you have fallen behind?', 'Sometimes I try to catch up quietly, and sometimes I stop asking.'),
 ('Have you already explained part of this to another adult at school?', 'A little, but I did not explain the whole situation.'),
 ('What do you think a teacher notices from the outside?', 'They probably notice the missed work more than the reason for it.'),
 ('Is there anything we might be misunderstanding from the attendance or homework record?', 'Possibly. It would be better to check particular dates than guess.'),
 ('How certain are you about the timing of all this?', 'I remember some examples clearly but not every date.'),
 ('What has helped even briefly?', 'When I get a clear next step, I feel less stuck.'),
 ('What kind of response from school would make things harder?', 'Being called out in front of everyone would be difficult.'),
 ('Do you want your explanation written down as something you reported, rather than as a verified fact?', 'Yes, that is more accurate.'),
 ('Would it be fair to say there may be more than one reason for the difficulty?', 'Yes, I do not think one answer explains everything.'),
 ('Which part of the problem feels within your control?', 'I can try a plan, but I cannot control every circumstance.'),
 ('What would be unfair for us to assume about your family or motivation?', 'That people do not care just because something went wrong.'),
 ('If school records disagree with your recollection, how should we handle it?', 'Check the evidence first, and let me explain the date.'),
]

SECONDARY_GENERAL=[
 ('Apart from the main difficulty, is there another small thing affecting your school day?', 'There are a few smaller things, but I want to keep them separate.'),
 ('Which of those is most urgent for the next week?', 'The one that makes tomorrow’s lessons harder.'),
 ('Would dealing with everything at once be realistic?', 'No, I would rather start with one or two things.'),
 ('Have you noticed whether this changes between weekdays?', 'It does change, so one day might not describe the whole week.'),
 ('What information would help clarify this extra concern?', 'A specific date or a conversation with the teacher might help.'),
 ('Is that something you have directly seen, or something you have been told?', 'Some of it I saw myself; the rest needs checking.'),
 ('How would you prefer another staff member to hear about it?', 'A short accurate summary, not a dramatic story.'),
 ('Can we mark anything you are unsure about as unknown for now?', 'Yes. I do not want to make up an answer.'),
 ('Would a practical adjustment be more useful than a big promise?', 'Yes, I would rather start with something possible.'),
]

SUPPORT_GENERAL=[
 ('What would make an extra support session worth your time?', 'It would need to address a real obstacle, not just add another appointment.'),
 ('Is there a time in the school week when a short session could work?', 'Lunch or a planned break could work, depending on the day.'),
 ('Would you rather try one step and review it than commit indefinitely?', 'Yes, I would like to know whether it is useful first.'),
 ('Do you have any concerns about teachers or family members being contacted?', 'I would like to know what will be shared and why.'),
 ('If the first option is unavailable, would you want us to discuss alternatives?', 'Yes, but please be clear that alternatives are not guaranteed.'),
 ('How should we know whether a plan is practical for you?', 'Ask whether I can actually attend or use it, not just whether I agreed.'),
 ('Would it help to write down which parts are still waiting for confirmation?', 'Yes, then I will not mistake a possibility for a promise.'),
 ('Can we separate requesting help from actually receiving it?', 'Yes, I know those are different things.'),
 ('Do you want to be involved in deciding what information gets passed to support staff?', 'As much as possible, yes.'),
 ('If support is offered but you cannot take it up, what should happen?', 'I would like someone to ask about the timing or reason.'),
 ('Should we review what has been tried instead of assuming it worked?', 'Yes. Something being offered does not mean it helped.'),
 ('If there is a waiting list, what information would be useful?', 'Whether my request is on it and when it will be reviewed.'),
]

CLOSING=[
 ('Can I summarise what I heard and you tell me if I missed something?', 'Yes, I would like to check the wording.'),
 ('What should I record as your account rather than as a confirmed fact?', 'The examples I told you about that have not been checked.'),
 ('Which part of today’s discussion feels most useful?', 'Understanding what is possible and what still needs checking.'),
 ('Is there anything you want corrected in the summary?', 'Please do not make it sound as if we have checked facts that are still uncertain.'),
 ('Do you know who you can approach if the situation changes before the next meeting?', 'I can come back to you or ask the support office.'),
 ('Would a brief follow-up next week be reasonable?', 'Yes, unless the timetable needs changing.'),
 ('What should we check at that follow-up?', 'Whether anything has changed, and whether the approach still makes sense.'),
 ('Is there anything else you want to add before we finish?', 'Not right now. Thank you for listening.'),
]

# Plausible but not falsely certain; the status is explicitly spoken during each session.
STATUS={
 'inquiry_pending': (
   ('At this point I can only make an inquiry; I cannot say that the support has been approved. Is that clear?', 'Yes, an inquiry is not the same as receiving the support.'),
   ('I will record the request as pending a response from the relevant team.', 'Please let me know what they say, even if it is a no.'),
 ),
 'information_only': (
   ('Would you prefer information first rather than making a request today?', 'Yes, I want to understand the options before deciding.'),
   ('I will record that we discussed options but did not submit an application or arrange a service.', 'That matches what we agreed.'),
 ),
 'declined': (
   ('Do you want to take up the proposed extra support now?', 'Not at the moment. I would like time to think about it.'),
   ('I will record that you declined the offer today, not that the underlying concern is resolved.', 'Thank you. I might ask again later.'),
 ),
 'assessment_requested': (
   ('Would you like me to request an assessment of available support, without assuming the outcome?', 'Yes, an assessment would be useful.'),
   ('I will record your agreement to the assessment request. Eligibility and any service are still unconfirmed.', 'Okay. Please tell me what information is needed.'),
 ),
 'followup_planned': (
   ('Would you be willing to review the idea again after checking your timetable?', 'Yes, I can check and come back with an answer.'),
   ('I will mark a follow-up discussion as planned; no additional service has been booked.', 'That is accurate.'),
 ),
}

# Topic-specific clarification exchanges: deliberately nuanced/uncertain and non-diagnostic.
TOPIC_QUESTIONS=[
 ('What first made you notice the difficulty?', 'overview'),
 ('When did it become more noticeable?', 'timeline'),
 ('Does it affect every day in the same way?', 'pattern'),
 ('Can you describe one particular occasion without guessing at other days?', 'example'),
 ('What happens to learning or attendance afterward?', 'impact'),
 ('What have you already tried yourself?', 'attempt'),
 ('What is outside your control here?', 'constraint'),
 ('What would be a mistaken conclusion from that story?', 'misconception'),
 ('Which details are still unknown or need checking?', 'uncertainty'),
 ('If we look ahead a little, what would you like school to feel like?', 'aspiration'),
 ('What should be the first question we try to resolve?', 'priority'),
]

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

