# chronoq

A self-hostable distributed job scheduler. Cron-as-a-service, done right.

## Why

Small teams and indie developers need reliable scheduled jobs without paying $50/month
or babysitting a cron on a random VPS. chronoq gives you retries, alerts, execution
history, and a dashboard — all self-hosted.

## Status

🚧 In active development. See `docs/roadmap.md` for the phased build plan.

## Quick start

    cp .env.example .env
    docker compose up --build

Dashboard: http://localhost:3000
API: http://localhost:8000/api
