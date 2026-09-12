# Quiet Agent Control Room

CopilotKit companion UI for the Slack intervention agent. It turns the SQLite
evaluation log into a live “proof of restraint” panel and adds a CopilotKit
sidebar powered by the same OpenRouter model configuration.

## Run it

Keep the Python Slack agent running first. It now starts the local control API
on `http://127.0.0.1:8765`.

```powershell
cd C:\Users\nideshpande\Downloads\AITinkerers\control-room
Copy-Item .env.example .env.local
# Put your OpenRouter key and model in .env.local
npm install
npm run dev
```

Open `http://localhost:3000`.

The browser uses `NEXT_PUBLIC_CONTROL_API_URL` to read the local decision log.
The CopilotKit runtime remains server-side and reads `OPENROUTER_API_KEY` from
`.env.local`; never place that key in a `NEXT_PUBLIC_` variable.
