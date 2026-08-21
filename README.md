# fantasybot ⚽🤖

Autonomous agent for **LALIGA Fantasy**: reads the game, decides and acts
(lineup, bids, sales, buyout clauses, rival finances, trade history and multi-season player scouting).

Written in standard Python (no extra dependencies for the core agent).

```bash
python -m fantasybot login                        # official OAuth (PKCE)
python -m fantasybot agent                        # review + decision plan
python -m fantasybot agent --execute              # acts: sets lineup + bids
python -m fantasybot rivals                       # rivals financial & clause audit
python -m fantasybot history                      # speculation trading & flip ROI leaderboard
python -m fantasybot scout <player>               # multi-season scouting report (points, tiers, starter)
python -m fantasybot scout --team                 # full squad scouting audit
python -m fantasybot watch [--run|--hermes]       # live monitoring UI
```

## Live monitoring (Mission Control)

To watch **in real time** what the agent reads, decides and executes —ideal for
supervising a run or recording a demo— there's a small web UI:

```bash
python -m fantasybot watch          # open the UI and supervise (you'll see the next cycle)
python -m fantasybot watch --run    # open the UI and trigger the deterministic agent
python -m fantasybot watch --hermes # open the UI and trigger the Hermes brain (LLM)
```

Every meaningful action (review, lineup, bid, sale, buyout) writes a line to
`.state/events.jsonl`; the UI follows it over SSE and renders it as a timeline.
It's fantasybot's **native** trace: it reflects what the CLI actually did, with or
without Hermes on top. It binds to `127.0.0.1`; on a VPS, open it through a tunnel:
`ssh -L 9137:127.0.0.1:9137 <server>`.

**Last-minute bidding:** instead of bidding early (and revealing your bid), the
agent schedules its flips into a "plan" (`bid-plan`) and a cron bids right at the
close: if there's no competition, the value plus a touch; if there is, up to your
max. Deterministic and free of tokens.

**Rival tracking & Trade History:**
- `rivals [manager|rank]`: estimates rivals' liquid balances, trading flow, clause investments, and acquisition performance.
- `history [manager|rank]`: analyzes speculation profitability, completed flips with ROI % and holding duration, open portfolio holdings, and initial squad liquidations.

**Multi-Season Player Scouting:**
- `scout <player>`: analyzes multi-season points history (`lastSeasonPoints`), historical tier (🌟 *Top Star*, 🛡️ *Fixed Starter*, 🔄 *Rotation*), scoring pace evolution vs last year, FutbolFantasy starting probability (0-95%), role shifts (e.g. was starter last year -> benched now), fitness & availability, and value-for-money (€/pt) ratio.
- `scout --team`: runs a full squad audit reviewing past season output, squad stars, fitness risk, and line-by-line recommendations.

The decision commands (`agent`, `flip`, `needs`, `optimize`, `rivals`, `history`, `scout`) accept `--json` for
programmatic consumption (that's how the autonomous agent reads them).

## Autonomous agent (Hermes)

To have it run on its own on a VPS —reviewing, deciding, acting and scheduling its
own reminders— fantasybot is deployed on top of
[Hermes Agent](https://hermes-agent.nousresearch.com): an agent runtime that
provides the **brain** (an LLM — Claude — plus persistent memory, native cron and
code execution), while `fantasybot` is its **toolbox**, called via the CLI.

What Hermes adds on top of the deterministic agent:

- **It keeps its own memory.** In `hermes/MEMORY.md` the agent maintains, between
  runs, the week's plan, the decisions it made and *why*, and the outcomes it
  learns from (did the flip I bought go up? did I read the starter right?). It's
  its working notebook, not a static file.
- **It schedules itself.** Beyond a daily review, it registers its own cron jobs
  and reminders for the key moments the report already computes: market close,
  clause windows opening, and the lineup deadline before the first match.
- **It acts with judgment.** Routine moves (lineups, bids) run without asking;
  the bigger, irreversible ones (buyout clauses, large sales) are done with care
  and recorded. How autonomous it is on those is configured in `hermes/USER.md`.

The agent's assets live in `hermes/`: `SOUL.md` (persona), `USER.md` (your
preferences), `MEMORY.md` (its working memory) and `skills/fantasy-manager/SKILL.md`
(the playbook). The full setup guide is in [`deploy/README.md`](deploy/README.md).

## The agent (a human-like review)

```bash
python -m fantasybot agent [--days N]  # review + PLAN of actions (touches nothing)
python -m fantasybot agent --execute   # ACTS: sets the lineup and bids for real
python -m fantasybot tasks             # the week's pending tasks
python -m fantasybot tasks --done 3    # mark task #3 as done
python -m fantasybot due               # fire due reminders (for the cron)
```

### Autonomy

With `--execute`, the agent does ON ITS OWN (without asking): sets the best
**lineup** and places/cancels **bids** on the market for profitable flips (it may
use the whole balance). **Buyout clauses are NOT automatic** (irreversible spend):
they're left as a notice and a task for you to confirm. Without `--execute`, it
just shows the plan.

> This applies to the **deterministic agent** (`fantasybot agent`). When it's
> piloted by **Hermes** (LLM), the autonomy for buyouts and sales is configured in
> `hermes/USER.md` (default: automatic, with judgment).

## Automation (so it connects on its own)

With Windows Task Scheduler:

- **Daily review:** run `python -m fantasybot agent` at your time (e.g. 09:00). It
  detects changes, decides and schedules the day's reminders.
- **Autonomous acting:** use `python -m fantasybot agent --execute` in the daily
  task so it sets the lineup and bids on its own.
- **Firing reminders:** run `python -m fantasybot due` every minute. When a
  reminder is due (a clause opening, market close), it prints the notice.

For an always-on Linux/VPS deployment, use Hermes (see above).

## Structure

Layers in a single direction (adding a source or a strategy = one new file):

```
fantasybot/
  config.py            constants: endpoints, OAuth, paths
  auth.py              OAuth login (PKCE) + token refresh
  api.py               FantasyClient: read and write against the API
  net.py / cache.py    HTTP with backoff (429) + on-disk cache of scrapes
  matching.py          name normalization and cross-source matching
  sources/             external data: market_trends, lineups, matchday (futbolfantasy)
  strategy/            decisions: flip, lineup (optimizer), needs, sell, rivals, history, scouting
  state.py             snapshot + tasks + reminders + bid plan (.state/)
  events.py            native action trace (for the monitoring UI)
  agent.py             the "brain": review() = a human-like cycle
  execute.py           execution layer: sets the lineup and bids for real
  bidding.py           last-minute bidding (deterministic, testable)
  monitor.py + web/    live monitoring UI (SSE)
  cli.py               command-line interface
hermes/                autonomous-agent assets (SOUL, USER, MEMORY, skill)
deploy/                installer and VPS deployment guide
```

## Disclaimer

**Unofficial API:** LaLiga may change it without notice, and automating the game
may go against its terms of use. This is a personal, non-commercial project with no
intention whatsoever to act against LaLiga or to harm the game in any way. The
software is provided "as is", without warranty of any kind; you use it at your own
risk and are solely responsible for its use.

## Contributing

Issues and PRs are welcome — as long as they're thoughtful and actually make sense.
Please, no AI slop.
