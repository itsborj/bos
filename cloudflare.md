# Cloudflare Workers AI Image Generation API - Documentation

## Overview
This document covers the setup and troubleshooting of a Cloudflare Workers AI Image Generation API that provides 100,000 free API calls per day using Cloudflare Workers.

## API Endpoints

### Base URL
```
https://cloudflare-worker.jvcatingub.workers.dev/
```

### Authentication
- **Method:** Bearer Token
- **Header:** `Authorization: Bearer <API_KEY>`
- **Environment Variable:** `API_KEY`

### Request Format
```json
POST /
{
  "prompt": "Your image description here"
}
```

### Headers Required
```http
Authorization: Bearer <your-api-key>
Content-Type: application/json
```

### Response
- **Success:** `image/png` (1024x1024 pixels)
- **Error:** `application/json` with error message

## Test Scripts

### Python Test Script
Create `test_cloudflare_ai.py`:
```python
#!/usr/bin/env python3
import requests
import argparse

def generate_image(worker_url, api_key, prompt, output_path):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"prompt": prompt}

    response = requests.post(worker_url, headers=headers, json=payload, timeout=60)

    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"✅ Image saved to: {output_path}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", default="image.png")
    args = parser.parse_args()

    generate_image(args.url.rstrip("/"), args.api_key, args.prompt, args.output)
```

### cURL Test
```bash
curl -X POST "https://cloudflare-worker.jvcatingub.workers.dev/" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A cute robot"}' \
  -o image.png
```

## Issues & Solutions

### Issue 1: "Hello World!" Response
**Symptom:** API returns "Hello World!" instead of generating images.

**Cause:** Worker code not deployed or still using default template.

**Solution:**
1. Go to Cloudflare Workers Dashboard
2. Edit the worker code
3. Replace Hello World code with the actual `worker.js`:
```javascript
export default {
    async fetch(request, env) {
        const API_KEY = env.API_KEY;
        const url = new URL(request.url);
        const auth = request.headers.get("Authorization");

        if (auth !== `Bearer ${API_KEY}`) {
            return json({ error: "Unauthorized" }, 401);
        }

        if (request.method !== "POST" || url.pathname !== "/") {
            return json({ error: "Not allowed" }, 405);
        }

        try {
            const { prompt } = await request.json();
            if (!prompt) return json({ error: "Prompt is required" }, 400);

            const result = await env.AI.run(
                "@cf/stabilityai/stable-diffusion-xl-base-1.0",
                { prompt }
            );

            return new Response(result, {
                headers: { "Content-Type": "image/jpeg" },
            });
        } catch (err) {
            return json({ error: "Failed to generate image", details: err.message }, 500);
        }
    },
};

function json(data, status = 200) {
    return new Response(JSON.stringify(data), {
        status,
        headers: { "Content-Type": "application/json" },
    });
}
```

### Issue 2: 401 Unauthorized
**Symptom:** Returns `{"error":"Unauthorized"}`.

**Cause:** API_KEY environment variable mismatch.

**Solution:**
1. Go to Worker Settings → Variables
2. Set `API_KEY` to your desired secret value
3. Ensure the same key is used in requests

### Issue 3: AI Binding Missing
**Symptom:** Worker crashes or fails to generate images.

**Cause:** AI binding not configured in worker settings.

**Solution:**
1. Go to Worker Settings → Variables
2. Under Service Bindings, click "Add binding"
3. Variable name: `AI`
4. Service: Select "Workers AI"

## Available Models
Other models you can use (replace in worker.js):
- `@cf/blackforestlabs/ux-1-schnell`
- `@cf/bytedance/stable-diffusion-xl-lightning`
- `@cf/lykon/dreamshaper-8-lcm`
- `@cf/runwayml/stable-diffusion-v1-5-img2img`
- `@cf/runwayml/stable-diffusion-v1-5-inpainting`
- `@cf/stabilityai/stable-diffusion-xl-base-1.0` (default)

## Environment Variables Needed
| Variable | Type | Description |
|----------|------|-------------|
| `API_KEY` | Secret | Authentication key for your API |
| `AI` | Binding | Workers AI service binding |

## Test Results Summary
- ✅ API Connection: Working
- ✅ Authentication: Valid
- ✅ Image Generation: Successful (1024x1024 PNG)
- ✅ Response Time: ~5-10 seconds

## Usage Examples

### JavaScript Fetch
```javascript
const res = await fetch("https://cloudflare-worker.jvcatingub.workers.dev/", {
  method: "POST",
  headers: {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ prompt: "A futuristic city" }),
});
const blob = await res.blob();
const img = document.createElement("img");
img.src = URL.createObjectURL(blob);
```

### Python Requests
```python
import requests

response = requests.post(
    "https://cloudflare-worker.jvcatingub.workers.dev/",
    headers={
        "Authorization": "Bearer YOUR_API_KEY",
        "Content-Type": "application/json",
    },
    json={"prompt": "A cute robot"}
)
with open("output.png", "wb") as f:
    f.write(response.content)
