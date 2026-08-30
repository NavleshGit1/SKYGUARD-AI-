# SkyGuard AI — Beginner's Guide (Start From Zero)
### What We're Building, In Plain Language, And How Every Piece Connects to the Next

This version assumes you know nothing yet. No jargon left unexplained. Think of this as building a factory assembly line — each station does one job, then hands the product to the next station. We'll go station by station.

---

## The One-Sentence Version

**We take weather readings (temperature, pressure, humidity), pass them through a chain of checks that spot "this looks wrong," and show the results on a screen with an alert — and we explain WHY each reading looked wrong.**

Everything below is just: what are the stations on this assembly line, and how does data physically flow from one to the next.

---

## The Big Picture — 8 Stations on One Conveyor Belt

Picture a conveyor belt. A weather reading gets placed on it at Station 1, and it moves forward, getting checked and stamped at each station, until it reaches Station 8 where you finally see it on a screen.

```
STATION 1: Where the data comes from
      ↓
STATION 2: The mailroom (data comes in, gets sorted/checked)
      ↓
STATION 3: The prep table (raw numbers get turned into useful clues)
      ↓
STATION 4: The panel of judges (multiple checks vote: normal or weird?)
      ↓
STATION 5: The explainer (says WHY it was flagged, in plain words)
      ↓
STATION 6: The decision maker (what to do about it)
      ↓
STATION 7: The filing cabinet (everything gets saved)
      ↓
STATION 8: The TV screen (you see it, get alerted)
```

That's the entire project. Now let's open each station.

---

## STATION 1 — Where the Data Comes From

**What it is:** The actual source of temperature/pressure/humidity numbers.

Since we're not building our own hardware, this is either:
- **Real weather station data**, if you can get access to it (a website, a database, a file someone gives you), OR
- **A "pretend" data generator we build ourselves** — a small program that reads old historical weather data from a file and feeds it out number-by-number, pretending to be a live weather station. This is called a **simulator**, and it's a required piece regardless — even if you get real data later, you'll want this for testing and for demos.

**Think of it like:** A water tap. Doesn't matter if the water comes from a lake (real station) or from a tank you filled yourself (simulator) — what comes out the tap looks the same to everything downstream.

**How it connects to Station 2:** It sends out one reading at a time (or in small batches) — station name, time, temperature, pressure, humidity — over to the next station, like handing over a filled-out form.

---

## STATION 2 — The Mailroom (Ingestion)

**What it is:** The place that receives every incoming reading, checks it's not garbage, and organizes it before passing it along.

**Three jobs happen here:**
1. **Reception desk (message broker):** A piece of software (like Kafka, or something simpler) that catches every incoming reading so nothing gets lost, even if the next station is momentarily busy. Think of it as an inbox tray — readings pile up here safely instead of getting dropped if things move too fast.
2. **Quality check (schema validation):** Reject anything that's obviously broken — like a form with letters where a number should be. Broken entries get set aside in a separate "reject" pile instead of clogging the system.
3. **Stapling on extra info (metadata join):** Attach known facts about the station — like its location and altitude — onto the reading, pulled from a small reference list we keep (built in Station 7).

**How it connects to Station 3:** Clean, verified, fully-labeled readings get passed forward one at a time.

---

## STATION 3 — The Prep Table (Feature Engineering)

**What it is:** Turning a raw number into useful clues a detector can actually use. A single number like "23°C" doesn't tell you much by itself — you need context.

**What gets prepared here:**
- **"How does this compare to the last hour?"** — rolling average and how much it's bouncing around (statistics over a time window)
- **"Is it changing too fast?"** — the rate of change from one reading to the next (a jump of 20 degrees in one minute is suspicious)
- **"Is this normal for this time of year at this station?"** — comparing today's reading against what history says is typical for this station in this season (this is what stops the system from panicking over a hot desert day)
- **"Do the numbers even make physical sense together?"** — for example, humidity and temperature together let you calculate something called "dew point," and dew point can never be higher than the temperature. If the math breaks, something's wrong.
- **"Are we missing data?"** — how long since the last reading arrived, which hints at a communication problem.

**Think of it like:** A chef prepping ingredients before cooking — chopping, measuring, and labeling everything so the next stage (the actual cooking/judging) is fast and easy.

**How it connects to Station 4:** All these prepared "clues" get handed to every single detector in Station 4 at once — they all read from the same prep table.

---

## STATION 4 — The Panel of Judges (Detection Ensemble)

**What it is:** Several independent checks, each looking for a different KIND of problem, all voting at the same time on the same reading. No single judge is trusted alone — that's the whole point.

**The judges:**

| Judge | What it's watching for | How it decides |
|---|---|---|
| **The Rulebook Judge** | Impossible values (like -500°C) | Simple hard-coded limits, no learning needed |
| **The "Are You Frozen?" Judge** | A sensor stuck repeating the exact same number over and over | Checks if the value hasn't changed in a suspiciously long time |
| **The Statistics Judge** | A single wild spike | Learns what "normal spread" looks like and flags anything way outside it |
| **The Common Sense Judge** | Numbers that don't make sense together (e.g., dew point higher than temperature) | Learns what normal combinations of temperature+pressure+humidity look like, flags weird combos |
| **The Slow-Drift Judge** | A sensor going gradually wrong over weeks (not a sudden spike — a slow lean) | Watches the trend over a long time, not just the latest reading |
| **The Neighbor-Check Judge (optional, only if you have multiple stations with locations)** | Whether nearby stations are seeing something similar | Compares this station to its neighbors — if only ONE station is going crazy, it's probably a broken sensor, not real weather |

**The Vote Counter (fusion layer):** Each judge gives a score. This station adds them all up (with some judges weighted more important than others) into one final "how suspicious is this?" score, plus a "how many judges agree?" confidence score.

**Think of it like:** A panel of judges on a talent show — each judge scores independently, then the scores get combined into one final verdict.

**How it connects to Station 5:** The final "this reading is suspicious" verdict, plus which judges voted "guilty," gets passed forward.

---

## STATION 5 — The Explainer (Explainability & Root Cause)

**What it is:** Turning "the judges said this is weird" into "here's WHY, in a sentence a human can read." This matters because a flashing red light with no explanation isn't trustworthy or actionable.

**What happens here:**
- Look at WHICH judges voted "suspicious" — this pattern tells you the likely cause. For example:
  - Only the "Frozen" judge fired → probably a stuck sensor
  - Only the "Slow-Drift" judge fired → probably needs recalibration
  - The "Common Sense" judge fired and neighbors look normal → probably a local sensor fault
  - The "Common Sense" judge fired and neighbors ALSO look weird → probably a real weather event, not a fault!
- Turn that pattern into a plain sentence, like: *"Flagged because the humidity reading is inconsistent with the temperature reading, and no neighboring stations show similar conditions — likely a local sensor fault."*

**Think of it like:** A doctor not just saying "you're sick" but explaining "your symptoms suggest X because of Y."

**How it connects to Station 6:** The suspicious reading + its verdict + its plain-English explanation moves forward together as one package.

---

## STATION 6 — The Decision Maker (Action Layer)

**What it is:** Now that we know something's wrong and why, what do we actually DO?

**Jobs here:**
- **Guess a replacement value (optional):** If we're fairly sure what the "real" reading probably should have been, offer a best-guess corrected value — but always clearly labeled as a guess, never silently swapped in for the real data.
- **Track sensor health over time:** Keep a running scorecard per station — how often has it been flagged lately? Is it getting worse? This becomes a health score, like a report card.
- **Predict maintenance needs:** If a station's health score has been sliding downward for weeks, flag it as "probably needs a technician visit soon" — this is an educated guess based on trend, not a certainty.
- **Decide who to notify and how:** Route serious problems to urgent channels (SMS/alert), minor ones to just show up quietly on the dashboard — and avoid sending the same alert 50 times in a row for the same ongoing issue.

**How it connects to Station 7:** Everything decided here — the reading, the verdict, the explanation, any corrected value, the health score update — gets saved permanently.

---

## STATION 7 — The Filing Cabinet (Storage)

**What it is:** Where everything gets permanently saved so it can be looked up later.

**Four drawers in this cabinet:**
1. **Raw + cleaned readings drawer** — every reading ever received, plus the cleaned-up version if one was estimated
2. **Anomaly events drawer** — every time something was flagged, with full details (verdict, explanation, which judges fired)
3. **Model drawer** — saved copies of the "trained judges" so we don't have to retrain them from scratch every time
4. **Station info drawer** — the reference list of station locations, altitudes, and calibration history that Station 2 and Station 4 both pull from

**Think of it like:** An actual filing cabinet with labeled drawers — anyone (including future stations on this belt) can pull out exactly what they need.

**How it connects to Station 8:** The dashboard and API don't touch the conveyor belt directly — they only ever read from this filing cabinet.

---

## STATION 8 — The TV Screen (Dashboard & Alerts)

**What it is:** The part a human actually looks at.

**What's on screen:**
- A live view of all stations (map or list) color-coded by health
- Charts showing readings over time, with flagged moments highlighted
- A feed of alerts, each with its plain-English explanation
- A settings area (admin panel) for adjusting sensitivity or adding new stations

**Alerts also go out** by email, text message, or chat notification depending on how serious the issue is.

**How it connects backward:** Everything shown here is pulled from Station 7's filing cabinet through a single "front desk" (the API) — nothing on the screen talks directly to earlier stations.

---

## How All 8 Stations Physically Connect (The Wiring Diagram)

```
[STATION 1: Data Source / Simulator]
        |  (sends one reading at a time)
        v
[STATION 2: Mailroom — receive, validate, label]
        |  (sends clean, labeled reading)
        v
[STATION 3: Prep Table — turn raw numbers into clues]
        |  (sends the full set of clues)
        v
[STATION 4: Panel of Judges — everyone votes at once]
        |  (sends final verdict + which judges voted guilty)
        v
[STATION 5: Explainer — turns verdict into plain English]
        |  (sends verdict + explanation together)
        v
[STATION 6: Decision Maker — corrects, scores, alerts]
        |  (sends the final complete record)
        v
[STATION 7: Filing Cabinet — saves everything permanently]
        |  (sits there, waiting to be read)
        v
[STATION 8: TV Screen — dashboard reads from filing cabinet]
```

**The golden rule of connection:** Each station only ever talks to the ONE station directly before and after it. Station 8 (the dashboard) never reaches back to Station 3 or Station 1 directly — it only ever asks Station 7 (the filing cabinet) "what do you have saved?" This keeps the whole system simple: if you ever want to swap out one station's internals later, you only have to make sure it still hands off the same kind of package to its neighbor — nothing else has to change.

---

## What Order to Actually Build This In

You don't have to build Station 1 through 8 in a straight line — but this order makes testing easiest, since each step needs the one before it to already produce output:

1. **Build Station 1 (the simulator) first.** Nothing else can be tested without something feeding it data.
2. **Build Station 7 (filing cabinet) early too**, even though it's listed last — Stations 2 and 4 need somewhere to read/write reference data (like station locations) from day one.
3. **Build Station 2 (mailroom)** — now you can pipe simulator data through basic validation.
4. **Build Station 3 (prep table)** — now readings have useful clues attached.
5. **Build Station 4 (judges), one judge at a time.** Start with the easiest ones (Rulebook, Frozen-checker — no training needed) before the ones that need to "learn" (Statistics judge, Common Sense judge, Slow-Drift judge).
6. **Build Station 5 (explainer)** once the judges are voting reliably.
7. **Build Station 6 (decision maker)** once you trust the verdicts and explanations.
8. **Build Station 8 (dashboard) last** — it just displays what's already sitting in Station 7, so it can't really be built (or at least tested with real data) until everything before it works.

**Security** isn't its own station — it's more like a security guard walking the whole hallway: locks on the mailroom door (Station 2's entry point), locks on the filing cabinet (Station 7), and locks on the TV screen's front desk (Station 8's API) — added once each of those stations physically exists.

---

## Recap in One Paragraph

A reading is born at the Data Source, gets received and cleaned at the Mailroom, gets its useful clues prepared at the Prep Table, gets voted on by a Panel of Judges, gets a plain-English explanation from the Explainer, gets acted on by the Decision Maker, gets permanently saved in the Filing Cabinet, and finally gets shown to you on the TV Screen — with alerts going out along the way if something's seriously wrong. Every station only ever hands its output to the very next station in line, which is what makes the whole thing buildable one piece at a time.
