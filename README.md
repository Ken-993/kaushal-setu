# Kaushal Setu

**Bridging skills to opportunities.** A data-science career map built on the SAS CU Hackathon datasets: how job roles relate, what companies reward, what the market pays for, and where a person's skills fit.

This README takes you from a fresh Fedora computer to a live website on the internet. It assumes you have never deployed anything. Follow the parts in order and copy the commands exactly.

**Your setup this guide is written for:** Fedora (Hyprland) · VS Code installed as a Flatpak · Podman for containers · GitHub for code · Render for hosting.

---

## Contents

- [Project at a glance](#project-at-a-glance)
- [How the pieces fit (read once)](#how-the-pieces-fit-read-once)
- [Part 1: Set up your Fedora computer](#part-1-set-up-your-fedora-computer-one-time)
- [Part 2: Make VS Code's terminal work (Flatpak fix)](#part-2-make-vs-codes-terminal-work-flatpak-fix)
- [Part 3: Put the project on your computer](#part-3-put-the-project-on-your-computer)
- [Part 4: Run the website on your computer](#part-4-run-the-website-on-your-computer)
- [Part 5: Put the code on GitHub](#part-5-put-the-code-on-github)
- [Part 6: Deploy on Render](#part-6-deploy-on-render)
- [Part 7: Change something and redeploy](#part-7-change-something-and-redeploy)
- [Part 8: Troubleshooting](#part-8-troubleshooting)
- [Part 9: How the project works (reference)](#part-9-how-the-project-works-reference)
- [Tech stack](#tech-stack)
- [Project status](#project-status)
- [Glossary](#glossary)

---

## Project at a glance

| | |
|---|---|
| **What it is** | A website that maps 19 data-science job profiles, measures how far apart they are, explains what drives pay and success, and matches a person's skills or resume to roles |
| **Data** | 4 SAS CU Hackathon files: Analytics Jobs (15,841 postings), DataScience Jobs (1,602 rows), JDS Skill Traits (139 juniors), SDS Personality Traits (161 seniors) |
| **Who it serves** | **Candidates**: role fit, skill gaps, salary band. **Companies**: what drives hikes and success internally, what the market pays for, and where the two disagree |
| **Website** | **Check my fit** (upload a resume or pick skills → a verdict for every role: Ready to apply / Almost there / Stretch goal, with missing skills and pay), **Explore roles** (role cards + a "similar roles" orbit), **Compare roles**, **Insights** (plain-language findings), **For analysts** (statistics, models, playground, role distances, data cleaning) |
| **Runs as** | One Docker container: Python trains the models during the build, then FastAPI serves the website and the API |
| **Hosted on** | Render, free plan |

**Unique selling points**

1. **Bridges company data and market data.** Job-posting skills are mapped onto the company's five competencies, so internal rewards can be compared with market pay.
2. **Measures how similar roles really are.** Four distance views (skills, competency mix, salary distribution, experience & pay) plus a blend, shown as a map, heatmap and family tree, with significance tests for every pair of roles.
3. **Personal.** Upload a resume (or tick your skills) and get a clear verdict for each of 19 roles, the skills to learn next, and a pay estimate in ₹ LPA.
4. **Its numbers can be checked.** Every cleaning decision is logged; tests are chosen after checking assumptions; effect sizes, multiple-test corrections and baseline comparisons are reported.
5. **Explainable and private.** Predictions show why; findings are written from the results; uploaded resumes are processed in memory and never stored.

**Key results**

- **Junior salary hike:** driven by dashboards & storytelling (d = 1.32), maths & stats (1.22), coding (0.99) and AI & ML (0.88); big data shows no reliable effect. Logistic regression, cross-validated AUC 0.90.
- **Senior success:** conscientiousness (d = 1.85) and openness (1.80) matter most; neuroticism alone does not. Random forest, AUC 0.996.
- **Market pay:** experience is the main driver (Spearman ρ = 0.69 with salary band). AI & ML (+0.80 bands), big data (+0.76) and maths & stats (+0.74) carry the largest premiums.
- **Company vs market:** the company rewards dashboards most, but the market pays nothing extra for them (−0.16 bands). A direction to investigate (only 5 competencies to compare).
- **Salary-band model:** 87% of test postings within one band (baseline 62%).
- **Roles:** ML / AI Engineer and Data Scientist are the most alike (skill distance 0.15); Data Engineer and Business Analyst are the furthest apart among data roles (0.93).

---

## How the pieces fit (read once)

```
 YOUR COMPUTER (Fedora)                      GITHUB                         RENDER
 ─────────────────────────                   ──────────────                 ─────────────────────────────
 VS Code: you edit files                     Stores your code               Watches your GitHub repo.
      │                                      (private repo)                 On every push it:
      │  ./run-local.sh                           ▲                           1. builds the Dockerfile
      ▼                                           │  git push                 2. trains the models
 Podman builds the container  ──────────────────┘                            3. runs the 17 tests
 and runs it at                                                               4. starts the website at
 http://localhost:8000                                                           https://<name>.onrender.com
```

Four words you will see a lot:

| Word | What it means here |
|---|---|
| **Container** | A sealed box with Python, all libraries, the data, the trained models and the website inside. It runs the same on your laptop and on Render, so "it works on my machine" problems disappear. |
| **Dockerfile** | The recipe for building that box. It's in the project folder. |
| **Podman** | The program on Fedora that builds and runs containers. It understands Dockerfiles and accepts the same commands as Docker. |
| **Render** | A hosting company. It reads your Dockerfile from GitHub, builds the box on its servers, and puts it on the internet. |

You do **not** need to install Python on Fedora. Python lives inside the container.

---

## Part 1: Set up your Fedora computer (one time)

### 1.1 Open a terminal

In Hyprland, open your terminal app (often `Super + Enter`, or `Super + Q` in the default config, depending on your keybinds). Any terminal works: kitty, foot, alacritty.

### 1.2 Install the tools

Copy this whole line, paste it into the terminal (`Ctrl+Shift+V`) and press Enter. Type your password when asked; nothing appears while you type, that's normal.

```bash
sudo dnf install -y git gh podman unzip
```

| Tool | Why you need it |
|---|---|
| `git` | Tracks changes to your code and sends them to GitHub |
| `gh` | GitHub's command-line tool; handles logging in to GitHub without passwords or SSH keys |
| `podman` | Builds and runs the container |
| `unzip` | Unpacks the project zip |

### 1.3 Check everything installed

```bash
git --version
gh --version
podman --version
```

Each should print a version number. If one says `command not found`, run the install line again.

### 1.4 Test that Podman can download and run containers

```bash
podman run --rm docker.io/library/hello-world
```

You should see `Hello from Docker!` and a short explanation. (Podman runs Docker's test image; that's expected.) If you get an error instead, see [Part 8](#part-8-troubleshooting).

### 1.5 Tell Git who you are

Use the same email as your GitHub account (create one at <https://github.com/signup> if you don't have one):

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git config --global init.defaultBranch main
```

---

## Part 2: Make VS Code's terminal work (Flatpak fix)

**The problem:** VS Code from Flatpak runs inside a sandbox. Its built-in terminal can't see programs installed on Fedora, so `podman`, `git` and `gh` would say "command not found" there.

**The fix:** make VS Code's terminal open a shell on the real system using `flatpak-spawn --host` (with `script`, which gives that shell a proper terminal so `Ctrl+C` works). The project already contains this setting in `.vscode/settings.json`, so it switches on automatically when you open the folder.

### 2.1 Allow VS Code to use flatpak-spawn

Run this once in your normal (Hyprland) terminal. It's harmless if the permission is already there:

```bash
flatpak override --user --talk-name=org.freedesktop.Flatpak com.visualstudio.code
```

(If VS Code is open, close it and open it again afterwards.)

### 2.2 Check it after opening the project

You'll open the project in [Part 3](#part-3-put-the-project-on-your-computer). When you do:

1. VS Code asks **"Do you trust the authors of the files in this folder?"** Click **Yes, I trust the authors**. (Untrusted folders can't change the terminal.)
2. Open the terminal: **View → Terminal** or `` Ctrl+` ``.
3. Type:
   ```bash
   which podman git gh
   ```
   You should see three paths starting with `/usr/bin/`. The terminal tab is named **Fedora (host)**.

### 2.3 If it still says "command not found"

Set it for all your projects instead:

1. Press `Ctrl+Shift+P`, type **Preferences: Open User Settings (JSON)**, press Enter.
2. Inside the outer `{ }`, add (put a comma after the previous line if needed):
   ```json
   "terminal.integrated.profiles.linux": {
     "Fedora (host)": {
       "path": "/usr/bin/flatpak-spawn",
       "args": ["--host", "--env=TERM=xterm-256color", "script", "-qc", "bash", "/dev/null"]
     }
   },
   "terminal.integrated.defaultProfile.linux": "Fedora (host)"
   ```
3. Save, close the terminal panel (trash-can icon) and open a new one.

**Still stuck?** You can always run every command in this guide from your normal Hyprland terminal instead. Just `cd` into the project folder first.

**About Python warnings:** the Python extension inside Flatpak VS Code may say it can't find an interpreter. Ignore it. You never run Python directly; the container does.

---

## Part 3: Put the project on your computer

### 3.1 Unzip it into a Projects folder

Download `kaushal-setu.zip` from the chat into `~/Downloads`, then:

```bash
mkdir -p ~/Projects
cd ~/Projects
unzip ~/Downloads/kaushal-setu.zip
cd kaushal-setu
ls
```

`ls` should list `Dockerfile`, `render.yaml`, `run-local.sh`, `backend`, `frontend`, `pipeline`, `data` and more.

### 3.2 Open it in VS Code

```bash
flatpak run com.visualstudio.code ~/Projects/kaushal-setu
```

(Or open VS Code and use **File → Open Folder** → `Projects/kaushal-setu`.) Then do the check in [2.2](#22-check-it-after-opening-the-project).

VS Code may suggest a few extensions (Docker, Python, YAML). Installing them is optional; they only add colours and hints.

---

## Part 4: Run the website on your computer

In the VS Code terminal (inside the project folder):

```bash
./run-local.sh
```

What happens:

1. **First time only: about 3–5 minutes.** Podman downloads the Python base image, installs the libraries, trains the models (about a minute) and runs the 17 tests. You'll see `17 passed`.
2. The site starts **in the background** and the script prints `Kaushal Setu is running: http://localhost:8000`.
3. Open **<http://localhost:8000>** in your browser.
4. The terminal then shows live logs. `Ctrl+C` only hides the logs; **the site keeps running**, even if you close VS Code.

Next time it takes seconds, because Podman reuses everything that didn't change.

**All the commands you need:**

| You want to… | Command |
|---|---|
| Build and start (or restart after a change) | `./run-local.sh` |
| Stop the site | `./run-local.sh stop` |
| Is it running? | `./run-local.sh status` |
| See the logs again | `./run-local.sh logs` (Ctrl+C to hide) |
| Open the interactive API docs | <http://localhost:8000/docs> |

> If you see `Permission denied`, run `chmod +x run-local.sh` once (the file lost its "executable" flag while unzipping).

**What the script does, if you ever type it yourself** (note the `.` at the end of the build command; it means "this folder"):

```bash
podman build -t kaushal-setu .                              # build the image
podman rm -f kaushal-setu                                   # remove an old copy, if any
podman run -d --name kaushal-setu -p 8000:10000 kaushal-setu   # start in the background
podman logs -f kaushal-setu                                 # watch the logs
podman stop kaushal-setu                                    # stop
```

Free disk space from old builds now and then with `podman system prune` (answer `y`).

---

## Part 5: Put the code on GitHub

Render deploys from GitHub, so the code has to be there first.

### 5.1 Log in to GitHub from the terminal (one time)

```bash
gh auth login
```

Answer the questions with the arrow keys and Enter:

| Question | Choose |
|---|---|
| Where do you use GitHub? | **GitHub.com** |
| Preferred protocol for Git operations? | **HTTPS** |
| Authenticate Git with your GitHub credentials? | **Yes** |
| How would you like to authenticate? | **Login with a web browser** |

It shows an 8-character code and opens your browser. Paste the code, click **Authorize**. If no browser opens (common on Hyprland when no default browser is set), open <https://github.com/login/device> yourself and type the code.

Check: `gh auth status` should say **Logged in to github.com**.

### 5.2 Create the repository and upload the code

From the project folder:

```bash
git init
git add .
git commit -m "Kaushal Setu: first version"
gh repo create kaushal-setu --private --source=. --push
```

| Command | What it does |
|---|---|
| `git init` | Starts tracking this folder with Git |
| `git add .` | Selects every file (except those listed in `.gitignore`) |
| `git commit -m "…"` | Saves a snapshot with a message |
| `gh repo create … --push` | Creates the repo on GitHub and uploads the snapshot |

**Why private?** The hackathon brief marks its slides "Company Confidential", and the raw data files are in the repo. Render can deploy private repos. The website itself will still be public: anyone with the link can open it.

Check: open <https://github.com/> → your profile → **kaushal-setu**. You should see the files.

---

## Part 6: Deploy on Render

### 6.1 Create a Render account

1. Go to <https://dashboard.render.com/register>.
2. Choose **Sign up with GitHub** (this links the two accounts).
3. Render may ask for a workspace name; anything is fine.

### 6.2 Give Render access to your repository

When Render shows the list of repositories and **kaushal-setu** isn't there, click the **Configure GitHub** (or **Configure account**) link under the list. On GitHub's page, under **Repository access**, pick **Only select repositories** → **kaushal-setu** → **Save**.

### 6.3 Create the service: Blueprint (recommended, fewest clicks)

The project contains `render.yaml`, which already says: Docker, free plan, Singapore region (closest to India), health check at `/api/health`, re-deploy on every push.

1. In the Render dashboard click **New +** → **Blueprint**.
2. Select the **kaushal-setu** repository.
3. Give the Blueprint a name (e.g. `kaushal-setu`) and click **Deploy Blueprint** / **Apply**.

### Alternative to 6.3: create the service by hand

If you prefer, or the Blueprint option gives you trouble:

1. **New +** → **Web Service** → select **kaushal-setu**.
2. **Language / Runtime:** Docker (Render detects the `Dockerfile`).
3. **Region:** Singapore. **Branch:** main.
4. **Instance Type:** **Free**.
5. Open **Advanced** → **Health Check Path:** `/api/health`.
6. Click **Deploy Web Service**.

> If Render asks for payment details at any point, that's its account verification. With the **Free** instance type selected, the service costs $0/month.

### 6.4 Watch the first deploy

Click the service → **Logs**. You'll see roughly the same steps as on your computer (exact wording varies):

```
Step: pip install -r requirements.txt     (1–2 min)
== Phase 1: cleaning == … All phases finished in …s     (1–2 min)
17 passed
Kaushal Setu: artifacts loaded
Uvicorn running on http://0.0.0.0:10000
Your service is live
```

The first deploy takes about **5–10 minutes**. Your site's address is at the top of the service page, like `https://kaushal-setu-xxxx.onrender.com`. Open it, and also try `/docs` on the same address.

### 6.5 What to expect from the free plan

| Behaviour | What it means for you |
|---|---|
| **Sleeps after 15 minutes without visitors** | The next visitor waits about 1 minute while it wakes up (plus about 20 s for the app to load). Before a demo or presentation, open the site a few minutes early. |
| **512 MB RAM, 0.1 CPU** | Plenty: the app uses about 115 MB (measured with the same limits). |
| **750 free hours/month** | Enough to run one service all month. |
| **500 build minutes/month** | Each deploy uses about 5–10 minutes, so roughly 50+ deploys a month. Don't push every tiny edit; batch them. |
| **5 GB bandwidth/month** | Responses are compressed and the chart library comes from a public CDN, so a page view costs very little. |

---

## Part 7: Change something and redeploy

Your everyday loop:

```bash
# 1. edit files in VS Code, then test on your computer
./run-local.sh                       # rebuilds + restarts; open http://localhost:8000 and check
./run-local.sh stop                  # when you're done

# 2. save a snapshot and send it to GitHub
git add .
git commit -m "Describe what you changed"
git push
```

Render notices the push and re-deploys automatically (watch **Logs** on Render). If the tests fail during the build, Render keeps the old version online, so a broken change never reaches the live site.

**Use the terminal for `git push`, not VS Code's Source Control buttons.** The Flatpak sandbox's Git can't use the GitHub login you set up with `gh`, so the buttons may fail to push.

| You changed… | Rebuild time (local) |
|---|---|
| `frontend/` or `backend/` files | Seconds |
| `pipeline/`, `config.py` or `data/raw/` | About 1–2 minutes (models retrain) |
| `requirements.txt` | 3–5 minutes (libraries reinstall) |

**Where to change common things:**

| To change… | Edit |
|---|---|
| Page text, tabs, layout | `frontend/index.html` |
| Colours, fonts, spacing | Tokens at the top of `frontend/css/styles.css` |
| Charts on a tab | `frontend/js/pages/<tab>.js` |
| Which job titles map to which role | `ROLE_RULES` in `pipeline/profiles.py` |
| Which skills count as which competency | `TAXONOMY` in `config.py` |
| Resume skill aliases | `ALIASES` in `backend/resume.py` |
| Render settings (region, plan) | `render.yaml` (region can't change after creation) |

---

## Part 8: Troubleshooting

### On your computer

| Symptom | Fix |
|---|---|
| `podman: command not found` in VS Code, but works in your normal terminal | The Flatpak terminal fix isn't active: see [Part 2](#part-2-make-vs-codes-terminal-work-flatpak-fix) (trust the folder, run the `flatpak override` command, reopen VS Code) |
| `flatpak-spawn: … Portal call failed` / terminal closes immediately | Run `flatpak override --user --talk-name=org.freedesktop.Flatpak com.visualstudio.code`, then restart VS Code |
| `./run-local.sh: Permission denied` | `chmod +x run-local.sh` once, or use `bash run-local.sh` |
| `Error: no context directory and no Containerfile specified` | You typed `podman build -t kaushal-setu` without the final ` .` (dot). Easier: just use `./run-local.sh` |
| Closed VS Code and the site seems gone, or `localhost:8000` doesn't load | Run `./run-local.sh status`. If it says not running, run `./run-local.sh` again. The script always removes old copies first |
| `bash: no job control in this shell` / `cannot set terminal process group` in VS Code | The terminal profile is the old one. Use the `script -qc bash /dev/null` version from [Part 2](#part-2-make-vs-codes-terminal-work-flatpak-fix), then open a new terminal (trash-can icon, then `+`) |
| `the container name "kaushal-setu" is already in use` | `./run-local.sh stop`, then `./run-local.sh` |
| `Error: … address already in use` / port 8000 busy | Something else uses port 8000. Run `./run-local.sh stop`; if it still fails, edit `run-local.sh`: change `8000:10000` to `8080:10000` and `localhost:8000` to `localhost:8080` |
| `Error: … short-name resolution` / asks which registry | Shouldn't happen (the Dockerfile uses the full image name). If it does, choose `docker.io` |
| Build fails at `pip install` with a network error | Check your internet and retry. On university Wi-Fi with a proxy, try another network |
| Build fails at `RUN python -m pytest` | A change broke something: scroll up to the first `FAILED` line; it names the test and the reason |
| `podman run --rm docker.io/library/hello-world` fails with "permission" or "newuidmap" | Run `podman system migrate` once, then retry |
| `toomanyrequests: You have reached your pull rate limit` | Docker Hub limits anonymous downloads. Wait an hour, or run `podman login docker.io` with a free Docker Hub account |
| Website shows a red box "Cannot reach the server" | The site isn't running: `./run-local.sh status`, then `./run-local.sh` |
| Charts look squashed or old after a change | Hard refresh: `Ctrl+Shift+R` |

### GitHub

| Symptom | Fix |
|---|---|
| `gh: command not found` | `sudo dnf install -y gh` |
| `git push` asks for a username/password | Run `gh auth setup-git`, then push again |
| `GraphQL: Name already exists on this account` | You already have a repo called kaushal-setu. Use another name: `gh repo create kaushal-setu-2 --private --source=. --push` (or delete the old one on github.com) |
| `fatal: not a git repository` | You're not in the project folder: `cd ~/Projects/kaushal-setu` |

### Render

| Symptom | Fix |
|---|---|
| Render can't see the repository | GitHub → Settings → Applications → Render → Configure → add **kaushal-setu** |
| Build log ends with `FAILED` tests | Same as locally: the first `FAILED` line says why. Fix, test with `./run-local.sh`, push again |
| `No open ports detected` / deploy times out | Don't change the `CMD` line in the Dockerfile; it binds to Render's `$PORT` on `0.0.0.0` |
| Site shows "Service unavailable" / takes a minute to load | It was asleep (free plan). Wait about a minute and reload |
| Build disabled for the rest of the month | You've used the 500 free build minutes. The live site keeps running; deploys resume next month (or add billing) |
| Site works locally but not on Render | Compare the Render **Logs** with your terminal output; the first error line is the clue |

---

## Part 9: How the project works (reference)

### 9.1 Project structure

```
kaushal-setu/
├── README.md               ← this guide
├── Dockerfile              ← recipe for the container (used locally and by Render)
├── .dockerignore           ← files the container doesn't need
├── render.yaml             ← Render Blueprint: Docker, free plan, Singapore, health check
├── run-local.sh            ← build + run locally in the background: start | stop | logs | status
├── requirements.txt        ← exact Python library versions
├── .gitignore              ← generated folders Git should ignore
├── .vscode/
│   ├── settings.json       ← Flatpak terminal fix ("Fedora (host)" profile)
│   └── extensions.json     ← suggested VS Code extensions
│
├── config.py               ← paths, feature names, salary bands, skill taxonomy
├── run_all.py              ← runs pipeline phases 1 → 5 (called by the Dockerfile)
├── pytest.ini              ← test settings
│
├── data/raw/               ← the 4 original hackathon files (never edited)
├── pipeline/               ← analysis + machine learning
│   ├── cleaning.py         ← PHASE 1: load, audit, clean; logs every decision
│   ├── stats_tests.py      ← PHASE 2: hypothesis tests, effect sizes, alignment
│   ├── ordinal.py          ← helper: ordinal classifier for salary bands
│   ├── models.py           ← PHASE 3: train, compare, save the 3 models
│   ├── profiles.py         ← PHASE 4: 19 job profiles + distances between them
│   └── insights.py         ← PHASE 5: plain-language findings
├── backend/                ← web server
│   ├── main.py             ← URLs (endpoints), start-up loading, compression, serves frontend/
│   ├── services.py         ← all logic: predictions, comparisons, role matching, resume analysis
│   ├── resume.py           ← reads PDF/Word/text resumes; finds skills + experience
│   └── schemas.py          ← validates incoming data (e.g. scores must be 1–5)
├── frontend/               ← website (plain HTML/CSS/JS, no build step)
│   ├── index.html          ← page skeleton: header, 8 tabs, chart boxes
│   ├── css/styles.css      ← colours (light + dark), fonts, layout, mobile
│   ├── vendor/plotly.min.js← chart library fallback (main copy comes from a CDN)
│   └── js/
│       ├── app.js          ← tabs, theme toggle, error messages
│       ├── api.js          ← the only file that talks to the backend
│       ├── charts.js       ← shared chart helpers + colour tokens
│       └── pages/          ← fit (home), explore (orbit), compare, insights; analysts: stats, models, tryit, atlas, info
├── samples/                ← a fictional resume (.txt/.docx/.pdf) to test the upload
└── tests/test_api.py       ← 17 automated checks (run in every build)
```

Generated inside the container during the build (not in Git): `data/clean/` (cleaned data + cleaning report) and `artifacts/` (results JSON + the three trained `.joblib` models).

### 9.2 What happens inside the Dockerfile

| Step | What | Re-runs when… |
|---|---|---|
| 1 | Start from the official `python:3.12-slim` image | Never (cached) |
| 2 | `pip install -r requirements.txt` | `requirements.txt` changes |
| 3 | Copy data + pipeline, run `python run_all.py` (phases 1–5, about 1 min) | Data or pipeline code changes |
| 4 | Copy backend, frontend, tests, samples | Those files change |
| 5 | `pytest`: 17 tests; a failure stops the build | Any of the above changes |
| 6 | Start `uvicorn` on `$PORT` (Render sets 10000) | Every container start |

Training inside the build guarantees the models are always made with exactly the library versions that later load them. That avoids a whole class of "model file won't load" errors.

### 9.3 The five analysis phases

**Phase 1: cleaning.** Snake-case column names; parse `"7.8L"` salaries and `"6-10 yrs"` experience; map salary text to ordered bands 0–5; remove the `...` truncation artifacts; merge city aliases (Bangalore → Bengaluru); flag (not delete) data-entry spam posts; group 4,474 copy-pasted descriptions so they never land in both training and test data; map free-text skills to the five company competencies. The DataScience Jobs file is descriptive only: its average salary is about (min + max) / 2, so modelling it would just learn that formula. Every decision is shown on the **Data & cleaning** tab.

**Phase 2: statistics.** For each feature, Shapiro–Wilk and Levene tests decide between Welch's t-test and Mann–Whitney U; Cohen's d with 95% intervals gives the size; Holm correction handles multiple tests. Market: Spearman/Kendall for experience vs band, Mann–Whitney for each competency's premium (overall and within experience levels), ordinal regression adjusting big data for experience, chi-square + Cramér's V for designation vs band. Alignment compares the company's and the market's competency rankings.

**Phase 3: models.**

| Model | Predicts | Validation | Result |
|---|---|---|---|
| JDS | P(high salary hike) from 5 skill scores | 5-fold CV × 10 repeats | Logistic regression, AUC 0.90 |
| SDS | P(high success) from 5 personality scores | 5-fold CV × 10 repeats | Random forest, AUC 0.996 |
| Band | Salary band 0–5 from experience, skills, title, city | Grouped train/test split | Ordinal logistic, 87% within one band |

Every candidate is compared with a baseline that always guesses the most common answer. Logistic regression is kept unless another model beats its AUC by more than 0.02, because it can explain each prediction.

**Phase 4: job profiles.** Ordered keyword rules map designations to 19 roles (10 data roles, 9 adjacent roles for contrast); 10,101 of 15,676 postings match. Each role gets a profile (310-skill prevalence, competency mix, experience, salary distribution, cities, example titles, advertised salary). Distances: cosine on skills, Euclidean on competencies, Jensen–Shannon on salary distributions, Euclidean on standardised experience & pay, and a blend. Each view gets a classical-MDS map, average-linkage clustering and a dendrogram. All 171 role pairs are tested (permutation test for skills, Mann–Whitney for band and experience, Holm-corrected).

**Phase 5: insights.** Fills sentence templates with numbers from phases 2–4, so the Findings tab always matches the data.

### 9.4 API endpoints

| Method | URL | Returns | Used by tab |
|---|---|---|---|
| GET | `/api/health` | `{"status": "ok"}` when models are loaded (Render's health check) | – |
| GET | `/api/overview` | Audit table, cleaning decisions, insights, role coverage | Findings, Data |
| GET | `/api/options` | Roles, skills, cities, input ranges, distance views | all |
| GET | `/api/stats` | Everything from phase 2 | Statistics |
| GET | `/api/models` | Model comparison, ROC, coefficients, confusion matrix, top terms | Models |
| GET | `/api/profiles` | One summary row per role | – |
| GET | `/api/profiles/{role}` | Full profile + 5 nearest roles in each view | Atlas |
| GET | `/api/similarity?view=skills` | Distance matrix, map coordinates, clusters, dendrogram | Atlas |
| GET | `/api/compare?a=…&b=…` | Two roles: all distances, ranks, tests, skill overlap | Compare |
| POST | `/api/predict/hike` | P(high hike) + contribution of each skill | Try it |
| POST | `/api/predict/success` | P(high success) + contribution of each trait | Try it |
| POST | `/api/predict/salary-band` | Probability of each salary band | Try it, Your resume |
| POST | `/api/match` | Data roles ranked by fit to your skill pattern + hike prediction | Try it |
| POST | `/api/resume` | Upload (.pdf/.docx/.txt, max 5 MB): skills, experience and a fit verdict for every role | Check my fit |
| POST | `/api/fit` | Same fit result from a list of skills + years (no resume) | Check my fit |
| GET | `/api/fit/sample` | Fit result for the bundled sample resume | Check my fit |
| GET | `/api/skill-picker` | Popular skills grouped into areas, for the skill picker | Check my fit |

Try any of them at `/docs` on your local or Render address.

### 9.5 How a click travels through the system

Example: dragging the **Coding** slider on *Try it*.

```
browser   tryit.js waits 180 ms, reads the 5 sliders
browser   api.js → POST /api/match  {"coding_skills": 4.4, ...}
server    main.py receives it → schemas.py checks every value is 1–5
server    services.match_roles() ranks roles; predict_hike() runs the trained model
          (loaded once at start-up from artifacts/jds_model.joblib)
server    returns JSON (compressed)
browser   tryit.js redraws the probability, contribution bars and role ranking
```

### 9.6 How the resume reader works

1. **Read in memory** (pypdf for PDF, python-docx for Word incl. tables). Never written to disk.
2. **Find skills**: about 740 skills learned from the postings, matched as whole words or phrases; longer phrases first so "machine learning" doesn't also count as "learning"; common spellings translated (scikit-learn → machine learning, PostgreSQL → sql).
3. **Find experience**: "3 years of experience" statements, else job date ranges (education lines skipped, overlaps merged), else 0 (you can edit it on the page).
4. **Rank roles**: cosine similarity between your skills and each role's skill profile.
5. **Skills worth adding**: skills in at least 8% of a role's postings that your resume doesn't mention.
6. **Salary band**: the band model with your skills, years, best-fit role and city.

Limits: keyword matching, not reading comprehension. Unusual wording can be missed and "no SAS experience" still counts SAS.

---

## Tech stack

| Layer | Technology | Used for |
|---|---|---|
| Language | **Python 3.12** (inside the container) | Pipeline, models, backend |
| Data handling | **pandas**, **NumPy**, **openpyxl** | Loading and cleaning CSV/Excel |
| Statistics | **SciPy**, **statsmodels** | Shapiro–Wilk, Levene, Welch t, Mann–Whitney U, Kruskal–Wallis, Spearman/Kendall, chi-square, Holm correction, ordinal regression |
| Machine learning | **scikit-learn** | Logistic regression, random forest, gradient boosting, repeated stratified CV, grouped split, CountVectorizer/TF-IDF, permutation importance |
| Custom model | **Frank & Hall ordinal classifier** | Salary-band prediction that respects band order |
| Similarity | SciPy + NumPy | Cosine, Euclidean, Jensen–Shannon distances; classical MDS; hierarchical clustering; permutation tests |
| Model storage | **joblib** | Saving and loading trained models |
| Backend | **FastAPI**, **Uvicorn**, **Pydantic**, **python-multipart** | 17 REST endpoints, validation, file upload, gzip compression, `/docs` |
| Resume reading | **pypdf**, **python-docx** | Text from PDF and Word files |
| Frontend | **HTML5, CSS3, vanilla JavaScript (ES modules)** | 8-tab single-page app, light/dark theme, mobile layout; no framework, no build step |
| Charts | **Plotly.js 4.1.2** (jsDelivr CDN, bundled fallback) | Maps, heatmaps, dendrograms, forest plots, ROC curves, bar and dumbbell charts |
| Testing | **pytest**, FastAPI TestClient, httpx | 17 tests, run in every build |
| Containers | **Docker** format; **Podman** locally on Fedora | Same container on laptop and server |
| Code hosting | **Git**, **GitHub** (private repo), **GitHub CLI** (`gh`) | Version control; source for Render |
| Hosting | **Render** (free web service, Docker runtime, Blueprint `render.yaml`) | Public website with auto-deploy on every push |
| Editor | **VS Code** (Flatpak) with a host-terminal profile | Editing and running commands |

**Architecture:** `GitHub repo → Render builds Dockerfile → (pip install → train models → run tests) → container runs FastAPI → serves website + API at https://<name>.onrender.com`

---

## Project status

*Last updated: 3 November 2026*

### Done

| Area | Status |
|---|---|
| Data cleaning, statistics, ML models, job-profile similarity, findings (phases 1–5) | Complete |
| Backend API (17 endpoints) and website (5 sections, navy + beige, light/dark, mobile) | Complete |
| Resume upload (PDF/DOCX/TXT) with role fit, skills to add, salary band | Complete |
| Containerised: Dockerfile with pinned libraries, training and tests in the build | Complete, built and tested |
| Tested under Render free-plan limits (512 MB, 0.1 CPU) | Starts in about 20 s; uses about 115 MB RAM; all endpoints respond |
| Render Blueprint (`render.yaml`), health check, `$PORT` binding, gzip, CDN for charts | Complete |
| Fedora + Flatpak VS Code setup (host terminal profile, Podman script) | Complete |
| Automated tests | 17/17 passing in every build |
| Live deployment on Render | **Your step:** follow Parts 5 and 6 |

### Planned next

| Feature | For | Idea |
|---|---|---|
| Evidence-weighted skill score | Candidates | Weight skills by proof: resume mention < certificate < project < GitHub code |
| Salary value of each missing skill | Candidates | Rank gaps by how much they'd raise the expected band |
| Career path through nearby roles | Candidates | Stepping-stone roles from the Atlas distances, with the skills that unlock each step |
| Proof-plan generator | Candidates | Small projects that build evidence for 2–3 missing skills at once |
| Job description → requirements | Companies | Paste a job description; get the matching role, key skills and a realistic band |
| Candidate ranking | Companies | Rank several resumes for one opening by fit |
| Team skill-gap dashboard | Companies | Team skill scores vs the market; flag promotion-ready people |

### Known limitations

- Analytics descriptions and skill lists are truncated at about 110 characters, so skill prevalences are lower bounds.
- JDS and SDS are single-company samples of about 150 people: results describe that company.
- The resume reader matches keywords; negative mentions still count.
- The skill-overlap map is an approximation (MDS stress 0.48); exact distances are in the heatmap.
- About 36% of postings don't match any of the 19 roles and are left out of the role map.
- Free hosting sleeps after 15 idle minutes; the first visit afterwards takes about a minute.

---

## Glossary

| Term | Meaning |
|---|---|
| **API / endpoint** | URLs a program calls to get data or trigger work; here everything under `/api/...` |
| **Backend / frontend** | Code on the server (Python + FastAPI) / code in the browser (HTML, CSS, JavaScript) |
| **Container / image** | An image is the built box (made by `podman build`); a container is a running copy of it (`podman run`) |
| **Dockerfile** | The step-by-step recipe for building the image |
| **Port** | A numbered door on a computer. The app listens on 10000 inside the container; your laptop maps 8000 to it |
| **localhost** | "This computer" |
| **Repository (repo)** | A project folder tracked by Git, stored on GitHub |
| **Commit / push** | Save a snapshot of your changes / upload snapshots to GitHub |
| **Deploy** | Build and start a new version on the server |
| **Blueprint** | Render's name for a `render.yaml` that describes your service |
| **Health check** | Render calls `/api/health`; if it answers OK, the new version goes live |
| **Cold start** | The wait while a sleeping free-plan service wakes up |
| **Artifact** | A file produced by the pipeline (results JSON or a trained model) |
| **AUC** | Chance the model ranks a random "high" case above a random "low" one (0.5 guessing, 1.0 perfect) |
| **Cohen's d** | Size of a difference in standard deviations (0.2 small, 0.5 medium, 0.8 large) |
| **Holm correction** | Adjusts p-values when many tests are run, so chance findings aren't reported as real |
| **Cosine distance** | Compares the *mix* of two vectors (e.g. skill profiles), ignoring their size |
| **MDS** | Draws points in 2-D so their gaps match a distance table as closely as possible |
| **Flatpak / sandbox** | Fedora's app packaging; apps run isolated from the rest of the system unless given permission |
