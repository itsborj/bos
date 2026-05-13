# Claude Chat Agent Client

This directory contains the Claude.ai chat agent client for BOS.

## Purpose

The Claude chat agent is an external client that connects to the BOS API. It acts as a "bridge" - translating external chat messages into BOS API calls.

## Architecture

```
User (Claude.ai) → Claude Agent Client → BOS API (/chat, /runs)
```

## Files

- `client.ts` - Main client that connects to Claude.ai and translates messages to BOS API
- `types.ts` - Shared types for the client
- `config.ts` - Configuration (API endpoints, keys)

## Setup

```bash
npm install
```

## Running

```bash
npm start
```

## How it works

1. User sends message to Claude.ai
2. Claude Agent receives webhook/API call
3. Agent calls BOS `POST /chat` with the message
4. BOS returns response + any run results
5. Agent formats and returns response to Claude.ai

## BOS Principle

The BOS API is the interface. Agents (like this client) call it like any other HTTP client. The BOS core does not know about specific agents.
