#!/usr/bin/env bash
set -e

WORKER_URL=${WORKER_URL:-"http://localhost:8000"}

echo "=== Dhoop E2E Smoke Test ==="
echo "1. Checking healthz at $WORKER_URL/healthz"
curl -s -f "$WORKER_URL/healthz" | grep '"ok":true'
echo "Health check passed!"

echo "2. Enqueuing test job (IISc Campus fixture)"
JOB_RESP=$(curl -s -X POST "$WORKER_URL/v1/jobs" \
  -H "Content-Type: application/json" \
  -d '{"lat":13.0185,"lon":77.5650,"floor":2,"facing":"E","radius_m":300,"meta":{"chat_id":12345}}')

echo "Response: $JOB_RESP"
JOB_ID=$(echo "$JOB_RESP" | grep -o '"job_id":"[^"]*' | cut -d'"' -f4)
echo "Enqueued Job ID: $JOB_ID"

echo "3. Polling job status..."
for i in {1..30}; do
  STATUS_RESP=$(curl -s "$WORKER_URL/v1/jobs/$JOB_ID")
  STATUS=$(echo "$STATUS_RESP" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
  echo "Attempt $i: status = $STATUS"
  if [ "$STATUS" = "done" ]; then
    echo "Job completed successfully!"
    break
  fi
  if [ "$STATUS" = "failed" ]; then
    echo "Job failed!"
    exit 1
  fi
  sleep 3
done

echo "4. Checking artifact download"
curl -s -f -o /tmp/timelapse.mp4 "$WORKER_URL/v1/jobs/$JOB_ID/artifacts/timelapse.mp4"
echo "Artifact downloaded successfully! Size: $(wc -c < /tmp/timelapse.mp4) bytes"

echo "=== All E2E checks passed! ==="
