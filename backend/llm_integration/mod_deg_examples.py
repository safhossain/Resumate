"""
Few-shot anchor for the discrete ``mod_deg`` levels and the ``faux`` axis.

Independent LLM calls have no relative baseline for what "low" vs "high" mean,
so this module supplies:
  1. a short RUBRIC defining each level on both axes, and
  2. compact, one-line worked examples across three different industries showing
     the SAME source field rewritten at all five levels, for both
     ``faux=false`` and ``faux=true``.

Kept deliberately compact: the goal is to anchor OUR intended gradient, not to
teach general tailoring (the base prompt already does that).

IMPORTANT: this text contains no ``{`` or ``}`` characters, so it is safe to
interpolate into the f-string ``SYSTEM_PROMPT`` and to ride along the
``.format()`` retry templates without brace-escaping issues. Keep it that way.
"""

_RUBRIC = """\
LEVEL RUBRIC (what each discrete level means - same intensity in every industry)
    faux=false (NO new facts; only rephrase / reorder / reframe existing truth):
      low         - keyword and terminology alignment + light polish; claims unchanged
      medium-low  - stronger action verbs; minor emphasis reordering
      medium      - reframe each field around the posting's top priorities; tighten wording
      medium-high - restructure phrasing; foreground the most relevant content; cut weak words
      high        - full rewrite of every field for maximal fit and impact; still strictly truthful

    faux=true (invention scales WITH the level; higher = bolder, the user accepts the risk):
      low         - at most 1-2 minor, plausible additions
      medium-low  - a few relevant additions (tools / contexts)
      medium      - moderate added skills / scope across fields
      medium-high - bold additions, including plausible metrics and tools
      high        - unrestricted plausible invention: scope, metrics, ownership - maximally tailored

    Treat the levels as a strict, monotonic increase in aggressiveness.
"""

_EXAMPLES = """\
WORKED EXAMPLES (one source line per industry, rewritten at each level)

[Software Engineer]  posting focus: senior backend - scalable microservices, Python, AWS, performance
  SOURCE: Built internal REST APIs in Python and fixed bugs for a team web app.
  faux=false:
    low         : Developed internal REST APIs in Python and resolved bugs for a team web application.
    medium-low  : Built and maintained internal REST APIs in Python, resolving bugs across a team web app.
    medium      : Engineered internal Python REST APIs and resolved backend defects for a team web app.
    medium-high : Designed and maintained internal Python REST API services, clearing backend defects to improve reliability.
    high        : Owned design and upkeep of internal Python REST API services, hardening backend reliability by clearing defects across a team web app.
  faux=true:
    low         : Built internal REST APIs in Python (basic AWS deploy) and fixed bugs for a team web app.
    medium-low  : Built and tested internal Python REST APIs deployed on AWS, resolving bugs across a team web app.
    medium      : Built scalable Python REST microservices on AWS, added CI tests, and resolved defects for a team web app.
    medium-high : Designed scalable Python microservices on AWS (ECS, Lambda), cut p95 latency ~30% via caching, and added CI/CD.
    high        : Architected high-throughput Python microservices on AWS (ECS, Lambda, DynamoDB), cut p95 latency 40%, scaled to 1M+ daily requests, and owned CI/CD and on-call.

[Registered Nurse]  posting focus: ICU / critical-care RN - acute care, ventilators, Epic EHR, fast-paced
  SOURCE: Cared for patients on a medical-surgical floor and recorded vitals.
  faux=false:
    low         : Provided patient care on a medical-surgical floor and documented vital signs.
    medium-low  : Delivered direct patient care on a med-surg floor, monitoring and documenting vital signs.
    medium      : Delivered acute patient care on a fast-paced med-surg floor, monitoring and charting vital signs.
    medium-high : Managed acute care on a high-acuity med-surg floor, closely tracking and charting vitals to flag deterioration.
    high        : Led bedside care for high-acuity med-surg patients in a fast-paced unit, tracking vitals to catch early deterioration and escalate promptly.
  faux=true:
    low         : Cared for med-surg patients, recorded vitals, and assisted with Epic EHR charting.
    medium-low  : Provided acute med-surg care, charted vitals in Epic, and supported ventilator-assisted patients.
    medium      : Delivered acute care for med-surg and step-down patients, managed ventilators, and charted in Epic.
    medium-high : Provided critical care for ventilated ICU patients, titrated drips per protocol, and precepted new nurses in Epic.
    high        : Led critical care for ventilated ICU patients, managed vasoactive drips and rapid-response events, precepted 5+ nurses, and drove an Epic workflow that cut charting time 25%.

[Brand / Growth Marketer]  posting focus: growth marketing manager - paid acquisition, analytics, ROAS, A/B testing
  SOURCE: Ran social media posts and helped with email campaigns for a small brand.
  faux=false:
    low         : Managed social media posts and supported email campaigns for a small brand.
    medium-low  : Managed social content and assisted email campaigns to grow a small brand's audience.
    medium      : Drove social media and email campaigns to grow audience and engagement for a small brand.
    medium-high : Owned social and email campaign execution, growing audience engagement for an emerging brand.
    high        : Led end-to-end social and email campaign strategy, building audience and engagement for an emerging brand.
  faux=true:
    low         : Ran social posts and email campaigns, tracking basic open and click rates for a small brand.
    medium-low  : Managed social and email campaigns, A/B tested subject lines, and reported open and click metrics.
    medium      : Ran paid social and email acquisition, A/B tested creative, and tracked ROAS in Google Analytics.
    medium-high : Owned paid acquisition across Meta and Google Ads, lifting ROAS ~35% via A/B testing and audience segmentation.
    high        : Directed a 50K/mo paid budget across Meta, Google, and TikTok Ads, lifting ROAS 60% and cutting CAC 30% through funnel analytics and continuous A/B testing.
"""

# Single embeddable block: rubric first (definitions), then the worked gradient.
MOD_DEG_GUIDE_SECTION = _RUBRIC + "\n" + _EXAMPLES
