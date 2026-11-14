# Requirements Analysis

As of 14 Nov 2026. Sources:
- [BRIEF.md](BRIEF.md): the challenge text
- [Project Submission Guide](https://www.spaceappschallenge.org/resources/project-submission-guide/)
- [Judging and Awards Guide](https://www.spaceappschallenge.org/resources/judging-awards-guide/)
- [Participant FAQs](https://www.spaceappschallenge.org/resources/participant-faqs/)

If this doc and an official page disagree, the official page wins.

## 1. Hard requirements (must have)

Missing any of these means the project is either off-challenge or not eligible for Global Judging.

### From the challenge

| # | Requirement | How we meet it |
| --- | --- | --- |
| C1 | Identify and characterize **one or more Earth locations** as analogs | 2–3 new candidate sites from global search, each with a report card |
| C2 | The analogs are for **candidate permanent Moon-base locations** or **future Mars landing and exploration sites** | Covered. All ten Artemis candidate regions are in the `moon_polar` index (75–90°S, polar stereographic) and each returns ranked Earth analogs ([#26](https://github.com/FionaL7/AnalogAtlas/issues/26)). Numbers per region: [TARGET-SITES.md](TARGET-SITES.md) |
| C3 | Use **open NASA Earth data** together with Moon or Mars data | Earth: ASTER / GIBS, NASA POWER. Moon: LRO (LOLA, Diviner, LROC, Mini-RF) |
| C4 | Explain **what makes the location analogous** | Report card: dimensions where the analogy holds, with values from both bodies |
| C5 | Explain **where the analogy breaks down** | Report card: dimensions where it breaks, plus fixed rows for Earth's limits (gravity, vacuum or atmosphere, radiation) |
| C6 | Explain **how studying the Earth site helps** Moon or Mars exploration | A "what to test here" line on each report card (instruments, rover mobility, ISRU, operations) |
| C7 | Present findings as a **map, visualization, app or other tool** | React app with one map per body, search and report cards |

### From the Space Apps rules

| # | Requirement | Source |
| --- | --- | --- |
| R1 | Use **at least one NASA data source or resource** (required for a Global Award) | Submission Guide, "NASA Data" field |
| R2 | **Project demo:** a video of **30 seconds or less**, or **up to 7 slides** including title and intro. Going over either limit makes the project ineligible for Global Judging | Submission Guide |
| R3 | Demo and final project are hosted externally, with **public links that need no login, permission or registration** | Submission Guide |
| R4 | **Everything in English**, on the form and in linked materials. A video in another language needs English subtitles | Submission Guide |
| R5 | **Every required field** on the project form is filled in | Judging Guide |
| R6 | Click **"Submit for Judging" before Sunday 15 Nov, 11:59 p.m.** local time of our Local Event. For the Universal Event, it's the Team Owner's local time | Submission Guide |
| R7 | All team members are registered for the **same Local Event** (not waitlisted) and listed on the team page. Universal Event teams need at least 2 people; the maximum is 6 | Judging Guide |
| R8 | **Disclose all use of AI ("Super Intelligence") tools.** AI-generated images and video need a visible watermark; AI-generated code and data must be acknowledged in descriptive text and metadata | Submission Guide, "Use of SI" field |
| R9 | **List every external resource** (code, text, images, data), even open source, in the References field. No copyrighted material without permission | Judging Guide, submission checkboxes |
| R10 | **Original work:** tick the "Confirm All Work is Original" box | Submission Guide |
| R11 | No images, video, audio or likeness of anyone **under 18** | Submission Guide |
| R12 | **Respond to one official challenge,** and only one per team | Judging Guide, FAQs |

## 2. Signals the judges are looking for (should have)

### The five official judging criteria

Every project is scored on these five. The left column paraphrases what the Judging Guide describes as a top score (5).

| Criterion | What a 5 looks like | What it means for us |
| --- | --- | --- |
| **Impact** | Addresses a significant problem; wide reach; benefits many; quality far beyond expectations | Frame it as de-risking Artemis base sites and Mars landings: find better places to test hardware before flight |
| **Creativity** | A new approach nobody has tried; original and inventive | Cross-body search (CLIP + physics + radar) over the *whole* Earth, rather than one hand-picked site |
| **Validity** | Scientifically sound, technically feasible, fully developed, usable | Check the ML against independent data (the LOLA slope check), report precision@k, state limitations. The app must actually work |
| **Relevance** | Engages deeply with the challenge; **NASA data is integral**, not decorative | Every analog is backed by NASA measurements; Moon-base sites in scope (south pole); the brief's dimensions covered |
| **Presentation** | Well structured, compelling story, polished delivery | 30-second video or 7 slides with strong visuals. The Submission Guide says a strong demo raises the Presentation score, though most of the score comes from the submission itself |

### Signals from the challenge brief

The brief repeats these, so judges will look for them:

- **Beyond visual similarity:** show data, not just pictures that look alike. *(CLIP finds candidates; physics and radar confirm them.)*
- **Previously unrecognized analogs:** don't just rediscover well-known sites. *(Tag known sites; lead with new ones.)*
- **What breaks down:** an honest account of where the analogy fails, including Earth's limits.
- **How similar:** quantify it (a score for each dimension), not just "similar" or "not similar".
- **Scale:** narrow the match to a specific crater, valley or volcanic field, not a whole desert.
- **Processes as well as places:** name the shared process (impact, volcanism, ice dynamics, aeolian).
- **Multiple datasets combined:** terrain + temperature + radar + climate in one comparison.
- **Connection to exploration:** what you'd test there, and which risk it reduces.
- **Surprise us:** at least one unexpected site or connection to lead the demo.

### Signals from the submission rules

- **Partner-agency data** is "highly encouraged." We use CSA (RADARSAT, SAR tutorial), ESA (Copernicus, Sentinel) and possibly JAXA (PALSAR). Name them explicitly.
- **Global Awards we're best placed for:** Best Use of Data ("makes space data accessible or leverages it to a unique application") and Best Use of Science ("best and most valid use of the scientific method").

## 3. Dimensions of analogy (from the brief)

How we cover each dimension the brief lists:

| Dimension | AnalogAtlas today | Gap / idea |
| --- | --- | --- |
| Geology, mineralogy, surface materials | Partial: Diviner rock abundance on the Moon only | Earth surface material from Sentinel-2 or ASTER bands; lunar basalt vs anorthosite (mare vs highland) |
| Terrain, elevation, slope, roughness, craters | **Strong:** LOLA slope and relief, CLIP on hillshade, radar roughness planned | Crater counts from the Robbins catalog |
| Temperature, illumination, environmental extremes | **Strong at the pole:** LOLA mean solar illumination over 18.6 yr (`avg_illum`, `illum_max`) vs Earth's annual sunlit fraction and polar-night length; Diviner temperature anomaly; NASA POWER on Earth | Illumination matters most for a base, and it is the dimension Earth most clearly fails: no Earth site exceeds ~50% annual sunlight, against 90% on the Shackleton rim |
| Water, ice, permafrost, resources | Partial: `psr_frac` from the LOLA permanent-shadow map — cold traps are where the ice is | Pair PSRs with Earth permafrost explicitly; LEND or Mini-RF ice signatures |
| Communications and operations | `earth_vis`: fraction of time Earth is in line of sight | Has no Earth equivalent, so it reports as `no_equivalent` rather than a match |
| Dust, wind, erosion, surface processes | None | Mostly a Mars dimension (dust storms) |
| Biology, extremophiles, habitability, biosignatures | None | Mars only. Low priority for a Moon-first scope |
| Caves, lava tubes, subsurface | Weak: two lunar pit presets | Lunar pits vs Earth lava-tube fields; L-band radar (ALOS PALSAR) for the shallow subsurface |
| Landing, mobility, navigation, operations, construction | Partial: slope and rock abundance are landing hazards | Phrase the report card as landing, rover and base-construction criteria |

**Earth's limits** (the brief asks us to recognize these): reduced gravity, the lunar vacuum, the thin Martian atmosphere, and the radiation environment. Earth can't reproduce any of them. Every report card lists them as "breaks down".

We don't need to cover every dimension. The brief says an analog "does not have to match everything". Covering terrain, temperature and illumination, ice, and operations well beats covering all eight thinly.

## 4. Things to avoid

| Avoid | Why |
| --- | --- |
| **Only visual similarity** (CLIP results alone) | The brief explicitly asks us to go beyond it |
| **Leading with well-known sites** (Atacama, Haughton, Death Valley, Antarctica, Iceland, Hawaii) | The brief says these are already widely studied; we'd look like we're rediscovering them |
| **Treating a whole desert or continent as one analog** | The brief asks us to consider scale |
| **Claiming a perfect match** | No Earth site reproduces the Moon or Mars, and leaving out where an analogy breaks costs Validity |
| **Moon terrain that isn't a base site** | The challenge title is about *permanent Moon-base locations*; mid-latitude terrain alone is weaker on Relevance |
| **A demo over 30 seconds or 7 slides** | Ineligible for Global Judging. This is a hard limit |
| **Links that need a login,** or a private repo | Judges can't open it, so it can't be judged. Test every link in a private browser window |
| **Undisclosed AI use** | AI-generated code must be acknowledged in descriptive text and metadata (README, commit trailers); AI images and video need a watermark |
| **Using AI to come up with the idea** | The Submission Guide says AI tools should not be used to come up with the solution idea |
| **NASA logos, flags or mission insignia** in our app, slides or generated media | Not allowed in generated content under NASA's brand rules |
| **Unlisted or copyrighted assets** (fonts, images, music, code snippets) | Everything must be in References, and copyrighted material needs permission |
| **Images or voices of anyone under 18** | Not allowed |
| **Saving or editing after the deadline** | Projects saved or submitted after 11:59 p.m. local time aren't eligible |
| **A broken live demo at judging time** | Have a fallback: the repo, a recorded video and static screenshots |

## 5. Deliverable checklist (Space Apps submission)

### Project form (all fields required)

- [ ] **Project Name**: AnalogAtlas, plus a tagline
- [ ] **High-Level Project Summary**: what we built, how it answers the challenge, why it matters
- [ ] **Link to Project Demo**: public link to the ≤30 s video or ≤7-slide deck
- [ ] **Link to Final Project**: public link to the deployed app and/or the public GitHub repo
- [ ] **Detailed Project Description**: what it does, how it works, benefits, goals, tools and languages
- [ ] **Use of Super Intelligence (SI)**: how we used AI tools (for example Claude Code for code), stated plainly
- [ ] **NASA Data**: each NASA dataset by name (LRO LOLA, Diviner, LROC WAC via Moon Trek, Mini-RF, GIBS / Worldview, ASTER GDEM, NASA POWER, …)
- [ ] **Space Agency Partner Data and Other References**: CSA RCM, the CSA SAR tutorial, ESA Copernicus, JAXA (if used), NOAA ETOPO, the Robbins crater catalog, open-source libraries (PyTorch, open_clip, FAISS, rasterio, FastAPI, React, map library), CLIP model weights

### Demo

- [ ] Choose the format early: video (≤30 s) or slides (≤7, including title and intro)
- [ ] Story: the challenge → our idea → how it works (show the app) → how NASA and partner data make it possible → the future
- [ ] One concrete new analog with its report card, showing where it holds and where it breaks
- [ ] English, or English subtitles
- [ ] AI-generated visuals watermarked; no NASA logos
- [ ] Hosted publicly (YouTube, Google Drive or GitHub), checked in a private browser window

### Final project

- [ ] Public GitHub repo with a README: what it is, how to run it, the data sources, and a section on AI use
- [ ] Deployed app (frontend and API) reachable without a login. A FortiGuard web-filter classification for any new domain is optional but recommended
- [ ] Short write-up: the method, the candidate sites, limitations and Earth's limits
- [ ] Accuracy evidence: the LOLA slope check, precision@k, radar comparison results

### Before clicking submit

- [ ] Both team members registered for the same Local Event (not waitlisted) and listed on the Members tab
- [ ] Every link tested logged out
- [ ] Tick "Terms and Conditions" and "Confirm All Work is Original"
- [ ] Click **Submit for Judging** with a buffer before **Sun 15 Nov, 11:59 p.m. local time**. Resubmitting is allowed until the deadline, and only the last save counts
- [ ] Check the confirmation banner appears

## Open questions

- **Local Event or Universal Event?** The deadline's time zone depends on it, and so does the team-size rule (Universal Event teams need at least 2 people).
- **Video or slides** for the demo?
