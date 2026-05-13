# NVIDIA NIM API Setup for Pi Coding Agent

This guide covers adding NVIDIA NIM (NVIDIA Inference Microservices) models to pi via the custom `models.json` configuration, including API log-in/authentication.

## Overview

NVIDIA NIM provides OpenAI-compatible API endpoints for various models (Llama 3, Mistral, etc.) through `integrate.api.nvidia.com`. Since the NIM API uses the OpenAI chat completions format, it's configured in pi via `~/.pi/agent/models.json` as a custom provider.

## Prerequisites

1. **NVIDIA API Key**: Get one from [build.nvidia.com](https://build.nvidia.com/)
2. **Set Environment Variable** (recommended):
   ```bash
   export NVIDIA_API_KEY="your-api-key-here"
   ```

## Configuration File Location

`~/.pi/agent/models.json` — Create this file if it doesn't exist.

## Basic Configuration

### Minimal Setup

```json
{
  "providers": {
    "nvidia-nim": {
      "baseUrl": "https://integrate.api.nvidia.com/v1",
      "api": "openai-completions",
      "apiKey": "NVIDIA_API_KEY",
      "models": [
        { "id": "meta/llama-3.1-405b-instruct" },
        { "id": "meta/llama3-70b-instruct" },
        { "id": "mistralai/mistral-nemo-12b-instruct" }
      ]
    }
  }
}
```

### Full Configuration (Recommended)

```json
{
  "providers": {
    "nvidia-nim": {
      "baseUrl": "https://integrate.api.nvidia.com/v1",
      "api": "openai-completions",
      "apiKey": "NVIDIA_API_KEY",
      "headers": {
        "User-Agent": "BOS-Client/1.0"
      },
      "models": [
        {
          "id": "meta/llama-3.1-405b-instruct",
          "name": "Llama 3.1 405B (NVIDIA NIM)",
          "reasoning": false,
          "input": ["text", "image"],
          "contextWindow": 128000,
          "maxTokens": 4096,
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 }
        },
        {
          "id": "meta/llama3-70b-instruct",
          "name": "Llama 3 70B Instruct",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 8192,
          "maxTokens": 4096,
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 }
        },
        {
          "id": "mistralai/mistral-nemo-12b-instruct",
          "name": "Mistral Nemo 12B",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 128000,
          "maxTokens": 4096,
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 }
        }
      ]
    }
  }
}
```

## API Key Authentication Options

### Option 1: Environment Variable (Recommended)

Set the key in your shell profile:

```bash
# ~/.bashrc or ~/.zshrc
export NVIDIA_API_KEY="nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Then in `models.json`:
```json
"apiKey": "NVIDIA_API_KEY"
```

Pi reads the env var at runtime.

### Option 2: Literal Value (Not Recommended)

```json
"apiKey": "nvapi-your-actual-key-here"
```

⚠️ **Security Risk**: The key is stored in plaintext on disk.

### Option 3: Shell Command (Secure)

Use a command to fetch the key from a secrets manager:

```json
"apiKey": "!security find-generic-password -ws 'nvidia-api-key'"
```

Or read from a protected file:
```json
"apiKey": "!cat ~/.config/nvidia/api-key"
```

### Option 4: Direct API Key Parameter

Pass the key directly when launching pi:

```bash
NVIDIA_API_KEY=nvapi-xxx pi --provider nvidia-nim --model meta/llama-3.1-405b-instruct
```

## Available NVIDIA NIM Models

Common models available through the NIM service:

| Model ID | Context Window | Description |
|----------|---------------|-------------|
| `meta/llama-3.1-405b-instruct` | 128K | Llama 3.1 405B (largest) |
| `meta/llama-3.1-70b-instruct` | 128K | Llama 3.1 70B |
| `meta/llama3-70b-instruct` | 8K | Llama 3 70B |
| `meta/llama3-8b-instruct` | 8K | Llama 3 8B |
| `mistralai/mistral-nemo-12b-instruct` | 128K | Mistral Nemo 12B |
| `mistralai/mixtral-8x7b-instruct` | 8K | Mixtral 8x7B |
| `google/gemma-2-27b-it` | 8K | Gemma 2 27B |

Check [build.nvidia.com](https://build.nvidia.com/) for the full, up-to-date list.

## Usage in Pi

### Switch to NVIDIA Model

1. Start pi:
   ```bash
   pi
   ```

2. Switch model with `/model` command:
   - Type `/model` in the editor
   - Select `nvidia-nim/meta/llama-3.1-405b-instruct`
   - Or use Ctrl+L for the model selector

3. Or specify on launch:
   ```bash
   pi --provider nvidia-nim --model meta/llama-3.1-405b-instruct
   ```

### List Available Models

```bash
pi --list-models nvidia-nim
```

## Troubleshooting

### "Invalid API Key" Error

1. Verify the key is set:
   ```bash
   echo $NVIDIA_API_KEY
   ```

2. Check key format — should start with `nvapi-`

3. Regenerate the key at [build.nvidia.com](https://build.nvidia.com/) if needed

### Model Not Found

- Verify the exact model ID on NVIDIA's site
- Model IDs are case-sensitive: `meta/llama-3.1-405b-instruct` ≠ `meta/Llama-3.1-405B-instruct`

### Rate Limiting

NIM has rate limits based on your account tier. If you see 429 errors:
- Add retry logic in your client code (handled outside pi)
- Upgrade your NVIDIA account
- Reduce request frequency

### Connection/Timeout Issues

Ensure the baseUrl is correct:
```json
"baseUrl": "https://integrate.api.nvidia.com/v1"
```

## Custom Headers Example

For enterprise proxies or custom auth:

```json
{
  "providers": {
    "nvidia-nim": {
      "baseUrl": "https://integrate.api.nvidia.com/v1",
      "api": "openai-completions",
      "apiKey": "NVIDIA_API_KEY",
      "authHeader": true,
      "headers": {
        "Authorization": "Bearer NVIDIA_API_KEY",
        "X-Custom-Tracking": "BOS-Internal"
      },
      "models": [...]
    }
  }
}
```

## Multiple Providers Example

Combine NVIDIA with other providers:

```json
{
  "providers": {
    "nvidia-nim": {
      "baseUrl": "https://integrate.api.nvidia.com/v1",
      "api": "openai-completions",
      "apiKey": "NVIDIA_API_KEY",
      "models": [
        { "id": "meta/llama-3.1-405b-instruct" }
      ]
    },
    "openrouter": {
      "apiKey": "OPENROUTER_API_KEY",
      "models": [
        { "id": "anthropic/claude-3.5-sonnet" }
      ]
    }
  }
}
```

## Related Files

- Sample configs: `~/cl_bos/sample/nvidia-api-log-config.json`
- Pi docs: `docs/models.md`
- Pi custom-provider docs: `docs/custom-provider.md`

## Notes

- The `api` field must be `"openai-completions"` for NVIDIA NIM
- NVIDIA NIM does **not** support reasoning/extended thinking parameters, so `"reasoning": false`
- Context window and max tokens vary by model — check NVIDIA docs
- No streaming token usage in responses for some older NIM deployments (set `"supportsUsageInStreaming": false` in `compat` if needed)
