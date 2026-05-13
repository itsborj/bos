import axios from 'axios';
import { config } from './config';
import type { ClaudeWebhookPayload, BOSChatResponse } from './types';

const bosClient = axios.create({
  baseURL: config.bos.apiUrl,
  headers: {
    'X-API-Key': config.bos.apiKey,
    'Content-Type': 'application/json',
  },
});

/**
 * Handle incoming webhook from Claude.ai
 * This function receives a message from Claude and forwards it to BOS
 */
export async function handleClaudeMessage(payload: ClaudeWebhookPayload): Promise<string> {
  try {
    // Call BOS chat endpoint
    const response = await bosClient.post<BOSChatResponse>('/chat', {
      message: payload.message,
      history: [], // TODO: retrieve conversation history if conversation_id provided
    });

    const { reply, runs } = response.data;

    // Format response for Claude
    let formattedReply = reply;

    // If there are run results, append them
    if (runs && runs.length > 0) {
      formattedReply += '\n\n--- Module Results ---';
      for (const run of runs) {
        formattedReply += `\n- ${run.module_id}: ${run.status}`;
        if (run.result?.content) {
          formattedReply += `\n  ${run.result.content.slice(0, 100)}...`;
        }
      }
    }

    return formattedReply;
  } catch (error) {
    console.error('Error calling BOS API:', error);
    return 'Sorry, there was an error processing your request.';
  }
}

/**
 * Start the Claude agent (placeholder for webhook server)
 */
export function startAgent() {
  console.log('Claude agent client initialized.');
  console.log(`BOS API: ${config.bos.apiUrl}`);
  console.log('Waiting for webhook connections...');
  
  // TODO: Implement webhook server (Express, etc.)
  // TODO: Register webhook with Claude.ai
}

// If running directly
if (require.main === module) {
  startAgent();
}
