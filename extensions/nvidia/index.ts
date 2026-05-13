import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.registerProvider("nvidia", {
    name: "NVIDIA AI Cloud",
    baseUrl: "https://api.nvidia.com/v1",
    apiKey: "NVIDIA_API_KEY",
    api: "openai-completions",
    authHeader: true,
    headers: {
      "Accept": "application/json"
    },
    models: [
      {
        id: "nvidia/llama3-70b-chat",
        name: "NVIDIA Llama 3 70B Chat",
        reasoning: false,
        input: ["text"],
        cost: { input: 0.25, output: 0.25, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 8192,
        maxTokens: 2048,
        compat: {
          supportsDeveloperRole: false,
          requiresToolResultName: false
        }
      },
      {
        id: "nvidia/llama3-8b-chat",
        name: "NVIDIA Llama 3 8B Chat",
        reasoning: false,
        input: ["text"],
        cost: { input: 0.25, output: 0.25, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 8192,
        maxTokens: 2048,
        compat: {
          supportsDeveloperRole: false,
          requiresToolResultName: false
        }
      },
      {
        id: "nvidia/mistral-8b-instruct-v0.2",
        name: "NVIDIA Mistral 8B Instruct",
        reasoning: false,
        input: ["text"],
        cost: { input: 0.25, output: 0.25, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 8192,
        maxTokens: 2048,
        compat: {
          supportsDeveloperRole: false,
          requiresToolResultName: false
        }
      },
      {
        id: "nvidia/mixtral-8x7b-instruct-v0.1",
        name: "NVIDIA Mixtral 8x7B Instruct",
        reasoning: false,
        input: ["text"],
        cost: { input: 0.25, output: 0.25, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 8192,
        maxTokens: 2048,
        compat: {
          supportsDeveloperRole: false,
          requiresToolResultName: false
        }
      },
      {
        id: "nvidia/nemotron-4b-chat",
        name: "NVIDIA Nemotron 4B Chat",
        reasoning: false,
        input: ["text"],
        cost: { input: 0.25, output: 0.25, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 4096,
        maxTokens: 1024,
        compat: {
          supportsDeveloperRole: false,
          requiresToolResultName: false
        }
      },
      {
        id: "nvidia/granite-8b-chat",
        name: "NVIDIA Granite 8B Chat",
        reasoning: false,
        input: ["text"],
        cost: { input: 0.25, output: 0.25, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 4096,
        maxTokens: 1024,
        compat: {
          supportsDeveloperRole: false,
          requiresToolResultName: false
        }
      },
      {
        id: "nvidia/codegen2-16b",
        name: "NVIDIA CodeGen 2 16B",
        reasoning: false,
        input: ["text"],
        cost: { input: 0.25, output: 0.25, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 4096,
        maxTokens: 1024,
        compat: {
          supportsDeveloperRole: false,
          requiresToolResultName: false
        }
      }
    ]
  });
}