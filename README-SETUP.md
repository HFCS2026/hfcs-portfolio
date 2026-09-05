# HFCS Live Portfolio — Setup Guide

**What this does.** Your crews already photograph every job twice: *Before Pictures* on the
Pre-Job Walkthrough form, *After Pictures* on the Job Closeout form. Today those photos sit
in Jotform and Google Drive and nobody ever puts them on the website. This turns them into
a live portfolio page that updates itself.

**How it flows.**

```
Crew submits walkthrough  ──┐
   (before photos)          │
                            ├──► every 3 hours, a free cloud job:
Crew submits closeout    ──┘        · matches before + after by customer and date
   (after photos)                   · checks YOU starred the job as website-worthy
                                    · strips GPS out of the photos
                                    · shrinks them for fast loading
                                    · publishes them
                                          │
                                          ▼
                          happyfamilycleaningsolutions.com/portfolio
                          (each job as a labelled Before group and After
                           group, filterable by service)
```

**You approve everything.** Nothing goes public on its own — your star on a closeout submission
is the only thing that publishes a job. See *Step 6 — the daily habit*.

**Photos are never paired one-to-one.** Each job shows a Before group and an After group, and the
card shows one from each side by side. Crews do not shoot the same rooms in the same order, and
guessing produces a bathroom labelled "before" next to a living room labelled "after" — which
reads as carelessness to exactly the customer we are trying to win. Grouping is always honest and
needs no work from you.

**Cost: $0.** GitHub Pages hosts the gallery and GitHub Actions runs the schedule, both free.

---

## What you need before you start

- The Jotform login (you have it)
- A free GitHub account — https://github.com/signup — about two minutes
- 30–40 minutes for the whole setup, once

You do not need to write any code. Every step below is copy, paste, or click.

---

## Step 1 — Create the GitHub repository

1. Sign in to GitHub, click the **+** at the top right, choose **New repository**.
2. Repository name: `hfcs-portfolio`
3. Set it to **Public**. (It has to be public for GitHub Pages to serve the photos free.
   Only approved job photos ever land in it — no customer names, no addresses.)
4. Leave everything else alone and click **Create repository**.
5. On the next screen click **uploading an existing file**.
6. Drag in *everything* from the `Portfolio Automation` folder — `sync_portfolio.py`,
   `requirements.txt`, the `docs` folder, the `seed` folder, and the `.github` folder.
   Then click **Commit changes**.

> If GitHub's web uploader skips the `.github` folder (some browsers hide folders starting
> with a dot), create it by hand: **Add file → Create new file**, and for the filename type
> `.github/workflows/sync-portfolio.yml` — typing the slashes makes the folders. Then paste
> in the contents of that file.

---

## Step 2 — Turn on GitHub Pages

1. In the repo, click **Settings**, then **Pages** in the left sidebar.
2. Under *Build and deployment* → *Source*, choose **Deploy from a branch**.
3. Branch: **main**, folder: **/docs**. Click **Save**.
4. Wait about a minute, then refresh. GitHub shows your live address:

   `https://YOURUSERNAME.github.io/hfcs-portfolio/`

   Open it. You will see the gallery frame with a "Nothing here yet" message, or the sample
   photos if the sample feed is still in place. Either way, if the page loads, Step 2 worked.
   **Write that address down — you need it in Step 7.**

---

## Step 3 — Get a Jotform API key and store it

1. Go to https://www.jotform.com/myaccount/api
2. Click **Create New Key**. Name it `HFCS Portfolio`. Set permission to **Read Only**.
   Read-only matters — this key can never change or delete a submission.
3. Copy the key.
4. Back in GitHub: **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `JOTFORM_API_KEY`
   - Secret: paste the key
   - **Add secret**

The key is now encrypted. Nobody, including anyone looking at the public repo, can read it.

> Never paste this key into a chat, an email, or a document. If it ever leaks, delete it on
> that Jotform page and make a new one.

---

## Step 4 — Brief the crew on the photo standards

Photos are part of the inspection on every job — nobody asks the customer for permission and
nobody offers a discount for them. The control is at the camera instead: contractors are trained
on what may and may not go in the frame.

Two documents cover this, both in `Hiring & Onboarding System/Onboarding/`:

- **`06 - Job Photo Standards & Word Tracks.pdf`** — the full policy. Goes in the onboarding
  packet, required reading for every contractor.
- **`Job Photo Pocket Card (print for the van).pdf`** — the one-page version. Print it, put one
  in each vehicle, and have the crew screenshot it to their phones.

The three things that matter most for this gallery:

1. **Same spot, same angle, same order, before and after.** The gallery pairs photo 1 with photo
   1. Same angle is the whole trick.
2. **Same spelling of the customer name on both forms.** "Dave Jones" on the walkthrough and
   "David Jones" on the closeout means the job never pairs and never publishes.
3. **`NO PHOTOS` at the top of the closeout Notes** if a customer objects. Never star a job with
   that note — the inspection photos stay internal.

---

## Step 5 — First run

1. In the repo, click the **Actions** tab.
2. If GitHub asks you to enable workflows, click the green **I understand my workflows,
   go ahead and enable them**.
3. Click **Sync portfolio photos** in the left list, then **Run workflow → Run workflow**.
4. Wait a minute, click into the run, and open the **Pull approved job photos** step.

It prints exactly what it did, in plain English:

```
Matched 3 before/after jobs. 1 closeouts had no walkthrough.
Approved for the website: 1
  + Jones — Junk Removal — 2026-08-28
Held back: 2
  - Rivera 2026-08-22: closeout not starred in Jotform
  - Chen 2026-08-19: no photos attached
```

That "Held back" list is your to-do list. Every line tells you what is missing.

---

## Step 6 — The daily habit (this is the whole approval step)

**Approving a closeout is what publishes a job.** There are two ways to do it and either one
works — use whichever you find faster.

1. Open the **HFCS Job Closeout Checklist** in Jotform → **Submissions**.
2. Look at the After Pictures on a new submission.
3. If it makes us look good, approve it:
   - **Click the star / flag icon** on the submission, **or**
   - **Type `#portfolio` anywhere in that submission's Notes / Comments.**
4. Within 3 hours it is on the website.

**Use `#portfolio` if the star doesn't seem to take.** The star depends on Jotform passing its
flag through to the API, which it does not always do. The keyword is plain text the API always
returns, so it is the one that is guaranteed to work. To undo it, delete the keyword.

**`NO PHOTOS` in the Notes beats everything.** If a customer asked us not to use their photos,
that job never publishes, even if someone stars it by mistake. The inspection photos stay in
Jotform as the damage record and go nowhere else.

What to star, in order of how much they sell:

1. **Junk removal cleanouts** — a packed garage and an empty one is the single most
   persuasive image this business can put on the internet. Star every decent one.
2. **Move-out and post-construction cleans** — dramatic, and they attract the property
   managers and HOAs you are already courting.
3. **Pet waste common areas** — these are what an HOA board wants to see before signing.
4. Routine recurring cleans — star occasionally, for variety. A wall of spotless
   kitchens all looks the same.

What never to approve: anything with a face, a mailbox number, a piece of mail, a prescription
bottle, a family photo, a car tag, or a monitor with something readable on it. When in doubt,
don't. The gallery already strips GPS coordinates out of every photo, but it cannot see what is
in the frame — you can.

### Checking a run without opening GitHub

Every run publishes a small status file at
**https://hfcs2026.github.io/hfcs-portfolio/status.json**

It says how many walkthroughs and closeouts it read, how many paired up, and for each job
whether it published and why not. It carries **no customer names and no photo links** — only
dates, service types and reason codes — so it is safe sitting on a public address. Open it in a
browser any time you want to know what the last run did.

---

## Step 7 — Put it on the website

Your portfolio page becomes one embedded gallery, replacing the hand-built sections.

1. Sign in at tailorbrands.com → **My Websites → Edit Site**.
2. Open the **Portfolio** page.
3. **Before you delete anything**, do Step 8 first so the existing photos survive the swap.
4. Add a widget: look for **HTML**, **Embed**, or **Custom Code** in the widget list.
   Drag it onto the page where the galleries were, and make it **full width**.
5. Open `embed-for-tailorbrands.html`, copy the whole thing, and paste it into the widget.
6. **Change `YOURUSERNAME` to your GitHub username** — it appears once, in the `src=` line.
   Everything else stays as-is.
7. Do **not** set a fixed height on the widget. The gallery reports its own height and the
   snippet resizes the frame to match.
8. Delete the old gallery sections, keep your page heading and the Book Now / Contact
   buttons, and **Publish**.
9. Check it on your phone. The grid drops to one column and the slider works by dragging.

If your Tailor Brands plan has no HTML widget, tell me — the fallback is to link a
"See our recent work" button straight to the GitHub Pages address, which works on every
plan and takes two minutes.

---

## Step 8 — Bring your existing portfolio photos across

Because the page is being replaced, the photos already on it need to come along.

1. Save the current portfolio images to your computer (right-click → Save image, or pull
   them from the Google Drive job folders — the Drive originals are better quality).
2. Put them in the `seed/images` folder.
3. Open `seed/seed.json` and list them. It already contains two worked examples matching
   your current page — the apartment cleanout before/after pairs and the 2 bed 2 bath deep
   clean. Edit the filenames to match yours, delete the examples you don't need.
   - `pairs` is for before/after two-shot sets.
   - `extras` is for standalone photos with no before shot.
4. Upload the changed `seed` folder to GitHub (**Add file → Upload files**). Saving it
   kicks off a sync automatically, and the photos appear in the gallery mixed in by date.

These seeded photos are permanent — they are not affected by starring.

---

## Step 9 — Confirm it is running on its own

Come back in a day and check the **Actions** tab. You should see runs every 3 hours, most
of them ending in "No new approved photos. Nothing to publish." That is a healthy schedule.

GitHub pauses scheduled jobs on repositories that sit completely untouched for 60 days, and
emails you when it does. If that email ever arrives, click the link and re-enable — or just
press **Run workflow** by hand, which also resets the clock.

---

## Reference — what the settings do

Set these under **Settings → Secrets and variables → Actions → Variables** only if you want
to change the defaults.

| Name | Default | What it does |
|---|---|---|
| `PUBLISH_GATE` | `flag` | `flag` = star the closeout **or** put the approve keyword in its Notes. `field` = use a "Publish to website" question on the closeout form instead. `none` = publish every matched job (not recommended). |
| `APPROVE_KEYWORD` | `#portfolio` | The word you type into the closeout Notes to approve a job. |
| `BLOCK_KEYWORD` | `no photos` | Text in the Notes that blocks a job outright, whatever else says. Leave this alone. |
| `REQUIRE_CONSENT` | `false` | Off, because photos are part of the standard inspection rather than a per-job ask. Only set it to `true` if a photo-release question is ever added back to the walkthrough form. |
| `MAX_PAIR_DAYS` | `45` | How many days apart a walkthrough and its closeout can be and still count as the same job. Raise it for long cleanout projects. |
| `PRE_FORM_ID` | `261183496401052` | Pre-Job Walkthrough form |
| `POST_FORM_ID` | `261183572696063` | Job Closeout Checklist form |

---

## Troubleshooting

**A job I starred is not showing up.**
Open **https://hfcs2026.github.io/hfcs-portfolio/status.json** — the `reason` line for that job
says exactly what stopped it. Two common ones:

- *"not approved"* with `"starred": false` — Jotform did not pass the star through to the API.
  Type `#portfolio` in that submission's Notes instead; that always works.
- The job is missing from the list entirely — the walkthrough and closeout never paired, almost
  always a customer-name spelling difference between the two forms. Case doesn't matter
  ("Diane Miles" and "Diane miles" pair fine), but "Dave" and "David" don't. Fix the spelling on
  either submission in Jotform and it pairs on the next run.

**"unmatched closeout" in the log.**
A closeout with no walkthrough at all. The crew skipped the pre-job form. Worth raising at
a check-in — that also means no before photo and no walkthrough record if there is ever a
damage claim.

**The gallery frame is empty on the website but works at the GitHub Pages address.**
The `YOURUSERNAME` in the embed snippet was not replaced, or the widget got a fixed height
of 0. Recheck Step 7 items 6 and 7.

**Photos look sideways.**
They will not — the sync reads the phone's rotation tag and bakes the rotation in before
saving. If one still does, the phone wrote a broken tag; re-shoot or rotate it and re-upload
to the Jotform submission.

**The API key stopped working.**
Someone deleted it in Jotform. Make a new read-only key and update the `JOTFORM_API_KEY`
secret.

---

## What is in this folder

| File | What it is |
|---|---|
| `sync_portfolio.py` | The engine. Pulls Jotform, pairs, filters, strips GPS, resizes, writes the feed. |
| `.github/workflows/sync-portfolio.yml` | The every-3-hours schedule plus the manual Run button. |
| `docs/index.html` | The gallery itself — sliders, service filters, lightbox. |
| `docs/gallery.json` | Generated. The list of published jobs. Don't hand-edit. |
| `docs/status.json` | Generated. What the last run did and why, with no customer names in it. |
| `docs/images/` | Generated. Web-sized, GPS-stripped copies of the photos. |
| `seed/` | Your pre-automation photos and the file that describes them. |
| `embed-for-tailorbrands.html` | The snippet that goes on the portfolio page. |
| `requirements.txt` | Tells the cloud job which two libraries to install. |

### Running it on your own Mac (optional)

```bash
cd "Portfolio Automation"
pip3 install -r requirements.txt
export JOTFORM_API_KEY="your-key"
python3 sync_portfolio.py --dry-run     # shows the approved / held-back list, changes nothing
python3 sync_portfolio.py --sample      # builds a demo gallery so you can see the layout
```

Then open `docs/index.html` in a browser.
