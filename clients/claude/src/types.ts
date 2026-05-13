export interface ClaudeMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ClaudeWebhookPayload {
  message: string;
  user_id: string;
  conversation_id?: string;
}

export interface BOSChatRequest {
  message: string;
  history?: { role: 'user' | 'ai'; text: string }[];
}

export interface BOSChatResponse {
  reply: string;
  runs?: BOSRunResult[];
  run?: BOSRunResult;
}

export interface BOSRunResult {
  run_id: string;
  module_id: string;
  status: string;
  result?: {
    content: string;
    self_check: string;
  };
}
