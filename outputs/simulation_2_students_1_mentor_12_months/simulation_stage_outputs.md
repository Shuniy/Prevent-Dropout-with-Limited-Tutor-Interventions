# Simulation stage outputs: 2 students, 1 mentor, 12 months

Run date: 4 November 2026. Seed: 42. Model: `qwen3.5:latest`. Students are the first two records in the supplied synthetic population. Defaults: five planned sessions per student, mentor capacity 10 students / 50 sessions per month, budget 10,000 units, cost 1 unit per recorded session.

This is a replay of synthetic recorded interventions. Each student receives at most one programme; the programme is processed in its allocation month, rather than spread over 12 months. No new case-linking logic or cross-case interpretation has been added. The existing runner selects a recorded history by support type; RAG outputs below are presented independently in execution order, without source-case links or a student-to-history mapping.

The RAG section contains private synthetic narrative findings for this requested review. The standard school exports remain separate and contain only allowlisted outcomes.


## Output 1 - Student allocation to mentors

Allocations at admission, before recorded-session costs are reconciled:


```json
[
  {
    "student_id": "SYN00002",
    "mentor_id": "mentor-1",
    "support_type": "wellbeing_checkin",
    "month": 1,
    "sessions": 5,
    "cost_units": 5.0,
    "completed_sessions": null
  },
  {
    "student_id": "SYN00001",
    "mentor_id": "mentor-1",
    "support_type": "device_access",
    "month": 1,
    "sessions": 5,
    "cost_units": 5.0,
    "completed_sessions": null
  }
]
```


## Output 2 - Student profiles, needs, scores and mentor selection reasons

Need score is the highest rule-based need severity on a 0–1 scale, not a predicted dropout probability. Students are considered in descending score order; seeded shuffling breaks ties. Mentor eligibility checks support skills, caseload, session capacity and budget. Among eligible mentors, the lowest caseload and then mentor ID decide selection.


### SYN00001


```json
{
  "source_profile": {
    "student_id": "SYN00001",
    "school_id": "MS",
    "age_years": 15,
    "sex_source": "F",
    "rural_residence": true,
    "family_size_gt3": false,
    "parents_apart": false,
    "mother_education_code": 1,
    "father_education_code": 1,
    "mother_job": "at_home",
    "father_job": "other",
    "guardian": "mother",
    "travel_time_category": 2,
    "study_time_category": 1,
    "past_failures_count": 0,
    "school_support_existing": false,
    "family_support_existing": true,
    "paid_classes_existing": false,
    "extracurricular": false,
    "nursery_attended": true,
    "higher_education_aspiration": false,
    "internet_at_home": false,
    "family_relationship_rating": 5,
    "health_self_rating": 4,
    "anchor_grade1_0_20": 9,
    "math_grade1_0_20": null,
    "initial_attendance_fraction_assumed": 0.9178379883,
    "initial_engagement_assumed": 0.8011652565,
    "weeks_since_offer": 0,
    "support_sessions_completed": 0,
    "enrolled_initial_assumed": true,
    "financial_need_verified": null
  },
  "needs": [
    {
      "problem": "digital_access",
      "support_type": "device_access",
      "severity": 0.5
    },
    {
      "problem": "study_routine",
      "support_type": "homework_support",
      "severity": 0.25
    },
    {
      "problem": "learning_gap",
      "support_type": "tutoring",
      "severity": 0.1
    }
  ],
  "need_score": 0.5,
  "baseline": {
    "anchor_grade": 9,
    "math_grade": null,
    "attendance_fraction": 0.9178379883,
    "engagement": 0.8011652565,
    "enrolled": true,
    "support_sessions_completed": 0,
    "attendance_improved": "unknown",
    "primary_barrier_resolved": "unknown",
    "intervention_helpful": "unknown",
    "evaluation_reason": "baseline",
    "need_score": 0.5,
    "primary_support_type": "device_access"
  }
}
```

Selected for `mentor-1` because the primary need requires `device_access` and the sole generalist mentor supports that service. The mentor had sufficient student and session capacity, and the budget covered 5 sessions (5.0 units reserved). There was no competing mentor to rank.


### SYN00002


```json
{
  "source_profile": {
    "student_id": "SYN00002",
    "school_id": "MS",
    "age_years": 17,
    "sex_source": "M",
    "rural_residence": false,
    "family_size_gt3": true,
    "parents_apart": false,
    "mother_education_code": 1,
    "father_education_code": 1,
    "mother_job": "at_home",
    "father_job": "services",
    "guardian": "mother",
    "travel_time_category": 3,
    "study_time_category": 2,
    "past_failures_count": 0,
    "school_support_existing": false,
    "family_support_existing": false,
    "paid_classes_existing": false,
    "extracurricular": false,
    "nursery_attended": true,
    "higher_education_aspiration": true,
    "internet_at_home": true,
    "family_relationship_rating": 5,
    "health_self_rating": 1,
    "anchor_grade1_0_20": 10,
    "math_grade1_0_20": null,
    "initial_attendance_fraction_assumed": 0.7920625644,
    "initial_engagement_assumed": 0.7805127216,
    "weeks_since_offer": 0,
    "support_sessions_completed": 0,
    "enrolled_initial_assumed": true,
    "financial_need_verified": null
  },
  "needs": [
    {
      "problem": "wellbeing_checkin",
      "support_type": "wellbeing_checkin",
      "severity": 0.6667
    },
    {
      "problem": "long_journey",
      "support_type": "transport_assessment",
      "severity": 0.5
    },
    {
      "problem": "attendance_routine",
      "support_type": "attendance_planning",
      "severity": 0.2079
    }
  ],
  "need_score": 0.6667,
  "baseline": {
    "anchor_grade": 10,
    "math_grade": null,
    "attendance_fraction": 0.7920625644,
    "engagement": 0.7805127216,
    "enrolled": true,
    "support_sessions_completed": 0,
    "attendance_improved": "unknown",
    "primary_barrier_resolved": "unknown",
    "intervention_helpful": "unknown",
    "evaluation_reason": "baseline",
    "need_score": 0.6667,
    "primary_support_type": "wellbeing_checkin"
  }
}
```

Selected for `mentor-1` because the primary need requires `wellbeing_checkin` and the sole generalist mentor supports that service. The mentor had sufficient student and session capacity, and the budget covered 5 sessions (5.0 units reserved). There was no competing mentor to rank.


Mentor configuration:


```json
[
  {
    "mentor_id": "mentor-1",
    "support_types": [
      "attendance_planning",
      "device_access",
      "family_finances",
      "family_liaison",
      "homework_support",
      "language_support",
      "learning_access",
      "peer_support",
      "reentry_support",
      "school_meals",
      "transport_assessment",
      "tutoring",
      "wellbeing_checkin"
    ],
    "max_active_students": 10,
    "current_student_ids": [],
    "availability_by_step": [
      {
        "step": 1,
        "available_hours": 0.0,
        "max_sessions": 50
      },
      {
        "step": 2,
        "available_hours": 0.0,
        "max_sessions": 50
      },
      {
        "step": 3,
        "available_hours": 0.0,
        "max_sessions": 50
      },
      {
        "step": 4,
        "available_hours": 0.0,
        "max_sessions": 50
      },
      {
        "step": 5,
        "available_hours": 0.0,
        "max_sessions": 50
      },
      {
        "step": 6,
        "available_hours": 0.0,
        "max_sessions": 50
      },
      {
        "step": 7,
        "available_hours": 0.0,
        "max_sessions": 50
      },
      {
        "step": 8,
        "available_hours": 0.0,
        "max_sessions": 50
      },
      {
        "step": 9,
        "available_hours": 0.0,
        "max_sessions": 50
      },
      {
        "step": 10,
        "available_hours": 0.0,
        "max_sessions": 50
      },
      {
        "step": 11,
        "available_hours": 0.0,
        "max_sessions": 50
      },
      {
        "step": 12,
        "available_hours": 0.0,
        "max_sessions": 50
      }
    ],
    "cost_units_per_hour": 0.0,
    "cost_units_per_session": 1.0
  }
]
```


## Output 3 - Intervention results from RAG

These are the actual validated model findings saved at each session. Earlier validated findings and retrieved earlier passages from the same history feed later sessions. The final valid session supplies the programme conclusion. A generation or validation failure stops that programme's analysis; any saved partial findings are retained.


### RAG execution 1


```json
{
  "session_number": 1,
  "findings": {
    "session_summary": "The first mentoring session focused on establishing a collaborative approach where the student maintains control over shared details. The primary issue discussed is the difficulty balancing school responsibilities with other tasks, leading to exhaustion and uncertainty about routine changes. A practical exercise was attempted to identify manageable versus difficult moments in the school day; the student found quiet activities easier than managing multiple tasks simultaneously but remains unsure about repeating this alone.",
    "primary_concern": "Balancing school workload with other responsibilities, causing exhaustion and difficulty participating in class.",
    "tracked_details": [
      {
        "detail": "School attendance/participation",
        "status": "reported"
      },
      {
        "detail": "External support delivery",
        "status": "pending"
      }
    ],
    "intervention": {
      "type": "Mentoring session focusing on practical planning and identifying manageable moments",
      "status": "completed",
      "service_delivered": null
    },
    "outcome": {
      "primary_barrier_resolved": "unknown",
      "attendance_improved": "unknown",
      "intervention_helpful": "unknown"
    },
    "session_helpful": "unknown",
    "next_steps": [
      "Student to attempt a smaller version of the identified routine step.",
      "Notice one manageable moment and one difficult moment during the week.",
      "Check with relevant school staff or review dated records regarding support eligibility before making formal requests.",
      "If the planned step is unavailable, student will report this rather than marking it as completed."
    ],
    "uncertainties": [
      "Whether the student can repeat the identified exercise alone.",
      "Which specific part of the routine can currently be changed.",
      "Confirmation of school records or support eligibility status.",
      "Exact dates of recent incidents affecting the student's day."
    ],
    "conclusion": "The session progressed by validating the student's desire for practical, non-judgmental support and clarifying that no external services have been delivered yet. While the student agreed to try a smaller, adjustable routine step and noted that quiet activities are more manageable, significant uncertainties remain regarding eligibility checks, record verification, and the ability to execute plans independently. The session concluded with an agreement to keep private family details out of summaries and to distinguish between reported experiences and verified facts."
  }
}
```


```json
{
  "error": null,
  "conclusion": {
    "session_summary": "The first mentoring session focused on establishing a collaborative approach where the student maintains control over shared details. The primary issue discussed is the difficulty balancing school responsibilities with other tasks, leading to exhaustion and uncertainty about routine changes. A practical exercise was attempted to identify manageable versus difficult moments in the school day; the student found quiet activities easier than managing multiple tasks simultaneously but remains unsure about repeating this alone.",
    "primary_concern": "Balancing school workload with other responsibilities, causing exhaustion and difficulty participating in class.",
    "tracked_details": [
      {
        "detail": "School attendance/participation",
        "status": "reported"
      },
      {
        "detail": "External support delivery",
        "status": "pending"
      }
    ],
    "intervention": {
      "type": "Mentoring session focusing on practical planning and identifying manageable moments",
      "status": "completed",
      "service_delivered": null
    },
    "outcome": {
      "primary_barrier_resolved": "unknown",
      "attendance_improved": "unknown",
      "intervention_helpful": "unknown"
    },
    "session_helpful": "unknown",
    "next_steps": [
      "Student to attempt a smaller version of the identified routine step.",
      "Notice one manageable moment and one difficult moment during the week.",
      "Check with relevant school staff or review dated records regarding support eligibility before making formal requests.",
      "If the planned step is unavailable, student will report this rather than marking it as completed."
    ],
    "uncertainties": [
      "Whether the student can repeat the identified exercise alone.",
      "Which specific part of the routine can currently be changed.",
      "Confirmation of school records or support eligibility status.",
      "Exact dates of recent incidents affecting the student's day."
    ],
    "conclusion": "The session progressed by validating the student's desire for practical, non-judgmental support and clarifying that no external services have been delivered yet. While the student agreed to try a smaller, adjustable routine step and noted that quiet activities are more manageable, significant uncertainties remain regarding eligibility checks, record verification, and the ability to execute plans independently. The session concluded with an agreement to keep private family details out of summaries and to distinguish between reported experiences and verified facts."
  }
}
```


### RAG execution 2


```json
{
  "session_number": 1,
  "findings": {
    "session_summary": "The first mentoring session focused on establishing a collaborative approach where the student controls shared details and avoids assumptions about home circumstances or eligibility. The primary barrier identified is limited mobile data availability preventing access to video lessons and task submission, causing frustration and lost time. The student clarified that while they can attempt small steps (like checking school computer room availability), external support has not yet been delivered. Uncertainty remains regarding exact dates of incidents, the availability of free data, and whether specific services are confirmed.",
    "primary_concern": "Inability to complete school tasks due to lack of mobile data and device access constraints.",
    "tracked_details": [
      {
        "detail": "Data Availability",
        "status": "unresolved"
      },
      {
        "detail": "Service Eligibility/Confirmation",
        "status": "pending"
      },
      {
        "detail": "Exact Dates of Incidents",
        "status": "unknown"
      }
    ],
    "intervention": {
      "type": "Mentoring Session",
      "status": "completed",
      "service_delivered": null
    },
    "outcome": {
      "primary_barrier_resolved": "no",
      "attendance_improved": "unknown",
      "intervention_helpful": "unknown"
    },
    "session_helpful": "yes",
    "next_steps": [
      "Check school computer room availability within the student's schedule.",
      "Identify appropriate school contact (teacher or office) to confirm support options without assuming eligibility.",
      "Monitor if the proposed small steps can be repeated independently."
    ],
    "uncertainties": [
      "Whether free data is available.",
      "Confirmation of specific support services.",
      "Exact dates of recent technical failures."
    ],
    "conclusion": "Progression across this initial session involved shifting from general feelings to concrete examples of barriers (data limits). The student agreed to a manageable next step involving checking computer room availability but expressed uncertainty about repeating it alone. No external support was delivered; the session served as an information-gathering and planning exercise. Key issues regarding data access and service confirmation remain unresolved pending further checks."
  }
}
```


```json
{
  "session_number": 2,
  "findings": {
    "session_summary": "The second session revisited the agreed plan to check school computer room availability, which the student reported completing. While this specific step was successful, the wider barrier regarding device access and data limitations remains unresolved. The student tested a low-bandwidth/paper-based task during the session; while smaller files opened, typing long answers remained awkward. The primary difficulty identified is uncertainty about repeating these steps independently without external guidance. The student emphasized that no external support (like free data or confirmed services) has been delivered yet and requested that family details remain private in summaries.",
    "primary_concern": "Inability to complete school tasks due to persistent lack of mobile data, device access constraints, and uncertainty about repeating independent steps without teacher assistance.",
    "tracked_details": [
      {
        "detail": "Data Availability",
        "status": "unresolved"
      },
      {
        "detail": "Service Eligibility/Confirmation",
        "status": "pending"
      },
      {
        "detail": "Exact Dates of Incidents",
        "status": "unknown"
      },
      {
        "detail": "Independent Repetition of Steps",
        "status": "unresolved"
      }
    ],
    "intervention": {
      "type": "Mentoring Session",
      "status": "completed",
      "service_delivered": null
    },
    "outcome": {
      "primary_barrier_resolved": "no",
      "attendance_improved": "unknown",
      "intervention_helpful": "unknown"
    },
    "session_helpful": "yes",
    "next_steps": [
      "Ask whether the next assignment has an offline option.",
      "Seek teacher explanation for procedures if stuck on independent steps.",
      "Verify school policy or contact details before promising support."
    ],
    "uncertainties": [
      "Whether free data is available.",
      "Confirmation of specific support services.",
      "Exact dates of recent technical failures.",
      "Ability to repeat low-bandwidth tasks independently without help."
    ],
    "conclusion": "Progression across sessions shows the student successfully executing small, agreed-upon steps (checking computer room availability) but continues to face unresolved systemic barriers regarding data access and device limitations. The intervention remains helpful for planning but has not yet delivered external support or resolved the core technical constraints. Uncertainties regarding service confirmation and independent capability persist, requiring further verification of school resources before a definitive resolution can be reached."
  }
}
```


```json
{
  "error": null,
  "conclusion": {
    "session_summary": "The second session revisited the agreed plan to check school computer room availability, which the student reported completing. While this specific step was successful, the wider barrier regarding device access and data limitations remains unresolved. The student tested a low-bandwidth/paper-based task during the session; while smaller files opened, typing long answers remained awkward. The primary difficulty identified is uncertainty about repeating these steps independently without external guidance. The student emphasized that no external support (like free data or confirmed services) has been delivered yet and requested that family details remain private in summaries.",
    "primary_concern": "Inability to complete school tasks due to persistent lack of mobile data, device access constraints, and uncertainty about repeating independent steps without teacher assistance.",
    "tracked_details": [
      {
        "detail": "Data Availability",
        "status": "unresolved"
      },
      {
        "detail": "Service Eligibility/Confirmation",
        "status": "pending"
      },
      {
        "detail": "Exact Dates of Incidents",
        "status": "unknown"
      },
      {
        "detail": "Independent Repetition of Steps",
        "status": "unresolved"
      }
    ],
    "intervention": {
      "type": "Mentoring Session",
      "status": "completed",
      "service_delivered": null
    },
    "outcome": {
      "primary_barrier_resolved": "no",
      "attendance_improved": "unknown",
      "intervention_helpful": "unknown"
    },
    "session_helpful": "yes",
    "next_steps": [
      "Ask whether the next assignment has an offline option.",
      "Seek teacher explanation for procedures if stuck on independent steps.",
      "Verify school policy or contact details before promising support."
    ],
    "uncertainties": [
      "Whether free data is available.",
      "Confirmation of specific support services.",
      "Exact dates of recent technical failures.",
      "Ability to repeat low-bandwidth tasks independently without help."
    ],
    "conclusion": "Progression across sessions shows the student successfully executing small, agreed-upon steps (checking computer room availability) but continues to face unresolved systemic barriers regarding data access and device limitations. The intervention remains helpful for planning but has not yet delivered external support or resolved the core technical constraints. Uncertainties regarding service confirmation and independent capability persist, requiring further verification of school resources before a definitive resolution can be reached."
  }
}
```


## Output 4 - Processed intervention results

Scalar requests sent to Intervention:


```json
[
  {
    "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
    "programme_id": "7560fc61e4754893ad8cffc3d0d33ea4:SYN00002",
    "month": 1,
    "student_id": "SYN00002",
    "mentor_id": "mentor-1",
    "support_type": "wellbeing_checkin",
    "planned_sessions": 5
  },
  {
    "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
    "programme_id": "7560fc61e4754893ad8cffc3d0d33ea4:SYN00001",
    "month": 1,
    "student_id": "SYN00001",
    "mentor_id": "mentor-1",
    "support_type": "device_access",
    "planned_sessions": 5
  }
]
```


Immutable allowlisted results returned to School; private narrative findings are excluded:


```json
[
  {
    "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
    "programme_id": "7560fc61e4754893ad8cffc3d0d33ea4:SYN00002",
    "month": 1,
    "student_id": "SYN00002",
    "mentor_id": "mentor-1",
    "support_type": "wellbeing_checkin",
    "planned_sessions": 5,
    "sessions_completed": 1,
    "status": "incomplete",
    "analysis_status": "completed",
    "attendance_improved": "unknown",
    "primary_barrier_resolved": "unknown",
    "intervention_helpful": "unknown"
  },
  {
    "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
    "programme_id": "7560fc61e4754893ad8cffc3d0d33ea4:SYN00001",
    "month": 1,
    "student_id": "SYN00001",
    "mentor_id": "mentor-1",
    "support_type": "device_access",
    "planned_sessions": 5,
    "sessions_completed": 2,
    "status": "incomplete",
    "analysis_status": "completed",
    "attendance_improved": "unknown",
    "primary_barrier_resolved": "no",
    "intervention_helpful": "unknown"
  }
]
```


## Output 5 - Results processed by School and changes made

School validates programme identity and session counts, records participation, reconciles reserved costs, and applies known reported outcomes. Unknown or conflicting outcomes retain their prior values. Grades, attendance fraction, engagement and enrolment are not numerically changed by this policy.


```json
[
  {
    "student_id": "SYN00002",
    "month": 1,
    "before": {
      "anchor_grade": 10,
      "math_grade": null,
      "attendance_fraction": 0.7920625644,
      "engagement": 0.7805127216,
      "enrolled": true,
      "support_sessions_completed": 0,
      "attendance_improved": "unknown",
      "primary_barrier_resolved": "unknown",
      "intervention_helpful": "unknown",
      "evaluation_reason": "baseline",
      "need_score": 0.6667,
      "primary_support_type": "wellbeing_checkin"
    },
    "after": {
      "anchor_grade": 10,
      "math_grade": null,
      "attendance_fraction": 0.7920625644,
      "engagement": 0.7805127216,
      "enrolled": true,
      "support_sessions_completed": 1,
      "attendance_improved": "unknown",
      "primary_barrier_resolved": "unknown",
      "intervention_helpful": "unknown",
      "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
      "need_score": 0.6667,
      "primary_support_type": "wellbeing_checkin"
    },
    "spent_budget_before": 10.0,
    "spent_budget_after": 6.0
  },
  {
    "student_id": "SYN00001",
    "month": 1,
    "before": {
      "anchor_grade": 9,
      "math_grade": null,
      "attendance_fraction": 0.9178379883,
      "engagement": 0.8011652565,
      "enrolled": true,
      "support_sessions_completed": 0,
      "attendance_improved": "unknown",
      "primary_barrier_resolved": "unknown",
      "intervention_helpful": "unknown",
      "evaluation_reason": "baseline",
      "need_score": 0.5,
      "primary_support_type": "device_access"
    },
    "after": {
      "anchor_grade": 9,
      "math_grade": null,
      "attendance_fraction": 0.9178379883,
      "engagement": 0.8011652565,
      "enrolled": true,
      "support_sessions_completed": 2,
      "attendance_improved": "unknown",
      "primary_barrier_resolved": "no",
      "intervention_helpful": "unknown",
      "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
      "need_score": 0.5,
      "primary_support_type": "device_access"
    },
    "spent_budget_before": 6.0,
    "spent_budget_after": 3.0
  }
]
```


## Output 6 - Monthly school outputs (months 1–12)

Each month includes allocations, processed results, budget and before/after evaluations for both students. Later months do not introduce additional programmes for already assigned students.


### Month 1


```json
{
  "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
  "month": 1,
  "spent_budget": 3.0,
  "remaining_budget": 9997.0,
  "assignments": [
    {
      "student_id": "SYN00002",
      "mentor_id": "mentor-1",
      "support_type": "wellbeing_checkin",
      "month": 1,
      "sessions": 5,
      "cost_units": 1.0,
      "completed_sessions": 1
    },
    {
      "student_id": "SYN00001",
      "mentor_id": "mentor-1",
      "support_type": "device_access",
      "month": 1,
      "sessions": 5,
      "cost_units": 2.0,
      "completed_sessions": 2
    }
  ],
  "results": [
    {
      "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
      "programme_id": "7560fc61e4754893ad8cffc3d0d33ea4:SYN00002",
      "month": 1,
      "student_id": "SYN00002",
      "mentor_id": "mentor-1",
      "support_type": "wellbeing_checkin",
      "planned_sessions": 5,
      "sessions_completed": 1,
      "status": "incomplete",
      "analysis_status": "completed",
      "attendance_improved": "unknown",
      "primary_barrier_resolved": "unknown",
      "intervention_helpful": "unknown"
    },
    {
      "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
      "programme_id": "7560fc61e4754893ad8cffc3d0d33ea4:SYN00001",
      "month": 1,
      "student_id": "SYN00001",
      "mentor_id": "mentor-1",
      "support_type": "device_access",
      "planned_sessions": 5,
      "sessions_completed": 2,
      "status": "incomplete",
      "analysis_status": "completed",
      "attendance_improved": "unknown",
      "primary_barrier_resolved": "no",
      "intervention_helpful": "unknown"
    }
  ],
  "evaluations": [
    {
      "month": 1,
      "student_id": "SYN00001",
      "before": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 0,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "baseline",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      },
      "after": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      }
    },
    {
      "month": 1,
      "student_id": "SYN00002",
      "before": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 0,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "baseline",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      },
      "after": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      }
    }
  ]
}
```


### Month 2


```json
{
  "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
  "month": 2,
  "spent_budget": 3.0,
  "remaining_budget": 9997.0,
  "assignments": [],
  "results": [],
  "evaluations": [
    {
      "month": 2,
      "student_id": "SYN00001",
      "before": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      },
      "after": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      }
    },
    {
      "month": 2,
      "student_id": "SYN00002",
      "before": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      },
      "after": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      }
    }
  ]
}
```


### Month 3


```json
{
  "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
  "month": 3,
  "spent_budget": 3.0,
  "remaining_budget": 9997.0,
  "assignments": [],
  "results": [],
  "evaluations": [
    {
      "month": 3,
      "student_id": "SYN00001",
      "before": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      },
      "after": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      }
    },
    {
      "month": 3,
      "student_id": "SYN00002",
      "before": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      },
      "after": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      }
    }
  ]
}
```


### Month 4


```json
{
  "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
  "month": 4,
  "spent_budget": 3.0,
  "remaining_budget": 9997.0,
  "assignments": [],
  "results": [],
  "evaluations": [
    {
      "month": 4,
      "student_id": "SYN00001",
      "before": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      },
      "after": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      }
    },
    {
      "month": 4,
      "student_id": "SYN00002",
      "before": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      },
      "after": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      }
    }
  ]
}
```


### Month 5


```json
{
  "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
  "month": 5,
  "spent_budget": 3.0,
  "remaining_budget": 9997.0,
  "assignments": [],
  "results": [],
  "evaluations": [
    {
      "month": 5,
      "student_id": "SYN00001",
      "before": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      },
      "after": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      }
    },
    {
      "month": 5,
      "student_id": "SYN00002",
      "before": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      },
      "after": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      }
    }
  ]
}
```


### Month 6


```json
{
  "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
  "month": 6,
  "spent_budget": 3.0,
  "remaining_budget": 9997.0,
  "assignments": [],
  "results": [],
  "evaluations": [
    {
      "month": 6,
      "student_id": "SYN00001",
      "before": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      },
      "after": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      }
    },
    {
      "month": 6,
      "student_id": "SYN00002",
      "before": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      },
      "after": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      }
    }
  ]
}
```


### Month 7


```json
{
  "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
  "month": 7,
  "spent_budget": 3.0,
  "remaining_budget": 9997.0,
  "assignments": [],
  "results": [],
  "evaluations": [
    {
      "month": 7,
      "student_id": "SYN00001",
      "before": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      },
      "after": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      }
    },
    {
      "month": 7,
      "student_id": "SYN00002",
      "before": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      },
      "after": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      }
    }
  ]
}
```


### Month 8


```json
{
  "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
  "month": 8,
  "spent_budget": 3.0,
  "remaining_budget": 9997.0,
  "assignments": [],
  "results": [],
  "evaluations": [
    {
      "month": 8,
      "student_id": "SYN00001",
      "before": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      },
      "after": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      }
    },
    {
      "month": 8,
      "student_id": "SYN00002",
      "before": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      },
      "after": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      }
    }
  ]
}
```


### Month 9


```json
{
  "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
  "month": 9,
  "spent_budget": 3.0,
  "remaining_budget": 9997.0,
  "assignments": [],
  "results": [],
  "evaluations": [
    {
      "month": 9,
      "student_id": "SYN00001",
      "before": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      },
      "after": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      }
    },
    {
      "month": 9,
      "student_id": "SYN00002",
      "before": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      },
      "after": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      }
    }
  ]
}
```


### Month 10


```json
{
  "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
  "month": 10,
  "spent_budget": 3.0,
  "remaining_budget": 9997.0,
  "assignments": [],
  "results": [],
  "evaluations": [
    {
      "month": 10,
      "student_id": "SYN00001",
      "before": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      },
      "after": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      }
    },
    {
      "month": 10,
      "student_id": "SYN00002",
      "before": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      },
      "after": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      }
    }
  ]
}
```


### Month 11


```json
{
  "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
  "month": 11,
  "spent_budget": 3.0,
  "remaining_budget": 9997.0,
  "assignments": [],
  "results": [],
  "evaluations": [
    {
      "month": 11,
      "student_id": "SYN00001",
      "before": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      },
      "after": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      }
    },
    {
      "month": 11,
      "student_id": "SYN00002",
      "before": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      },
      "after": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      }
    }
  ]
}
```


### Month 12


```json
{
  "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
  "month": 12,
  "spent_budget": 3.0,
  "remaining_budget": 9997.0,
  "assignments": [],
  "results": [],
  "evaluations": [
    {
      "month": 12,
      "student_id": "SYN00001",
      "before": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      },
      "after": {
        "anchor_grade": 9,
        "math_grade": null,
        "attendance_fraction": 0.9178379883,
        "engagement": 0.8011652565,
        "enrolled": true,
        "support_sessions_completed": 2,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
        "need_score": 0.5,
        "primary_support_type": "device_access"
      }
    },
    {
      "month": 12,
      "student_id": "SYN00002",
      "before": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      },
      "after": {
        "anchor_grade": 10,
        "math_grade": null,
        "attendance_fraction": 0.7920625644,
        "engagement": 0.7805127216,
        "enrolled": true,
        "support_sessions_completed": 1,
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown",
        "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
        "need_score": 0.6667,
        "primary_support_type": "wellbeing_checkin"
      }
    }
  ]
}
```


## Output 7 - Final simulation report


```json
{
  "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
  "months": 12,
  "status": "finished",
  "output_dir": "/Users/shuniy/Documents/projects/school-dropout/outputs/simulation_2_students_1_mentor_12_months/school",
  "spent_budget": 3.0,
  "remaining_budget": 9997.0,
  "assignments": [
    {
      "student_id": "SYN00002",
      "mentor_id": "mentor-1",
      "support_type": "wellbeing_checkin",
      "month": 1,
      "sessions": 5,
      "cost_units": 1.0,
      "completed_sessions": 1
    },
    {
      "student_id": "SYN00001",
      "mentor_id": "mentor-1",
      "support_type": "device_access",
      "month": 1,
      "sessions": 5,
      "cost_units": 2.0,
      "completed_sessions": 2
    }
  ],
  "students": {
    "SYN00001": {
      "student_id": "SYN00001",
      "result": {
        "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
        "programme_id": "7560fc61e4754893ad8cffc3d0d33ea4:SYN00001",
        "month": 1,
        "student_id": "SYN00001",
        "mentor_id": "mentor-1",
        "support_type": "device_access",
        "planned_sessions": 5,
        "sessions_completed": 2,
        "status": "incomplete",
        "analysis_status": "completed",
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "no",
        "intervention_helpful": "unknown"
      },
      "unassigned_reason": null,
      "evaluations": [
        {
          "month": 1,
          "student_id": "SYN00001",
          "before": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 0,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "baseline",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          },
          "after": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          }
        },
        {
          "month": 2,
          "student_id": "SYN00001",
          "before": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          },
          "after": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          }
        },
        {
          "month": 3,
          "student_id": "SYN00001",
          "before": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          },
          "after": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          }
        },
        {
          "month": 4,
          "student_id": "SYN00001",
          "before": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          },
          "after": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          }
        },
        {
          "month": 5,
          "student_id": "SYN00001",
          "before": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          },
          "after": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          }
        },
        {
          "month": 6,
          "student_id": "SYN00001",
          "before": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          },
          "after": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          }
        },
        {
          "month": 7,
          "student_id": "SYN00001",
          "before": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          },
          "after": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          }
        },
        {
          "month": 8,
          "student_id": "SYN00001",
          "before": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          },
          "after": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          }
        },
        {
          "month": 9,
          "student_id": "SYN00001",
          "before": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          },
          "after": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          }
        },
        {
          "month": 10,
          "student_id": "SYN00001",
          "before": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          },
          "after": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          }
        },
        {
          "month": 11,
          "student_id": "SYN00001",
          "before": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          },
          "after": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          }
        },
        {
          "month": 12,
          "student_id": "SYN00001",
          "before": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          },
          "after": {
            "anchor_grade": 9,
            "math_grade": null,
            "attendance_fraction": 0.9178379883,
            "engagement": 0.8011652565,
            "enrolled": true,
            "support_sessions_completed": 2,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "no",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,intervention_helpful",
            "need_score": 0.5,
            "primary_support_type": "device_access"
          }
        }
      ]
    },
    "SYN00002": {
      "student_id": "SYN00002",
      "result": {
        "run_id": "7560fc61e4754893ad8cffc3d0d33ea4",
        "programme_id": "7560fc61e4754893ad8cffc3d0d33ea4:SYN00002",
        "month": 1,
        "student_id": "SYN00002",
        "mentor_id": "mentor-1",
        "support_type": "wellbeing_checkin",
        "planned_sessions": 5,
        "sessions_completed": 1,
        "status": "incomplete",
        "analysis_status": "completed",
        "attendance_improved": "unknown",
        "primary_barrier_resolved": "unknown",
        "intervention_helpful": "unknown"
      },
      "unassigned_reason": null,
      "evaluations": [
        {
          "month": 1,
          "student_id": "SYN00002",
          "before": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 0,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "baseline",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          },
          "after": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          }
        },
        {
          "month": 2,
          "student_id": "SYN00002",
          "before": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          },
          "after": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          }
        },
        {
          "month": 3,
          "student_id": "SYN00002",
          "before": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          },
          "after": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          }
        },
        {
          "month": 4,
          "student_id": "SYN00002",
          "before": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          },
          "after": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          }
        },
        {
          "month": 5,
          "student_id": "SYN00002",
          "before": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          },
          "after": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          }
        },
        {
          "month": 6,
          "student_id": "SYN00002",
          "before": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          },
          "after": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          }
        },
        {
          "month": 7,
          "student_id": "SYN00002",
          "before": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          },
          "after": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          }
        },
        {
          "month": 8,
          "student_id": "SYN00002",
          "before": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          },
          "after": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          }
        },
        {
          "month": 9,
          "student_id": "SYN00002",
          "before": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          },
          "after": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          }
        },
        {
          "month": 10,
          "student_id": "SYN00002",
          "before": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          },
          "after": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          }
        },
        {
          "month": 11,
          "student_id": "SYN00002",
          "before": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          },
          "after": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          }
        },
        {
          "month": 12,
          "student_id": "SYN00002",
          "before": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          },
          "after": {
            "anchor_grade": 10,
            "math_grade": null,
            "attendance_fraction": 0.7920625644,
            "engagement": 0.7805127216,
            "enrolled": true,
            "support_sessions_completed": 1,
            "attendance_improved": "unknown",
            "primary_barrier_resolved": "unknown",
            "intervention_helpful": "unknown",
            "evaluation_reason": "reported_outcomes_only; numeric_measures_unchanged; unknown_outcomes_unchanged:attendance_improved,primary_barrier_resolved,intervention_helpful",
            "need_score": 0.6667,
            "primary_support_type": "wellbeing_checkin"
          }
        }
      ]
    }
  }
}
```
