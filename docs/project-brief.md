# Groundwork

## Business Operations Intelligence

**Project brief · MVP specification · Demonstration plan**

> Groundwork helps teams understand operational problems, investigate
> what is actually happening, prototype practical interventions, and
> measure whether those interventions improve business outcomes.

------------------------------------------------------------------------

## 1. Product overview

**Name:** Groundwork\
**Descriptor:** Business operations intelligence\
**Product type:** AI-assisted operational problem-solving workspace\
**Initial use case:** Customer-support operations for a mid-sized
e-commerce business\
**MVP format:** A focused web application with one tool-using AI agent
and an outcome measurement workflow.

Groundwork should feel like a useful internal business product---not a
project named after a job title, and not a generic chatbot with a
dashboard attached.

The product takes an operational problem from an initial, often vague
description through investigation, prioritisation, prototyping and
measurement.

### Product principle

**Start with the business problem. Use evidence to understand it. Build
only what is useful. Measure what changes.**

Groundwork is not intended to replace a human operator, consultant or
decision-maker. It helps them structure their thinking, analyse
operational evidence and move from discussion to action more
efficiently.

------------------------------------------------------------------------

## 2. Why this product exists

Businesses often describe symptoms rather than root causes:

-   "Our support team is overwhelmed."
-   "Customers are waiting too long."
-   "We hired more people, but service has not improved."
-   "We need AI to automate customer support."

These statements do not yet establish what is wrong, why it is
happening, or what intervention would be worthwhile.

A team can easily jump into building a chatbot or automation before
understanding the workflow. That risks delivering software without
improving the business.

Groundwork provides a repeatable way to:

1.  Capture the client's situation and understand its operating context.
2.  Turn observations into a clear, testable problem statement.
3.  Analyse available operational data.
4.  Identify and validate likely bottlenecks.
5.  Prioritise interventions based on impact, effort and risk.
6.  Prototype a practical workflow using AI.
7.  Define success measures and evaluate the result.

------------------------------------------------------------------------

## 3. Initial client scenario

The MVP will use one realistic, clearly bounded business scenario.

### Client

A mid-sized e-commerce company with an in-house customer-support team.

### Initial client statement

> "Our customer support team is overwhelmed. Customers are waiting too
> long for responses. We have hired more employees, but the problem
> hasn't improved."

This is a starting observation, not a confirmed diagnosis.

### Business context to investigate

-   Incoming support-ticket volume.
-   Ticket categories and complexity.
-   First-response time.
-   Resolution time.
-   Unresolved backlog.
-   Workload distribution across agents.
-   Ticket reassignment and escalation.
-   Operating hours and staffing coverage.
-   Existing response templates and workflows.

### Possible causes to investigate

These are hypotheses, not facts:

-   A small number of ticket categories may account for a
    disproportionate share of workload.
-   Tickets may be routed to the wrong teams.
-   Manual classification may delay assignment.
-   Workload may be unevenly distributed.
-   Repeated questions may consume time that could be handled through
    approved templates.
-   Staffing coverage may not match demand patterns.

Groundwork should distinguish between **what the client said, what the
data shows, what is inferred, and what remains unknown**.

------------------------------------------------------------------------

## 4. Product workflow

Groundwork has four connected stages.

### Stage 1 --- Discover

**Purpose:** Understand how the business operates before proposing a
solution.

Inputs:

-   Client's initial problem description.
-   Interview notes or meeting transcript.
-   Operational context.
-   Known constraints and desired outcomes.

Capabilities:

-   Organise unstructured notes into themes.
-   Identify stakeholders, workflows and affected users.
-   Ask useful follow-up questions.
-   Separate symptoms from confirmed facts.
-   Identify missing information and assumptions.
-   Draft a concise problem statement.

Expected output --- a **Problem Brief** containing:

-   Client and business context.
-   Current workflow.
-   Observed symptoms.
-   Affected stakeholders.
-   Business impact.
-   Known facts.
-   Assumptions and unknowns.
-   Follow-up questions.
-   A clear, testable problem statement.

Example problem statement:

> Customer-support tickets are not being triaged and assigned quickly
> enough, resulting in delayed first responses and a growing unresolved
> backlog. The underlying causes need to be validated through ticket and
> workflow data.

### Stage 2 --- Diagnose

**Purpose:** Investigate the problem using operational evidence.

For the MVP, the user uploads a CSV containing support-ticket records.

Potential fields:

  Field                Meaning
  -------------------- --------------------------------
  ticket_id            Unique ticket identifier
  created_at           Ticket creation timestamp
  first_response_at    First agent response timestamp
  resolved_at          Resolution timestamp
  category             Ticket category
  priority             Ticket priority
  assigned_agent       Current or initial agent
  status               Open, pending, resolved, etc.
  channel              Email, chat, web, etc.
  reassignment_count   Number of times reassigned
  customer_id          Anonymised customer identifier

The application should validate the uploaded file, explain missing or
invalid fields and show the data period and record count before
analysis.

Capabilities:

-   Calculate first-response and resolution times.
-   Analyse ticket volume by category, channel and time period.
-   Identify backlog and ageing tickets.
-   Compare agent workloads.
-   Examine reassignment patterns.
-   Find categories associated with longer response or resolution times.
-   Identify unusual patterns and data-quality issues.

Expected output --- a **Diagnostic Report** containing:

-   Key observations.
-   Supporting figures.
-   Potential bottlenecks.
-   Impacted workflows.
-   Confidence and limitations.
-   Questions requiring client validation.

Every finding should be traceable to a calculation or source record. The
LLM must not invent statistics or present correlation as proof of
causation.

### Stage 3 --- Build

**Purpose:** Turn the validated opportunity into a small, usable
prototype.

The MVP will include a customer-support triage agent.

#### Triage agent capabilities

Given a new support ticket, the agent should:

1.  Read the ticket content.
2.  Categorise the issue.
3.  Identify urgency and priority using defined rules.
4.  Recommend an appropriate queue or team.
5.  Draft a response using approved information or templates.
6.  Explain why it made its recommendation.
7.  Present the proposed action for human review.

Example:

**Incoming ticket**

> "I placed an order three days ago. The tracking page hasn't updated
> and I need the product urgently."

**Proposed agent output**

-   Category: Order tracking.
-   Suggested priority: Medium or High, according to the configured
    urgency rules.
-   Suggested queue: Order support.
-   Reason: Delivery-status query with an explicit urgency signal.
-   Draft response: A response based only on available order and policy
    information.
-   Action: Awaiting agent approval.

The prototype should demonstrate a real workflow, not merely generate a
conversational answer.

#### Human approval

For the MVP:

-   The agent proposes actions.
-   A human can approve, edit or reject them.
-   No customer-facing message is sent automatically.
-   No external system is modified without explicit approval.
-   Each decision is recorded.

#### MVP scope and prioritisation

  -----------------------------------------------------------------------
  Capability              Priority                Reason
  ----------------------- ----------------------- -----------------------
  CSV ingestion and       P0                      Required for
  validation                                      evidence-based analysis

  Operational metrics     P0                      Establishes the
                                                  baseline

  Ticket bottleneck       P0                      Helps diagnose the
  analysis                                        problem

  AI-assisted problem     P0                      Demonstrates discovery
  brief                                           and structuring

  Ticket triage agent     P0                      Demonstrates a working
                                                  AI prototype

  Human approval and      P0                      Makes actions
  audit log                                       reviewable

  KPI comparison          P0                      Connects work to
                                                  outcomes

  Live helpdesk           Later                   Not necessary to
  integration                                     validate the prototype

  Automatic customer      Later                   Requires stronger
  messaging                                       controls and validation

  Multi-agent             Not in MVP              Adds complexity without
  architecture                                    a demonstrated need
  -----------------------------------------------------------------------

### Stage 4 --- Measure

**Purpose:** Establish whether the proposed intervention makes a
meaningful difference.

Groundwork should define the measurement framework before evaluating the
intervention.

Potential KPIs:

  -----------------------------------------------------------------------
  KPI                     Definition              Direction
  ----------------------- ----------------------- -----------------------
  First-response time     Time between ticket     Lower is better
                          creation and first      
                          response                

  Resolution time         Time between ticket     Lower is better
                          creation and resolution 

  Backlog                 Number of unresolved    Lower is generally
                          tickets at a defined    better
                          point in time           

  SLA attainment          Share of eligible       Higher is better
                          tickets answered within 
                          the agreed SLA          

  Reassignment rate       Share of tickets        Lower may be better
                          reassigned at least     
                          once                    

  Triage time             Time from ticket        Lower is better
                          creation to correct     
                          assignment              

  Agent workload balance  Distribution of         More balanced, where
                          workload across agents  appropriate
  -----------------------------------------------------------------------

Each KPI should have:

-   A precise definition.
-   A calculation method.
-   A baseline.
-   A target.
-   A measurement period.
-   A data source.
-   An owner.
-   Any relevant caveats.

Targets must be based on the client's baseline, operating requirements
and realistic intervention assumptions. Do not invent achieved
improvements.

#### Pilot design

A simple pilot can compare two groups:

-   **Intervention group:** Tickets processed using the triage
    prototype.
-   **Comparison group:** Comparable tickets processed using the
    existing workflow.

Measure both groups over a defined period.

Where practical:

-   Compare similar ticket categories and priorities.
-   Account for changes in ticket volume and staffing.
-   Use the same KPI definitions.
-   Record exceptions and manual overrides.
-   Avoid claiming causation from a weak or non-comparable sample.

For a demonstration, a simulated pilot using clearly labelled synthetic
data is acceptable. It must be presented as a simulation, not as a real
client result.

Expected output --- an **Outcome Review** containing:

-   Baseline and comparison results.
-   KPI changes.
-   Sample sizes and measurement period.
-   What improved and what did not.
-   Limitations and confounding factors.
-   Recommendation: continue, modify, expand or stop.

------------------------------------------------------------------------

## 5. The AI agent

The agent is the central interactive element of Groundwork.

It should be able to understand a business objective, gather relevant
evidence, call tools, explain findings and propose an action.

### Example user request

"Why are customers waiting so long for support responses?"

### Expected agent workflow

1.  Clarify the relevant period or scope if necessary.
2.  Query available ticket data through approved tools.
3.  Calculate response-time distributions.
4.  Compare categories, channels and workloads.
5.  Identify the largest observed contributors to delays.
6.  Explain the findings with supporting figures.
7.  Distinguish evidence from hypotheses.
8.  Recommend the next investigation or intervention.

### Initial tool set

  Tool                       Responsibility
  -------------------------- ------------------------------------------
  `get_ticket_summary`       Retrieve ticket volume and status counts
  `get_response_metrics`     Calculate first-response metrics
  `get_resolution_metrics`   Calculate resolution metrics
  `get_category_breakdown`   Compare categories
  `get_agent_workload`       Analyse workload distribution
  `get_backlog_analysis`     Examine unresolved and ageing tickets
  `classify_ticket`          Categorise a ticket
  `recommend_priority`       Suggest priority using defined criteria
  `draft_ticket_response`    Prepare a response for review
  `create_triage_proposal`   Record a proposed action
  `record_human_decision`    Record approval, editing or rejection

### Technical approach

Use deterministic Python functions for calculations, validation and
database operations.

Use the LLM for:

-   Interpreting natural-language objectives.
-   Selecting relevant tools.
-   Summarising evidence.
-   Structuring problem statements.
-   Explaining recommendations.
-   Coordinating the workflow.

The LLM should not independently calculate or fabricate business
metrics.

### Agent reliability requirements

-   Validate tool arguments.
-   Handle missing or incomplete data.
-   Show the evidence behind important findings.
-   Maintain an audit trail.
-   Require approval before consequential actions.
-   Prevent duplicate actions.
-   Handle tool errors gracefully.
-   Avoid exposing sensitive customer data unnecessarily.

A single well-designed tool-using agent is sufficient for the MVP.
Multi-agent architecture is not a goal in itself.

------------------------------------------------------------------------

## 6. User experience and interface

Groundwork should feel like a professional internal consulting and
operations workspace.

### Main navigation

1.  Overview
2.  Engagements
3.  Discovery
4.  Diagnostics
5.  Prototypes
6.  Outcomes

### Suggested main screens

#### A. Engagement overview

Shows:

-   Client name and business context.
-   Current problem statement.
-   Engagement status.
-   Current stage.
-   Key findings.
-   Open questions.
-   Next actions.

#### B. Discovery workspace

Shows:

-   Client notes and transcript.
-   AI-generated themes.
-   Confirmed facts and assumptions.
-   Follow-up questions.
-   Editable problem brief.

#### C. Diagnostics workspace

Shows:

-   Dataset summary.
-   Data-quality warnings.
-   Operational metrics.
-   Category and workload analysis.
-   Evidence-backed findings.

#### D. Prototype workspace

Shows:

-   Ticket triage inbox.
-   Agent recommendations.
-   Priority and category.
-   Draft responses.
-   Approve, edit and reject actions.
-   Action history.

#### E. Outcome workspace

Shows:

-   KPI definitions.
-   Baseline and target.
-   Pilot measurements.
-   Comparison charts.
-   Outcome review.

### Design direction

-   Professional, calm and restrained.
-   Strong typography and information hierarchy.
-   Generous whitespace without wasting space.
-   Neutral surfaces and restrained accent colours.
-   Clear distinction between facts, hypotheses, recommendations and
    decisions.
-   Dense enough for real work, but not visually cluttered.

The interface should prioritise clarity and usability over decorative AI
imagery or excessive gradients.

------------------------------------------------------------------------

## 7. Technology stack

Keep the MVP easy to develop, run and demonstrate.

  Layer           Technology                  Purpose
  --------------- --------------------------- -------------------------------------
  Frontend        React                       Application interface
  Styling         Tailwind CSS                Consistent UI styling
  Backend         Python + FastAPI            APIs and application logic
  AI              LLM API with tool calling   Reasoning and workflow coordination
  Data analysis   Pandas + NumPy              Metrics and analysis
  Database        SQLite                      Initial persistence
  Charts          Recharts                    Operational and KPI visualisation
  Validation      Pydantic                    Structured input and output
  Deployment      Docker, optional            Reproducible execution

### Architecture principles

-   Keep the backend modular.
-   Separate business logic from AI orchestration.
-   Keep calculations deterministic and testable.
-   Use structured schemas for agent tools.
-   Store engagement data and agent decisions.
-   Keep API keys in environment variables.
-   Make the application usable with a supplied sample dataset.
-   Avoid unnecessary infrastructure in the first version.

------------------------------------------------------------------------

## 8. Data strategy

Use synthetic but realistic support-ticket data for the initial
demonstration.

The dataset should contain enough variation to reveal operational
patterns:

-   Multiple ticket categories.
-   Different priority levels.
-   Different channels.
-   Multiple agents.
-   Open, pending and resolved tickets.
-   Different first-response and resolution times.
-   Some reassigned tickets.
-   Some older unresolved tickets.
-   Periods of higher and lower ticket volume.

The data should be designed to support investigation, not to guarantee a
predetermined conclusion.

### Data quality checks

-   Missing timestamps.
-   Invalid timestamp ordering.
-   Duplicate ticket IDs.
-   Unknown categories.
-   Missing agent assignments.
-   Inconsistent statuses.
-   Implausible response or resolution durations.

Groundwork should disclose data limitations rather than silently
discarding records or producing misleading metrics.

------------------------------------------------------------------------

## 9. Deliverables

The project is complete when it includes:

1.  A working Groundwork web application.
2.  A client engagement and discovery workspace.
3.  CSV upload and validation.
4.  An operational diagnostic report.
5.  A tool-using support triage agent.
6.  Human approval and action history.
7.  A KPI baseline and outcome comparison.
8.  One realistic sample engagement.
9.  A concise case study documenting the problem-solving process.
10. A GitHub repository with setup instructions and a demonstration.

------------------------------------------------------------------------

## 10. Implementation plan

This is intentionally a small project. The first version should be
achievable in approximately **6--10 focused hours**, depending on AI
integration and UI polish.

### Phase 1 --- Foundation

-   Set up the React application and FastAPI backend.
-   Create the sample engagement.
-   Add synthetic ticket data.
-   Implement CSV ingestion and validation.

### Phase 2 --- Diagnose

-   Implement deterministic metric calculations.
-   Build the diagnostic view.
-   Add category, response-time and backlog analysis.
-   Generate evidence-backed findings.

### Phase 3 --- Agent

-   Integrate the LLM API.
-   Add structured tool calling.
-   Implement ticket classification and prioritisation.
-   Generate draft responses.
-   Add approval and audit logging.

### Phase 4 --- Outcomes

-   Define KPI baselines and targets.
-   Implement a simulated intervention comparison.
-   Display results.
-   Generate an outcome review.

### Phase 5 --- Demonstration

-   Test the complete workflow.
-   Prepare a sample client engagement.
-   Record a short demonstration.
-   Document assumptions, decisions and limitations.

If time is particularly limited, prioritise the complete journey over
the number of features. A smaller working workflow is better than five
unfinished modules.

------------------------------------------------------------------------

## 11. Five-minute demonstration plan

The demonstration should tell one coherent client story.

  -----------------------------------------------------------------------
  Time                                What to demonstrate
  ----------------------------------- -----------------------------------
  0:00--0:40                          Introduce the e-commerce client and
                                      its reported problem

  0:40--1:30                          Show how the problem is structured
                                      and what questions remain

  1:30--2:30                          Upload data and investigate
                                      operational bottlenecks

  2:30--3:40                          Ask the agent to investigate and
                                      demonstrate ticket triage

  3:40--4:30                          Review the proposed workflow and
                                      human approval

  4:30--5:00                          Show the KPI framework and outcome
                                      comparison
  -----------------------------------------------------------------------

Do not present simulated improvements as real-world achievements.

------------------------------------------------------------------------

## 12. What this demonstrates professionally

Groundwork is designed to provide evidence of the following
capabilities:

  -----------------------------------------------------------------------
  Capability                          Evidence in Groundwork
  ----------------------------------- -----------------------------------
  Business discovery                  Client context, interview notes and
                                      follow-up questions

  Problem structuring                 Testable problem statements

  Analytical thinking                 Operational data investigation

  AI prototyping                      Working support triage agent

  Agentic workflows                   Tool selection, execution and
                                      action proposals

  Product thinking                    MVP definition and prioritisation

  Engineering collaboration           Technical scope and modular
                                      architecture

  KPI ownership                       Baselines, targets and measurement
                                      definitions

  Outcome management                  Pilot comparison and outcome review

  Client communication                Structured diagnostic and review
                                      reports
  -----------------------------------------------------------------------

The important point is that the project demonstrates a way of working,
not just a collection of technologies.

------------------------------------------------------------------------

## 13. Resume positioning

Suggested project entry, to be updated after implementation:

### Groundwork --- Business Operations Intelligence

*React, Python, FastAPI, LLM Tool Calling, Pandas, SQLite*

-   Built an AI-assisted business operations workspace that transforms
    unstructured client problems into structured problem briefs,
    evidence-backed diagnostics and prioritised solution proposals.
-   Developed a tool-using AI agent for customer-support ticket
    analysis, classification, prioritisation and human-reviewed response
    drafting.
-   Implemented operational KPI analysis and a pilot measurement
    framework to evaluate workflow interventions against defined
    baselines.

Only retain statements corresponding to implemented and tested
functionality. Add actual evaluation results when available.

------------------------------------------------------------------------

## 14. Interview discussion points

Be ready to explain:

1.  Why did you choose customer-support operations?
2.  Why isn't the client's initial statement sufficient to define the
    problem?
3.  What information would you ask the client for before building?
4.  How did you distinguish symptoms from root causes?
5.  Why did you choose ticket triage as the first prototype?
6.  Which parts use AI, and which parts use deterministic logic?
7.  How do you prevent an incorrect agent recommendation from affecting
    a customer?
8.  How did you decide which features belonged in the MVP?
9.  Which KPI would you prioritise, and why?
10. How would you establish whether the intervention actually caused an
    improvement?
11. What would you do if the prototype failed to improve the KPI?
12. What would you build next if the client approved a production
    rollout?

Be honest about what is simulated, what is measured, what is assumed and
what remains unimplemented.

------------------------------------------------------------------------

## 15. Explicit non-goals

To protect the scope, the MVP will not attempt to:

-   Build a complete customer-support platform.
-   Replace an existing helpdesk.
-   Integrate with multiple external business systems.
-   Send customer messages autonomously.
-   Build a multi-agent framework without a practical need.
-   Support every industry and business scenario.
-   Claim actual business improvements from synthetic data.
-   Build a complex analytics platform.

These can be considered later if the initial prototype demonstrates a
meaningful opportunity.

------------------------------------------------------------------------

## 16. Definition of done

Groundwork's MVP is ready to demonstrate when a user can:

-   [ ] Open a sample client engagement.
-   [ ] Read and edit a structured problem brief.
-   [ ] Upload a support-ticket CSV.
-   [ ] See validation results and data limitations.
-   [ ] Review operational metrics and diagnostic findings.
-   [ ] Ask the AI agent questions about the data.
-   [ ] See which tools the agent used and the evidence behind its
    conclusions.
-   [ ] Submit a ticket to the triage agent.
-   [ ] Review, edit, approve or reject its recommendation.
-   [ ] Inspect an audit trail of decisions.
-   [ ] View KPI definitions, baselines and targets.
-   [ ] Review a clearly labelled simulated pilot comparison.

------------------------------------------------------------------------

## 17. The central idea

Groundwork should tell a simple story:

A client reports a problem. You do not immediately start coding.

You understand the business, ask better questions, investigate the
evidence, identify the highest-value opportunity, prototype a solution,
and establish how to measure whether it worked.

**The product is not the outcome. The business improvement is the
outcome.**

That is the mindset Groundwork is intended to demonstrate.
