# Next steps

## Current status (2026-10-19)

- Done: scraper, API, React frontend, zero-shot CLIP photo guesses (ML v1), deploy prep (device IDs, privacy notice, photo metadata stripping, Docker image) and UI polish.
- 246 tests pass (164 pytest + 82 Vitest).
- Not hosted yet. To share it, run it in Docker on the Mac and expose it with a temporary Cloudflare tunnel.

## Demo in one command

```bash
chmod +x scripts/demo.sh   # once
scripts/demo.sh
```

- It stops any old `macros` container, rebuilds the image, starts the app, waits for `/api/health`, opens the Cloudflare tunnel, and prints only the public `https://….trycloudflare.com` link. Wait ~10 seconds before opening it; if a device opens it too early, its DNS can cache "not found" for a while.
- It keeps the Mac awake (`caffeinate`) while it runs. Keep the lid open and the charger plugged in.
- Control+C stops the tunnel, caffeinate and the container.
- Scrape menus first (step 2 below). The script doesn't scrape.
- If something fails, it prints one line saying which step and where its log is.

## Run it by hand: Docker + Cloudflare tunnel

```bash
# 1. Build the image (once, and again after code changes)
docker build -t macros .

# 2. Scrape today's menus into docker-data/ (once a day; takes ~10 min)
docker run --rm -v "$PWD/docker-data:/data" macros python -m scraper.daily_scrape

# 3. Start the app in the background at http://localhost:8080
docker run -d --name macros -p 8080:8080 -v "$PWD/docker-data:/data" macros

# 4. Share it: a temporary public https URL that forwards to the app
cloudflared tunnel --url http://127.0.0.1:8080 --protocol http2
```

- The tunnel must point to `http://127.0.0.1:8080` (the Docker port).
- Keep `--protocol http2`. It makes the tunnel use TCP instead of QUIC (UDP), which some networks block.
- Copy the `https://….trycloudflare.com` URL that `cloudflared` prints. The URL is new each time the tunnel restarts, and it only works while the Mac is awake and both commands are running.
- Stop the app with `docker stop macros && docker rm macros`. Ctrl+C stops the tunnel.

## Remaining tasks (optional, in this order)

1. **Log 15–20 plate photos.** Log real dining hall meals through the photo screen, picking the right dishes each time. Each logged photo becomes labeled data.
2. **Run the evaluation** on those photos:
   ```bash
   docker run --rm -v "$PWD/docker-data:/data" macros python -m ml.export_training_data
   docker run --rm -v "$PWD/docker-data:/data" macros python -m ml.evaluate --training
   ```
   Record top-1 / top-3 / recall@5 in `DECISIONS.md`.
3. **Share with the club.** Send them the tunnel URL and collect feedback and usage.
4. **Filter condiments from the CLIP candidates.** About 250 dishes per meal includes toppings like Butter that crowd out real dishes. Filter them, then re-run step 2 to check that the scores improve.
5. **Real hosting.** Deploy the Docker image (Fly.io is the leading option; see the Deploy section of `DECISIONS.md`), with a mounted volume for `/data` and a scheduled daily scrape.
