# Dhoop (धूप) — Telegram Sunlight Audit Bot

> **Check direct sunlight for any apartment, balcony, or spot in seconds.**
> Built with **n8n** (orchestration) + **Docker** (reproducible runtime) + **Blender Cycles CPU** (BVH ray-cast & 3D shadow rendering).

---

## 1. How It Works

1. Send a **location pin** on Telegram.
2. Tap your **floor** (`Ground`, `2nd`, `5th`, `10th`) and **facing direction** (`N`, `E`, `S`, `W`, `Not sure`).
3. Get back:
   - A rendered **3D shadow time-lapse (MP4)** showing building shadows moving across your block.
   - A **sun-hours report** for **Today**, the **Shortest Day (Dec 21)**, and the **Longest Day (Jun 21)** with time windows and a data-confidence rating.

```
Telegram User ──▶ n8n (Intake WF) ──POST /v1/jobs──▶ Worker (FastAPI)
                                                            │
                                              ┌─────────────┴─────────────┐
                                              ▼                           ▼
                                      Blender (BVH raycast)      Blender (Cycles CPU)
                                              │                           │
                                         Sun Hours                 Shadow Time-lapse
                                              └─────────────┬─────────────┘
                                                            ▼
Telegram User ◀── Telegram (Send Animation) ◀── n8n (Result WF)
```

---

## 2. Quickstart Setup (<= 10 Commands)

```bash
# 1. Clone repository and navigate inside
cd Dhoop

# 2. Configure environment
cp .env.example .env

# 3. Build the worker image (Blender bpy + ffmpeg)
docker-compose build worker

# 4. Start worker and n8n services
docker-compose up -d

# 5. Check worker health
curl http://localhost:8000/healthz

# 6. Pre-seed demo cache for instant offline runs
python scripts/seed_demo_cache.py

# 7. Run E2E smoke test
bash scripts/e2e_smoke.sh
```

---

## 3. Telegram & n8n Integration

1. In Telegram, talk to [@BotFather](https://t.me/BotFather) to create your bot and get the `TELEGRAM_BOT_TOKEN`.
2. Start tunnel (e.g. ngrok or cloudflared) pointing to n8n port `5678`, set `PUBLIC_URL` in `.env`.
3. Open `http://localhost:5678` and import the 3 workflows from `n8n/workflows/`:
   - `dhoop-intake.json`: Telegram trigger, inline keyboards, job enqueue.
   - `dhoop-result.json`: Webhook receiver, time-lapse video delivery, summary message formatting.
   - `dhoop-ops.json`: Error workflow and admin alert.
4. Add credential `Dhoop Telegram` with your bot token and activate the workflows.

---

## 4. Testing

```bash
# Run unit tests (height parsing, OSM relations, geometry projection, sun calculation)
docker-compose run --rm worker pytest worker/tests -v

# Run the mandatory analytic shadow test (10m wall at 30° elevation)
docker-compose run --rm worker pytest worker/tests/test_raycast.py -v
```

---

## 5. Offline Demo Mode

To run completely offline without calling public Overpass API servers:
```bash
DEMO_FIXTURES=1 docker-compose up -d
```
Pre-seeded fixtures cover:
- **Campus**: IISc Bengaluru (`13.0185, 77.5650`)
- **Residential**: Dense block with multipolygon courtyard (`12.9780, 77.6400`)
- **Open Area**: Public park / open field (`12.9750, 77.5920`)

---

## 6. Limitations & Attribution

- **Terrain & Overhangs**: Ground is assumed flat; individual window overhangs and trees are not modelled.
- **Estimated Heights**: Unspecified building heights are estimated using the median of the 5 nearest explicit neighbours and flagged with a confidence score.
- **Data Attribution**: Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) (ODbL).
