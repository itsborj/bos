export const config = {
  bos: {
    apiUrl: process.env.BOS_API_URL || 'http://localhost:8000',
    apiKey: process.env.BOS_API_KEY || '',
  },
  claude: {
    apiKey: process.env.CLAUDE_API_KEY || '',
    webhookSecret: process.env.CLAUDE_WEBHOOK_SECRET || '',
  },
};
