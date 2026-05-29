# KVIS Analyzer 🔍📺

**TubeCoach** — by KRGN Systems

YouTube channel intelligence for content creators. Analyze any channel, understand your audience, get actionable next steps.

Works for any channel size: from 10 subscribers to 100M.

## What it does

Give KVIS a YouTube channel URL and it builds a complete intelligence report:

- 📝 **Transcription** — Full transcript extraction with timestamps
- 🧠 **Content Analysis** — Key insights ("nutrients") extracted from each video
- 🎵 **Audio Spectrum** — Spectral analysis of video audio
- 🔗 **Cross-Analysis** — Fusion of transcript + audio for deeper insights
- 💬 **Fan Analysis** — Comment extraction, sentiment, top fans, engagement rate
- 👥 **Audience Overlap** — Compare audiences between channels, find shared fans
- 🏷️ **Auto-Classification** — Categorize videos by topic automatically
- 🔍 **Semantic Search** — Search across all your transcripts and insights
- 📊 **Channel Audit** — Full pipeline: what's working, what's not, what's next

## Use cases

| Who | What they get |
|-----|--------------|
| **Small creator** (100 subs) | What content resonates, which videos grow, audience profile |
| **Growing channel** (1K-100K) | Engagement patterns, best performing topics, fan loyalty |
| **Established creator** (100K+) | Audience overlap with peers, content gaps, cross-promo opportunities |
| **Agencies / Managers** | Compare multiple clients, benchmark against competitors |

## Quick start

```bash
git clone https://github.com/vpino/kvis-analyzer.git
cd kvis-analyzer
pip install -r requirements.txt
```

### Analyze a single video

```bash
python kvis.py process https://youtube.com/watch?v=VIDEO_ID
```

### Deep analysis (transcript + audio + spectrum + cross)

```bash
python kvis.py deep https://youtube.com/watch?v=VIDEO_ID
```

### Analyze fan comments on a channel

```bash
python kvis.py comments https://youtube.com/@channelhandle
```

### Compare audiences between channels

```bash
python kvis.py audience https://youtube.com/@creator1 https://youtube.com/@creator2
```

### Search across analyzed videos

```bash
python kvis.py search "production techniques"
```

### Full channel audit

```bash
# Process multiple videos from a channel
python kvis.py batch https://youtube.com/watch?v=ID1 https://youtube.com/watch?v=ID2 https://youtube.com/watch?v=ID3

# Then synthesize insights
python kvis.py synthesize
```

## All commands

| Command | What it does |
|---------|-------------|
| `process` | Quick pipeline: extract transcript + analyze |
| `deep` | Full pipeline: transcript + audio + spectrum + cross-analysis |
| `batch` | Process multiple URLs at once |
| `comments` | Analyze comments: sentiment, top fans, engagement rate |
| `audience` | Compare audiences between 2+ channels |
| `search` | Semantic search across transcripts and insights |
| `catalog` | Browse analyzed videos by category and tags |
| `synthesize` | Combine insights from multiple videos |
| `extract` | Extract transcript only |
| `analyze` | Analyze transcript only (nutrient extraction) |
| `audio` | Download audio for spectral analysis |
| `spectral` | Audio spectrum analysis |
| `cross` | Cross-analysis: transcript + audio fusion |
| `classify` | Auto-classify video by topic |
| `teach` | Extract key lessons from a video |
| `keyframes` | Extract keyframes by scene detection |
| `smart` | Auto-detect content type, run optimal pipeline |
| `status` | View pipeline status (all processed videos) |

## Project structure

```
kvis-analyzer/
├── kvis.py                   # CLI entry point
├── kvis/
│   ├── __init__.py
│   ├── cli.py                # 20+ subcommands dispatcher
│   ├── constants.py          # Configurable paths
│   ├── extract.py            # YouTube transcript extraction
│   ├── analyze.py            # Nutrient extraction engine
│   ├── pipeline.py           # Composable pipelines
│   ├── comments.py           # Comment analysis + fan detection
│   ├── audience.py           # Cross-channel audience comparison
│   ├── audio.py              # Audio download
│   ├── spectral.py           # Audio spectrum analysis
│   ├── cross.py              # Transcript × audio cross-analysis
│   ├── compare.py            # Multi-video comparison
│   ├── classify.py           # Auto-classification
│   ├── teach.py              # Lesson extraction
│   ├── reducer.py            # Relevance filtering
│   ├── search.py             # Semantic search (TF-IDF + neural)
│   ├── keyframes.py          # Scene detection + keyframes
│   ├── smart.py              # Auto-detect pipeline
│   ├── synthesize.py         # Multi-video synthesis
│   ├── status.py             # Pipeline status
│   ├── build_catalog.py      # Catalog builder
│   ├── autocat.py            # Auto-categorization
│   ├── integrate.py          # Knowledge store integration
│   └── utils.py              # Shared utilities
├── data/sample/              # Example data
├── requirements.txt
└── README.md
```

## Tested with

| Channel | Size | Use case |
|---------|------|----------|
| @akajohnbazooka | Micro | Personal music production channel |
| @matiaszeta | Small | Artist channel — fan engagement |
| @lolobenj4 | Small | Peer comparison — shared audiences |
| @katteyes | Medium | Cross-genre audience analysis |
| @misterbeast | Mega (300M+) | Stress test — massive comment volume |

46+ videos analyzed in production.

## Tech stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| CLI | argparse (20+ subcommands) |
| YouTube data | yt-dlp, youtube-transcript-api |
| Analysis | numpy, scikit-learn |
| Search | TF-IDF + sentence-transformers (optional) |
| Data | JSON (portable, no database required) |

## Technical concepts demonstrated

| Pattern | Where |
|---------|-------|
| Pipeline composition | `process` → `deep` → `batch` |
| CLI with subcommands | argparse dispatcher pattern |
| ETL | Extract transcript → Transform to nutrients → Load to data store |
| Semantic search | TF-IDF + cosine similarity |
| Cross-analysis | Multi-dimensional fusion (text + audio) |
| Sentiment analysis | Comment classification and fan scoring |

## Roadmap

- [ ] Web dashboard (Django) for visual channel reports
- [ ] API REST to query analysis results
- [ ] OOP refactor (Video, Channel, Analyzer classes)
- [ ] Scheduled monitoring — track channel growth over time
- [ ] PDF report generation for client delivery
- [ ] Competitor benchmarking

## Author

**Víctor Pino Alonso** ([johnbazooka](https://github.com/johnbazooka)) — Founder, KRGN Systems

## License

MIT
