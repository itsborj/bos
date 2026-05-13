# NVIDIA AI Cloud Provider for Pi

This extension registers NVIDIA's cloud AI models as a custom provider in the Pi coding agent.

## Configuration

Set your NVIDIA API key in your environment:

```bash
export NVIDIA_API_KEY="your-nvidia-api-key"
```

Or add to `.env.example`:
```env
NVIDIA_API_KEY=
```

## Available Models

The following NVIDIA models are registered:

| Model | Context Window | Max Tokens | Input Types |
|-------|---------------|------------|-------------|
| Llama 3 70B Chat | 8192 | 2048 | text |
| Llama 3 8B Chat | 8192 | 2048 | text |
| Mistral 8B Instruct | 8192 | 2048 | text |
| Mixtral 8x7B Instruct | 8192 | 2048 | text |
| Nemotron 4B Chat | 4096 | 1024 | text |
| Granite 8B Chat | 4096 | 1024 | text |
| CodeGen 2 16B | 4096 | 1024 | text |

All models use the OpenAI-compatible chat completions API and support standard tool calls.

## Usage

Once configured, you can select NVIDIA models in the Pi agent:

```typescript
// List available models
pi --list-models

// Use in chat
const response = await pi.chat({
  provider: "nvidia",
  model: "nvidia/llama3-70b-chat",
  messages: [...]
});
```

## API Details

- **Base URL**: `https://api.nvidia.com/v1`
- **API Type**: `openai-completions` (OpenAI-compatible chat completions)
- **Auth**: Bearer token via `NVIDIA_API_KEY`

## Notes

- All costs are listed in USD per million tokens (input/output)
- Actual pricing may vary by region or plan
- The provider uses OpenAI-compatible schema, so existing tool call handling works as expected
- NVIDIA's API expects standard OpenAI chat message format

## Troubleshooting

If you encounter issues:

1. Verify your API key is correctly set
2. Check that your key has sufficient permissions
3. Ensure the model name matches NVIDIA's catalog
4. Review NVIDIA's API documentation for rate limits