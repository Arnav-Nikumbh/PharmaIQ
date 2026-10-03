# Running PharmaIQ on Windows

A complete walk through, from a fresh Windows laptop to the app open in your
browser with a working database, a research index, and passing tests.

Every command goes in **PowerShell**. To open it, press the Windows key, type
`powershell`, and press Enter.

> The project was developed and tested on macOS. Every command below is
> standard Windows tooling, but if something behaves differently on your
> machine, the Troubleshooting section at the end covers what is most likely
> to go wrong.

## What you need first

- Windows 10 or 11
- About 3 GB of free disk space (most of it is the machine learning libraries)
- An internet connection for the first run
- A free Groq API key, from [console.groq.com](https://console.groq.com)

You do **not** need to install Python. The tool in step 2 installs the correct
version for you.

---

## Step 1: Install Git

Download and run the installer from [git-scm.com/download/win](https://git-scm.com/download/win).
The default options are fine.

Close PowerShell and open it again, then check it worked:

```powershell
git --version
```

You should see something like `git version 2.47.0`.

---

## Step 2: Install uv

`uv` manages the Python version and all the libraries, so you never have to
think about virtual environments.

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Close PowerShell and open it again.** This matters: the installer adds `uv`
to your PATH and an already-open window will not see it.

```powershell
uv --version
```

---

## Step 3: Get the project

```powershell
cd $HOME
git clone https://github.com/Arnav-Nikumbh/PharmaIQ.git
cd PharmaIQ
```

Everything from here on assumes you are inside the `PharmaIQ` folder. If you
open a new PowerShell window later, run `cd $HOME\PharmaIQ` first.

---

## Step 4: Install the project

```powershell
uv sync
```

This downloads Python 3.12 and every library the project needs. It takes a few
minutes the first time because it includes PyTorch, which is large. You will
see a list of installed packages when it finishes.

Check it worked:

```powershell
uv run python --version
```

You should see `Python 3.12.x`.

---

## Step 5: Add your Groq API key

Get a key first:

1. Go to [console.groq.com](https://console.groq.com) and sign in.
2. Open **API Keys** in the left sidebar.
3. Click **Create API Key**, name it `pharmaiq`, and create it.
4. Copy it immediately. Groq shows a key once and never again.

Now create your `.env` file:

```powershell
Copy-Item .env.example .env
notepad .env
```

Notepad opens. Replace `your-groq-key-here` with your key, so the line reads:

```
GROQ_API_KEY=gsk_yourkeyhere
```

No quotes and no spaces around the `=`. Save and close Notepad.

Check the key is being read. This prints `True` or `False`, never the key
itself:

```powershell
uv run python -c "import config; print('key loaded:', bool(config.GROQ_API_KEY))"
```

**Important:** put your key in `.env`, never in `.env.example`. `.env` is
ignored by Git and will never be uploaded. `.env.example` is a tracked template
and anything you put there can end up public.

---

## Step 6: Build the local database

```powershell
uv run python -m database.build
```

This creates `data\pharmaiq.db` and fills it with generated sales data: 60
products across 10 therapy areas, 120 customer accounts (90 in the USA, 30 in
India), 26 territories across five regions, and 3600 orders. All of it is synthetic. None of it is real business data.

You should see the therapy areas listed with their totals:

```
Database built at C:\Users\you\PharmaIQ\data\pharmaiq.db
Total sales by therapy area:
  Diabetes Care          6,165,416.47
  Heart Health           6,092,481.18
  Mental Health          4,510,484.49
  ...
```

The numbers will match these exactly, because the data is generated from a
fixed random seed.

---

## Step 7: Download the research

The assistant can only answer research questions about topics you have
ingested. Run these three, one at a time:

```powershell
uv run python -m ingestion.ingest --topic "obesity weight loss treatment" --limit 25
uv run python -m ingestion.ingest --topic "type 2 diabetes treatment" --limit 25
uv run python -m ingestion.ingest --topic "heart failure blood pressure cholesterol treatment" --limit 25
```

Each one fetches 25 clinical trials and 25 papers, splits them into searchable
pieces, and adds them to the search index. Neither source needs an API key.

**The first one is slow.** It downloads a small language model, about 80 MB,
used to turn text into searchable vectors. Later runs reuse it.

After all three you should see:

```
search index now holds 731 chunks
```

To add other areas later, use the same command with a different topic. Your
database has ten therapy areas and only three now have research behind them,
so questions about Cancer Care or Respiratory will correctly report that no
research was found.

---

## Step 8: Run the tests

```powershell
uv run pytest
```

Expect `167 passed`. This suite runs offline and makes no API calls, so it
costs nothing and works without a network connection.

To run the few tests that call Groq for real:

```powershell
uv run pytest -m llm
```

These are skipped by default, which is why the normal run is fast and free.

---

## Step 9: Start the app

```powershell
uv run streamlit run app.py
```

Then open **http://localhost:8501** in your browser.

Windows may show a firewall prompt the first time. Allow it on private
networks. The app only listens on your own machine.

The first question takes about 20 seconds while the search model loads. After
that answers take a few seconds.

The sidebar should show:

```
Research extracts   731
Orders              3,600
```

If it says 0 extracts, step 7 did not finish. If it warns about a missing API
key, step 5 did not finish.

---

## Step 10: Try it

Type these into the box and press the **arrow button** to send. Each one takes
a different path through the system.

**Research only.** Reads studies, cites sources, never touches the database.

```
What do recent studies report about treatments for type 2 diabetes?
```

**Sales only.** Writes a database query, no research.

```
Which sales representative covers the best performing territory?
```

**Both at once.** This is the interesting one. It reads the research first,
works out which therapy areas it is about, checks those against the product
catalogue, and only then queries sales.

```
Recent research covers diabetes and heart treatments. Compare how those two therapy areas are performing across our regions.
```

**Off topic.** Turned away without doing any work.

```
What is the weather today?
```

Under each answer, click the panels to see how it was reached: what research
was found, what was pulled out of it, and the exact query that produced the
numbers.

---

## Step 11: Stop the app

Click on the PowerShell window and press **Ctrl+C**.

If you already closed that window and the app is still running, closing every
PowerShell window will stop it. Avoid hunting for the process by name: on
Windows it may appear as `python` rather than `streamlit`, and stopping every
`python` process would take unrelated programs with it. If the port stays
busy, simply start the app on another one, as described in Troubleshooting.

---

## Optional: the MCP server

The same three data operations can be exposed to an MCP client such as Claude
Desktop:

```powershell
uv run python server.py
```

It offers `search_research_documents`, `get_database_schema`, and
`execute_sql_query`. Queries are read only and anything that is not a single
SELECT is rejected.

---

## Starting up again later

Once set up, you only need this:

```powershell
cd $HOME\PharmaIQ
uv run streamlit run app.py
```

The database and the research index are stored on disk in `data\` and
`chroma_db\`, so they survive restarts. You only repeat steps 6 and 7 if you
delete those folders or want to add new research topics.

---

## Troubleshooting

**`uv` is not recognized**
You did not reopen PowerShell after installing it. Close the window, open a new
one, and try again.

**The uv install command is blocked**
Windows is refusing to run the script. The `-ExecutionPolicy ByPass` in the
command should handle it. If not, download the installer directly from
[docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/).

**`uv sync` fails while building a package**
Usually a path length limit. Two options: move the project somewhere short
like `C:\dev\PharmaIQ`, or enable long paths by running PowerShell as
Administrator and entering:

```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

**`No database at ...` when starting the app**
You skipped step 6. Run `uv run python -m database.build`.

**The sidebar shows 0 research extracts**
You skipped step 7, or it failed partway. Re-run the ingest commands. They
cache what they already downloaded, so a repeat run is quick.

**`Port 8501 is already in use`**
Something else is on that port, or a previous copy is still running. Use a
different one:

```powershell
uv run streamlit run app.py --server.port 8502
```

Then open http://localhost:8502 instead.

**`The model ... does not exist or you do not have access to it`**
Groq changes which models it offers. See what your key can reach:

```powershell
uv run python -c "import requests, config; r=requests.get('https://api.groq.com/openai/v1/models', headers={'Authorization': 'Bearer '+config.GROQ_API_KEY}); print(*sorted(m['id'] for m in r.json()['data']), sep=chr(10))"
```

Pick a chat model from the list and add it to `.env` on its own line, for
example:

```
GROQ_MODEL=openai/gpt-oss-120b
```

**`Error code: 429` or a rate limit message**
Groq's free tier limits requests per minute. Wait a minute and ask again.
Nothing is broken.

**Ingestion fails to reach the internet**
ClinicalTrials.gov and PubMed are public, but a company network or VPN may
block them. Try a different network.

**The first question hangs for a long time**
Normal on a fresh start. The search model is loading. It only happens once per
run of the app.
